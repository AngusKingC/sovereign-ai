"""
Tests for escalation flow in Orchestrator.

Tests the full escalation path: decision created → submitted to ApprovalGate → approved → re-routed → denied → task marked DENIED.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

from core.schemas import Task, WorkerOutput, TaskStatus, EscalationDecision, EscalationTier
from core.approval_gate import ApprovalGate, ApprovalResponse
from core.orchestrator import Orchestrator
from core.observability import MemoryTraceEmitter


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
        # Return the task unchanged from transition to preserve task object
        state_machine.transition = AsyncMock(side_effect=lambda task, *args, **kwargs: task)
        state_machine.can_transition = AsyncMock(return_value=True)
        return state_machine
    
    @pytest.fixture
    def mock_approval_gate(self):
        """Create a mock approval gate."""
        gate = AsyncMock(spec=ApprovalGate)
        gate.request_approval = AsyncMock()
        return gate
    
    @pytest.fixture
    def mock_escalation_engine(self):
        """Create a mock escalation engine."""
        engine = AsyncMock()
        engine.evaluate = AsyncMock()
        engine.request_approval = AsyncMock()
        engine.execute_escalation = AsyncMock()
        return engine

    @pytest.fixture
    def orchestrator(self, mock_memory_router, mock_state_machine, mock_approval_gate, mock_escalation_engine):
        """Create an orchestrator with mock dependencies."""
        with patch('core.task_state_machine.TaskStateMachine', return_value=mock_state_machine):
            orch = Orchestrator(
                memory_router=mock_memory_router,
                cloud_fallback_model="gpt-4o",
                approval_gate=mock_approval_gate,
                escalation_engine=mock_escalation_engine,
                emitter=MemoryTraceEmitter(),
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
            created_at=datetime.now(timezone.utc),
        )
    
    @pytest.mark.asyncio
    async def test_escalation_engine_evaluate_called_after_worker_execution(self, orchestrator, task, mock_escalation_engine):
        """Test that EscalationEngine.evaluate() is called after worker execution."""
        # Register a worker
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        mock_worker.run = AsyncMock(return_value=WorkerOutput(
            task_id=task.task_id,
            worker_id="worker1",
            content="Test output",
            confidence=0.3,  # Low confidence to trigger escalation
            model_used="test-model",
            metadata={},
        ))
        orchestrator.register_worker("worker1", mock_worker)
        
        # Configure escalation engine to return escalation decision
        mock_escalation_engine.evaluate = AsyncMock(return_value=EscalationDecision(
            task_id=task.task_id,
            should_escalate=True,
            reasons=["Low confidence"],
            suggested_model="gpt-4o",
            estimated_cost=0.0,
            tier="cloud",
        ))
        
        # Process task
        result = await orchestrator.process_task(task, "worker1")
        
        # Verify evaluate was called
        assert mock_escalation_engine.evaluate.called
        call_args = mock_escalation_engine.evaluate.call_args
        assert call_args[0][0] == task
        assert call_args[0][1].confidence == 0.3

    @pytest.mark.asyncio
    async def test_escalation_not_triggered_when_worker_output_has_high_confidence(self, orchestrator, task, mock_escalation_engine):
        """Test that escalation is not triggered when worker output has high confidence."""
        # Register a worker
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        mock_worker.run = AsyncMock(return_value=WorkerOutput(
            task_id=task.task_id,
            worker_id="worker1",
            content="Test output",
            confidence=0.9,  # High confidence - no escalation
            model_used="test-model",
            metadata={},
        ))
        orchestrator.register_worker("worker1", mock_worker)
        
        # Configure escalation engine to return no escalation
        mock_escalation_engine.evaluate = AsyncMock(return_value=EscalationDecision(
            task_id=task.task_id,
            should_escalate=False,
            reasons=[],
            suggested_model="",
            estimated_cost=0.0,
            tier="local",
        ))
        
        # Process task
        result = await orchestrator.process_task(task, "worker1")
        
        # Verify evaluate was called but request_approval was not
        assert mock_escalation_engine.evaluate.called
        assert not mock_escalation_engine.request_approval.called

    @pytest.mark.asyncio
    async def test_escalation_request_approval_called_when_should_escalate_true(self, orchestrator, task, mock_escalation_engine, mock_approval_gate):
        """Test that request_approval is called when should_escalate is True."""
        # Register a worker
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        mock_worker.run = AsyncMock(return_value=WorkerOutput(
            task_id=task.task_id,
            worker_id="worker1",
            content="Test output",
            confidence=0.3,
            model_used="test-model",
            metadata={},
        ))
        orchestrator.register_worker("worker1", mock_worker)
        
        # Configure escalation engine to return escalation decision
        mock_escalation_engine.evaluate = AsyncMock(return_value=EscalationDecision(
            task_id=task.task_id,
            should_escalate=True,
            reasons=["Low confidence"],
            suggested_model="gpt-4o",
            estimated_cost=0.0,
            tier="cloud",
        ))
        
        # Configure approval gate to approve
        mock_approval_gate.request = AsyncMock(return_value=ApprovalResponse(
            request_id=str(uuid4()),
            task_id=str(task.task_id),
            approved=True,
            decision_reason="Approved for testing",
            approved_by="test_user",
            approved_at=datetime.now(timezone.utc),
        ))
        
        # Process task
        result = await orchestrator.process_task(task, "worker1")
        
        # Verify request_approval was called
        assert mock_escalation_engine.request_approval.called

    @pytest.mark.asyncio
    async def test_escalation_execute_escalation_called_when_approved(self, orchestrator, task, mock_escalation_engine, mock_approval_gate):
        """Test that execute_escalation is called when approval is granted."""
        # Register a worker
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        mock_worker.run = AsyncMock(return_value=WorkerOutput(
            task_id=task.task_id,
            worker_id="worker1",
            content="Test output",
            confidence=0.3,
            model_used="test-model",
            metadata={},
        ))
        orchestrator.register_worker("worker1", mock_worker)
        
        # Configure escalation engine
        mock_escalation_engine.evaluate = AsyncMock(return_value=EscalationDecision(
            task_id=task.task_id,
            should_escalate=True,
            reasons=["Low confidence"],
            suggested_model="gpt-4o",
            estimated_cost=0.0,
            tier="cloud",
        ))
        mock_escalation_engine.request_approval = AsyncMock(return_value=True)
        mock_escalation_engine.execute_escalation = AsyncMock(return_value=WorkerOutput(
            task_id=task.task_id,
            worker_id="cloud",
            content="Escalated output",
            confidence=0.8,
            model_used="gpt-4o",
            metadata={"escalated": True},
        ))
        
        # Process task
        result = await orchestrator.process_task(task, "worker1")
        
        # Verify execute_escalation was called
        assert mock_escalation_engine.execute_escalation.called
        assert result.worker_id == "cloud"

    @pytest.mark.asyncio
    async def test_escalation_denied_sets_metadata_when_approval_denied(self, orchestrator, task, mock_escalation_engine, mock_approval_gate):
        """Test that escalation_denied metadata is set when approval is denied."""
        # Register a worker
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        mock_worker.run = AsyncMock(return_value=WorkerOutput(
            task_id=task.task_id,
            worker_id="worker1",
            content="Test output",
            confidence=0.3,
            model_used="test-model",
            metadata={},
        ))
        orchestrator.register_worker("worker1", mock_worker)
        
        # Configure escalation engine
        mock_escalation_engine.evaluate = AsyncMock(return_value=EscalationDecision(
            task_id=task.task_id,
            should_escalate=True,
            reasons=["Low confidence"],
            suggested_model="gpt-4o",
            estimated_cost=0.0,
            tier="cloud",
        ))
        mock_escalation_engine.request_approval = AsyncMock(return_value=False)
        
        # Process task
        result = await orchestrator.process_task(task, "worker1")
        
        # Verify escalation_denied metadata is set
        assert result.metadata.get("escalation_denied") is True
        assert result.metadata.get("denied_reason") == "User denied escalation"

    @pytest.mark.asyncio
    async def test_escalation_error_does_not_crash_task_processing(self, orchestrator, task, mock_escalation_engine):
        """Test that escalation errors do not crash task processing."""
        # Register a worker
        mock_worker = AsyncMock()
        mock_worker.profile = MagicMock()
        mock_worker.profile.preferred_complexity = 0.5
        mock_worker.profile.capabilities = ["test"]
        mock_worker.profile.status = "active"
        mock_worker.run = AsyncMock(return_value=WorkerOutput(
            task_id=task.task_id,
            worker_id="worker1",
            content="Test output",
            confidence=0.3,
            model_used="test-model",
            metadata={},
        ))
        orchestrator.register_worker("worker1", mock_worker)
        
        # Configure escalation engine to raise exception
        mock_escalation_engine.evaluate = AsyncMock(side_effect=Exception("Test error"))
        
        # Process task - should not raise
        result = await orchestrator.process_task(task, "worker1")
        
        # Should return original worker output
        assert result.worker_id == "worker1"
    
    @pytest.mark.asyncio
    async def test_escalation_tier_enum_values_match_expected_strings(self):
        """Test that EscalationTier enum values match expected strings."""
        assert EscalationTier.LOCAL_UPGRADE.value == "local_upgrade"
        assert EscalationTier.CLOUD.value == "cloud"
