"""Tests for Approval Gate."""

import pytest
from datetime import datetime, timedelta, timezone

from core.approval_gate import (
    ApprovalGate,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalScope,
    ApprovalActionType,
)
from core.observability import MemoryTraceEmitter
from core.exceptions import ApprovalDeniedError, WorkerNotFoundError
from core.approval_trust import ApprovalTrustRegistry, TrustLevel
from core.memory_router import MemoryRouter
from core.task_state_machine import TaskStateMachine


class MockMemoryRouter(MemoryRouter):
    """Mock MemoryRouter for testing."""
    
    def __init__(self) -> None:
        super().__init__()
        self.writes: list[dict] = []
    
    async def write(self, data: dict) -> None:  # type: ignore[override]
        """Mock write."""
        self.writes.append(data)


class MockStateMachine(TaskStateMachine):
    """Mock TaskStateMachine for testing."""
    
    def __init__(self) -> None:
        super().__init__(memory_router=MockMemoryRouter())
        self.transitions: list[dict] = []
    
    async def transition(self, task, to_state, reason=None, actor="system"):  # type: ignore[override]
        """Mock transition."""
        self.transitions.append({
            "task_id": str(task.task_id),
            "from_state": str(task.current_state),
            "to_state": str(to_state),
            "reason": reason,
            "actor": actor,
        })
        task.current_state = to_state
        return task


@pytest.mark.asyncio
class TestApprovalGateSchemas:
    """Tests for approval gate Pydantic schemas."""
    
    async def test_approval_request_schema_validation(self) -> None:
        """Test ApprovalRequest schema validation."""
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.FILE_WRITE,
            action_description="Write config file",
            action_parameters={"path": "/etc/config.yaml"},
            risk_level="medium",
            reason_for_approval="System directory write",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        
        assert request.request_id == "apr_123"
        assert request.task_id == "task_abc"
        assert request.action_type == ApprovalActionType.FILE_WRITE
        assert request.status == "pending"
        assert request.timeout_seconds == 300
    
    async def test_approval_request_timeout_validation(self) -> None:
        """Test ApprovalRequest timeout validation (min 30, max 3600)."""
        # Valid timeout
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.FILE_WRITE,
            action_description="Write config file",
            risk_level="medium",
            reason_for_approval="System directory write",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            timeout_seconds=60,
        )
        assert request.timeout_seconds == 60
    
    async def test_approval_response_schema_validation(self) -> None:
        """Test ApprovalResponse schema validation."""
        response = ApprovalResponse(
            request_id="apr_123",
            task_id="task_abc",
            approved=True,
            approved_by="user_123",
        )
        
        assert response.request_id == "apr_123"
        assert response.approved is True
        assert response.approved_by == "user_123"
        assert response.decision_reason is None
    
    async def test_approval_scope_schema_validation(self) -> None:
        """Test ApprovalScope schema validation."""
        scope = ApprovalScope(
            scope_id="scope_123",
            session_id="sess_xyz",
            scope_type="file_write",
            scope_pattern="/tmp/*",
            size_limit_mb=1024,
            time_limit_seconds=3600,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            granted_by="user_123",
        )
        
        assert scope.scope_id == "scope_123"
        assert scope.scope_type == "file_write"
        assert scope.is_active is True
        assert scope.size_limit_mb == 1024
    
    async def test_approval_action_type_enum_values(self) -> None:
        """Test ApprovalActionType enum has correct values."""
        assert ApprovalActionType.FILE_WRITE.value == "file_write"
        assert ApprovalActionType.FILE_DELETE.value == "file_delete"
        assert ApprovalActionType.MODEL_DOWNLOAD.value == "model_download"
        assert ApprovalActionType.NETWORK_REQUEST.value == "network_request"
        assert ApprovalActionType.SHELL_COMMAND.value == "shell_command"
        assert ApprovalActionType.SYSTEM_CONFIG.value == "system_config"
        assert ApprovalActionType.CLOUD_ESCALATION.value == "cloud_escalation"


@pytest.mark.asyncio
class TestApprovalGate:
    """Tests for ApprovalGate class."""
    
    async def test_request_approval_adds_to_pending_queue(self) -> None:
        """Test request_approval adds request to pending queue."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.FILE_WRITE,
            action_description="Write config file",
            risk_level="medium",
            reason_for_approval="System directory write",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        
        response = await gate.request_approval(request)
        
        assert "apr_123" in gate._pending_requests
        assert gate._pending_requests["apr_123"].status == "pending"
        assert response.approved is False
    
    async def test_request_approval_emits_trace_event(self) -> None:
        """Test request_approval emits trace event."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.FILE_WRITE,
            action_description="Write config file",
            risk_level="medium",
            reason_for_approval="System directory write",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        
        await gate.request_approval(request)
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any("request_id" in event.data for event in events)
    
    async def test_respond_with_approved_true_transitions_to_executing(self) -> None:
        """Test respond with approved=True transitions task to EXECUTING."""
        
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        # Add pending request
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.FILE_WRITE,
            action_description="Write config file",
            risk_level="medium",
            reason_for_approval="System directory write",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        gate._pending_requests["apr_123"] = request
        
        response = await gate.respond("apr_123", approved=True, responder="user_123")
        
        assert response.approved is True
        assert response.approved_by == "user_123"
        assert request.status == "approved"
        # Approved requests remain in pending queue for tracking
    
    async def test_respond_with_approved_false_transitions_to_denied_and_raises_error(self) -> None:
        """Test respond with approved=False transitions to DENIED and raises ApprovalDeniedError."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        # Add pending request
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.FILE_WRITE,
            action_description="Write config file",
            risk_level="medium",
            reason_for_approval="System directory write",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        gate._pending_requests["apr_123"] = request
        
        with pytest.raises(ApprovalDeniedError):
            await gate.respond("apr_123", approved=False, responder="user_123")
        
        assert request.status == "denied"
        assert "apr_123" not in gate._pending_requests
    
    async def test_respond_with_unknown_request_id_raises_worker_not_found_error(self) -> None:
        """Test respond with unknown request_id raises WorkerNotFoundError."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        with pytest.raises(WorkerNotFoundError):
            await gate.respond("unknown_id", approved=True, responder="user_123")
    
    async def test_timeout_auto_denies_pending_request(self) -> None:
        """Test expire_pending auto-denies timed-out requests."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        # Add expired request
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.FILE_WRITE,
            action_description="Write config file",
            risk_level="medium",
            reason_for_approval="System directory write",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),  # Expired
        )
        gate._pending_requests["apr_123"] = request
        
        await gate.expire_pending()
        
        assert request.status == "expired"
        assert "apr_123" not in gate._pending_requests
    
    async def test_check_scope_returns_true_when_matching_scope_exists(self) -> None:
        """Test check_scope returns True when matching scope exists."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        # Add scope
        scope = ApprovalScope(
            scope_id="scope_123",
            session_id="sess_xyz",
            scope_type="file_write",
            scope_pattern="/tmp/",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            granted_by="user_123",
        )
        gate._scope_cache["sess_xyz"] = [scope]
        
        result = await gate.check_scope("sess_xyz", "file_write", {"path": "/tmp/test.txt"})
        
        assert result is True
    
    async def test_check_scope_returns_false_when_no_scope_exists(self) -> None:
        """Test check_scope returns False when no scope exists."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        result = await gate.check_scope("sess_xyz", "file_write", {"path": "/tmp/test.txt"})
        
        assert result is False
    
    async def test_check_scope_returns_false_when_scope_type_mismatch(self) -> None:
        """Test check_scope returns False when scope type doesn't match."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        # Add scope for download
        scope = ApprovalScope(
            scope_id="scope_123",
            session_id="sess_xyz",
            scope_type="download",
            scope_pattern="*",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            granted_by="user_123",
        )
        gate._scope_cache["sess_xyz"] = [scope]
        
        result = await gate.check_scope("sess_xyz", "file_write", {"path": "/tmp/test.txt"})
        
        assert result is False
    
    async def test_add_scope_writes_to_cache_and_postgres(self) -> None:
        """Test add_scope writes to cache and Postgres."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        scope = ApprovalScope(
            scope_id="scope_123",
            session_id="sess_xyz",
            scope_type="file_write",
            scope_pattern="/tmp/*",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            granted_by="user_123",
        )
        
        await gate.add_scope(scope)
        
        assert "sess_xyz" in gate._scope_cache
        assert len(gate._scope_cache["sess_xyz"]) == 1
        assert gate._scope_cache["sess_xyz"][0].scope_id == "scope_123"
        assert len(mock_router.writes) > 0
    
    async def test_load_scopes_initializes_cache_for_session(self) -> None:
        """Test load_scopes initializes cache for session."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        await gate.load_scopes("sess_xyz")
        
        assert "sess_xyz" in gate._scope_cache
        assert isinstance(gate._scope_cache["sess_xyz"], list)
    
    async def test_check_scope_returns_false_when_scope_expired(self) -> None:
        """Test check_scope returns False when scope is expired."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        # Add expired scope
        scope = ApprovalScope(
            scope_id="scope_123",
            session_id="sess_xyz",
            scope_type="file_write",
            scope_pattern="/tmp/*",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            granted_by="user_123",
        )
        gate._scope_cache["sess_xyz"] = [scope]
        
        result = await gate.check_scope("sess_xyz", "file_write", {"path": "/tmp/test.txt"})
        
        assert result is False
    
    async def test_check_scope_returns_false_when_scope_inactive(self) -> None:
        """Test check_scope returns False when scope is inactive."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        # Add inactive scope
        scope = ApprovalScope(
            scope_id="scope_123",
            session_id="sess_xyz",
            scope_type="file_write",
            scope_pattern="/tmp/*",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            granted_by="user_123",
            is_active=False,
        )
        gate._scope_cache["sess_xyz"] = [scope]
        
        result = await gate.check_scope("sess_xyz", "file_write", {"path": "/tmp/test.txt"})
        
        assert result is False
    
    async def test_add_scope_emits_trace_event(self) -> None:
        """Test add_scope emits trace event."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        
        gate = ApprovalGate(mock_state_machine, mock_router, emitter)
        
        scope = ApprovalScope(
            scope_id="scope_123",
            session_id="sess_xyz",
            scope_type="file_write",
            scope_pattern="/tmp/",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            granted_by="user_123",
        )
        
        await gate.add_scope(scope)
        
        events = emitter.get_events()
        assert len(events) > 0
        assert any("scope_id" in event.data for event in events)

    async def test_approval_gate_skips_gate_when_command_is_trusted(self) -> None:
        """Test gate returns approved without prompting when trust_registry says trusted."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        trust_emitter = MemoryTraceEmitter()
        
        # Create trust registry and set a trusted command
        trust_registry = ApprovalTrustRegistry(memory_router=None, emitter=trust_emitter)
        await trust_registry.set_trust("git status", TrustLevel.PERMANENT_TRUST, scope="permanent")
        
        # Create gate with trust registry
        gate = ApprovalGate(mock_state_machine, mock_router, emitter, trust_registry=trust_registry)
        
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.SHELL_COMMAND,
            action_description="git status",
            action_parameters={"command": "git status"},
            risk_level="low",
            reason_for_approval="Git command",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        
        response = await gate.request_approval(request)
        
        # Should return approved immediately without adding to pending queue
        assert response.approved is True
        assert response.approved_by == "trust_registry"
        assert "apr_123" not in gate._pending_requests

    async def test_approval_gate_raises_on_never_allow(self) -> None:
        """Test gate raises ApprovalDeniedError when trust_registry returns NEVER_ALLOW."""
        mock_router = MockMemoryRouter()
        mock_state_machine = MockStateMachine()
        emitter = MemoryTraceEmitter()
        trust_emitter = MemoryTraceEmitter()
        
        # Create trust registry
        trust_registry = ApprovalTrustRegistry(memory_router=None, emitter=trust_emitter)
        
        # Create gate with trust registry
        gate = ApprovalGate(mock_state_machine, mock_router, emitter, trust_registry=trust_registry)
        
        request = ApprovalRequest(
            request_id="apr_123",
            task_id="task_abc",
            session_id="sess_xyz",
            action_type=ApprovalActionType.SHELL_COMMAND,
            action_description="rm -rf /",
            action_parameters={"command": "rm -rf /"},
            risk_level="critical",
            reason_for_approval="Dangerous command",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        
        # Should raise ApprovalDeniedError immediately
        with pytest.raises(ApprovalDeniedError):
            await gate.request_approval(request)
        
        # Should not add to pending queue
        assert "apr_123" not in gate._pending_requests
