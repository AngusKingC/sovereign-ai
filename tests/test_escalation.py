"""
Tests for escalation flow in Orchestrator.

Tests the full escalation path: decision created → submitted to ApprovalGate → approved → re-routed → denied → task marked DENIED.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from core.schemas import Task, WorkerOutput, TaskStatus, EscalationDecision, EscalationTier, ApprovalActionType
from core.orchestrator import Orchestrator
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalResponse
from core.exceptions import CrossScopeAccessError


class TestEscalationFlow:
    """Test suite for escalation flow in Orchestrator."""
    
    @pytest.fixture
    def mock_memory_router(self):
        """Create a mock memory router."""
        router = AsyncMock()
        router.fetch = AsyncMock(return_value=[])
        router.write = AsyncMock()
        router.get_global_context = AsyncMock(return_value=None)
        router.set_global_context = AsyncMock()
        return router
    
    @pytest.fixture
    def mock_state_machine(self):
        """Create a mock task state machine."""
        state_machine = AsyncMock()
        state_machine.transition = AsyncMock(return_value=None)
        state_machine.can_transition = AsyncMock(return_value=True)
        return state_machine
    
    @pytest.fixture
    def mock_approval_gate(self):
        """Create a mock approval gate."""
        gate = AsyncMock(spec=ApprovalGate)
        gate.request_approval = AsyncMock()
        return gate
    
    @pytest.fixture
    def orchestrator(self, mock_memory_router, mock_state_machine, mock_approval_gate):
        """Create an orchestrator with mock dependencies."""
        with patch('core.orchestrator.TaskStateMachine', return_value=mock_state_machine):
            orch = Orchestrator(
                memory_router=mock_memory_router,
                cloud_fallback_model="gpt-4o",
                approval_gate=mock_approval_gate,
            )
            # Replace the state_machine with our mock
            orch.state_machine = mock_state_machine
            return orch
    
    @pytest.fixture
    def task(self):
        """Create a test task."""
        return Task(
            task_id=uuid4(),
            intent="Test task that requires escalation",
            complexity_score=0.9,
            priority="normal",
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.utcnow(),
        )
    
    @pytest.mark.asyncio
    async def test_orchestrator_creates_escalation_decision_when_no_worker_meets_minimum_score(self, orchestrator, task):
        """Test that EscalationDecision is created when no worker meets minimum routing score."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Route the task (should trigger escalation due to low score)
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orchestrator.route_task(task)
        
        # Verify escalation metadata in response
        assert "escalation" in result.metadata
        escalation_data = result.metadata["escalation"]
        assert escalation_data["task_id"] == str(task.task_id)
        assert escalation_data["escalation_tier"] == EscalationTier.CLOUD.value
        assert escalation_data["to_model"] == "gpt-4o"
    
    @pytest.mark.asyncio
    async def test_escalation_decision_tier_is_cloud_when_no_better_local_model_exists(self, orchestrator, task):
        """Test that EscalationDecision tier is CLOUD when no better local model exists."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orchestrator.route_task(task)
        
        # Verify escalation tier is CLOUD
        escalation_data = result.metadata["escalation"]
        assert escalation_data["escalation_tier"] == EscalationTier.CLOUD.value
    
    @pytest.mark.asyncio
    async def test_escalation_decision_created_trace_event_emitted_with_correct_fields(self, orchestrator, task):
        """Test that escalation_decision_created trace event is emitted with correct fields."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock emit_trace to capture calls
        with patch('core.orchestrator.emit_trace', AsyncMock()) as mock_emit:
            await orchestrator.route_task(task)
            
            # Verify trace event was called
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["event_type"].value == "ESCALATION_TRIGGERED"
            assert call_args[1]["component"].value == "ORCHESTRATOR"
            assert "task_id" in call_args[1]["data"]
            assert "escalation_tier" in call_args[1]["data"]
            assert "to_model" in call_args[1]["data"]
    
    @pytest.mark.asyncio
    async def test_approval_gate_request_approval_called_with_correct_approval_request(self, orchestrator, task, mock_approval_gate):
        """Test that ApprovalGate.request_approval is called with correct ApprovalRequest."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval response - approved
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=True,
            decision_reason="Approved for testing",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        ))
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orchestrator.route_task(task)
        
        # Verify ApprovalGate.request_approval was called
        assert mock_approval_gate.request_approval.called
        call_args = mock_approval_gate.request_approval.call_args
        approval_request = call_args[0][0]
        assert approval_request.action_type == ApprovalActionType.CLOUD_ESCALATION
        assert approval_request.task_id == str(task.task_id)
        assert "Escalate task" in approval_request.action_description
        assert approval_request.risk_level == "high"
    
    @pytest.mark.asyncio
    async def test_on_approval_decision_approved_set_to_true(self, orchestrator, task, mock_approval_gate):
        """Test that decision.approved is set to True on approval."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval response - approved
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=True,
            decision_reason="Approved for testing",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        ))
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orchestrator.route_task(task)
        
        # Verify decision.approved is True in response metadata
        escalation_data = result.metadata["escalation"]
        assert escalation_data["approved"] is True
    
    @pytest.mark.asyncio
    async def test_on_approval_task_redispatched_to_to_model(self, orchestrator, task, mock_approval_gate):
        """Test that task is re-dispatched to to_model on approval."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval response - approved
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=True,
            decision_reason="Approved for testing",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        ))
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orchestrator.route_task(task)
        
        # Verify response indicates re-dispatch to cloud model
        assert result.worker_id == "cloud"
        assert result.model_used == "gpt-4o"
        assert "escalated" in result.content.lower()
    
    @pytest.mark.asyncio
    async def test_on_approval_strategic_context_escalation_history_updated(self, orchestrator, task, mock_approval_gate, mock_memory_router):
        """Test that StrategicContext.escalation_history is updated on approval."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval response - approved
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=True,
            decision_reason="Approved for testing",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        ))
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orchestrator.route_task(task)
        
        # Verify set_global_context was called
        assert mock_memory_router.set_global_context.called
        call_args = mock_memory_router.set_global_context.call_args
        context = call_args[0][0]
        assert "approved" in context.escalation_history[-1].lower()
    
    @pytest.mark.asyncio
    async def test_on_approval_escalation_approved_trace_event_emitted(self, orchestrator, task, mock_approval_gate):
        """Test that escalation_approved trace event is emitted on approval."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval response - approved
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=True,
            decision_reason="Approved for testing",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        ))
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()) as mock_emit:
            await orchestrator.route_task(task)
            
            # Verify trace event was emitted
            assert mock_emit.called
            # Check for escalation approved message
            found_approved = False
            for call in mock_emit.call_args_list:
                if "approved" in call[1]["message"].lower():
                    found_approved = True
                    break
            assert found_approved
    
    @pytest.mark.asyncio
    async def test_on_denial_task_transitioned_to_task_status_denied(self, orchestrator, task, mock_approval_gate, mock_state_machine):
        """Test that task is transitioned to TaskStatus.DENIED on denial."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval response - denied
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=False,
            decision_reason="Denied for testing",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        ))
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orchestrator.route_task(task)
        
        # Verify state_machine.transition was called with DENIED
        assert mock_state_machine.transition.called
        call_args = mock_state_machine.transition.call_args
        assert call_args[0][1] == TaskStatus.DENIED
        assert "denied" in call_args[0][2].lower()
    
    @pytest.mark.asyncio
    async def test_on_denial_escalation_denied_trace_event_emitted(self, orchestrator, task, mock_approval_gate):
        """Test that escalation_denied trace event is emitted on denial."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval response - denied
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=False,
            decision_reason="Denied for testing",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        ))
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()) as mock_emit:
            await orchestrator.route_task(task)
            
            # Verify trace event was emitted
            assert mock_emit.called
            # Check for escalation denied message
            found_denied = False
            for call in mock_emit.call_args_list:
                if "denied" in call[1]["message"].lower():
                    found_denied = True
                    break
            assert found_denied
    
    @pytest.mark.asyncio
    async def test_on_denial_orchestrator_returns_gracefully_no_raise(self, orchestrator, task, mock_approval_gate):
        """Test that orchestrator returns gracefully on denial without raising."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval response - denied
        mock_approval_gate.request_approval = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=False,
            decision_reason="Denied for testing",
            approved_by="test_user",
            approved_at=datetime.utcnow(),
        ))
        
        # Route the task - should not raise
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orchestrator.route_task(task)
        
        # Verify response indicates denial
        assert result.metadata.get("denied") is True
        assert result.metadata.get("denied_reason") == "Denied for testing"
    
    @pytest.mark.asyncio
    async def test_escalation_tier_enum_values_match_expected_strings(self):
        """Test that EscalationTier enum values match expected strings."""
        assert EscalationTier.LOCAL_UPGRADE.value == "local_upgrade"
        assert EscalationTier.CLOUD.value == "cloud"
    
    @pytest.mark.asyncio
    async def test_cloud_fallback_model_constructor_param_respected_in_escalation_decision_to_model(self, mock_memory_router, mock_state_machine):
        """Test that cloud_fallback_model constructor param is respected in EscalationDecision.to_model."""
        # Create orchestrator with custom cloud_fallback_model
        with patch('core.orchestrator.TaskStateMachine', return_value=mock_state_machine):
            orch = Orchestrator(
                memory_router=mock_memory_router,
                cloud_fallback_model="claude-3-opus",
                approval_gate=None,  # No approval gate for this test
            )
            orch.state_machine = mock_state_machine
        
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orch.register_worker("worker1", mock_worker)
        
        # Create a task
        task = Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.9,
            priority="normal",
            current_state=TaskStatus.RECEIVED,
            created_at=datetime.utcnow(),
        )
        
        # Route the task
        with patch('core.orchestrator.emit_trace', AsyncMock()):
            result = await orch.route_task(task)
        
        # Verify to_model uses custom cloud_fallback_model
        escalation_data = result.metadata["escalation"]
        assert escalation_data["to_model"] == "claude-3-opus"
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_during_escalation_emits_escalation_error_trace_and_returns_error_response(self, orchestrator, task, mock_approval_gate):
        """Test that unexpected exception during escalation emits escalation_error trace and returns error response without raising."""
        # Register a worker with low score
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        orchestrator.register_worker("worker1", mock_worker)
        
        # Mock approval gate to raise exception
        mock_approval_gate.request_approval = AsyncMock(side_effect=Exception("Test exception"))
        
        # Route the task - should not raise
        with patch('core.orchestrator.emit_trace', AsyncMock()) as mock_emit:
            result = await orchestrator.route_task(task)
        
        # Verify error response
        assert "error" in result.metadata
        assert result.metadata["error"] == "Test exception"
        
        # Verify trace event was emitted
        assert mock_emit.called
        # Check for escalation error message
        found_error = False
        for call in mock_emit.call_args_list:
            if "error" in call[1]["message"].lower():
                found_error = True
                break
        assert found_error
