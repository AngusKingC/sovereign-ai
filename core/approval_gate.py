"""
Approval Gate - Human-in-the-loop authorization for high-risk actions.

Single responsibility: Manage approval requests, scopes, and state transitions
for actions requiring human authorization.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from core.observability import (
    TraceComponent,
    TraceEvent,
    TraceEventType,
    TraceLevel,
    TraceEmitter,
)
from core.exceptions import ApprovalDeniedError, WorkerNotFoundError

if TYPE_CHECKING:
    from core.task_state_machine import TaskStateMachine
    from core.memory_router import MemoryRouter
    from core.approval_trust import ApprovalTrustRegistry


class ApprovalActionType(str, Enum):
    """Types of actions requiring approval."""
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    MODEL_DOWNLOAD = "model_download"
    NETWORK_REQUEST = "network_request"
    SHELL_COMMAND = "shell_command"
    SYSTEM_CONFIG = "system_config"
    CLOUD_ESCALATION = "cloud_escalation"


class ApprovalRequest(BaseModel):
    """Request for human approval of an action."""
    
    # Identification
    request_id: str = Field(..., description="Unique request identifier")
    task_id: str = Field(..., description="Associated task ID")
    session_id: str = Field(..., description="Session identifier")
    
    # Action details
    action_type: ApprovalActionType = Field(..., description="Type of action requiring approval")
    action_description: str = Field(..., description="Human-readable description of the action")
    action_parameters: dict = Field(default_factory=dict, description="Action parameters")
    
    # Risk assessment
    risk_level: Literal["low", "medium", "high", "critical"] = Field(..., description="Risk level of the action")
    reason_for_approval: str = Field(..., description="Why this action requires approval")
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When request was created")
    timeout_seconds: int = Field(default=300, ge=30, le=3600, description="Timeout in seconds")
    expires_at: datetime = Field(..., description="When request expires")
    
    # Status
    status: Literal["pending", "approved", "denied", "expired"] = Field(default="pending", description="Request status")
    approved_by: Optional[str] = Field(default=None, description="Who approved (user ID)")
    approved_at: Optional[datetime] = Field(default=None, description="When approval was granted")
    denied_reason: Optional[str] = Field(default=None, description="Reason for denial")
    
    # Scope matching
    matched_scope_id: Optional[str] = Field(default=None, description="If auto-approved by scope")


class ApprovalResponse(BaseModel):
    """Response to an approval request."""
    
    # Identification
    request_id: str = Field(..., description="Request being responded to")
    task_id: str = Field(..., description="Associated task ID")
    
    # Decision
    approved: bool = Field(..., description="Whether the request was approved")
    decision_reason: Optional[str] = Field(default=None, description="Reason for decision")
    
    # Metadata
    approved_by: str = Field(..., description="User ID who made the decision")
    approved_at: datetime = Field(default_factory=datetime.utcnow, description="When decision was made")
    
    # Scope reference
    scope_id: Optional[str] = Field(default=None, description="If approved by scope, scope ID")


class ApprovalScope(BaseModel):
    """Session-scoped approval policy."""
    
    # Identification
    scope_id: str = Field(..., description="Unique scope identifier")
    session_id: str = Field(..., description="Session this scope applies to")
    
    # Scope definition
    scope_type: Literal["file_write", "download", "network", "command"] = Field(..., description="Type of scope")
    scope_pattern: str = Field(..., description="Pattern matching rule")
    
    # Limits
    size_limit_mb: Optional[int] = Field(default=None, ge=0, description="Max size in MB")
    time_limit_seconds: Optional[int] = Field(default=None, ge=0, description="Max duration in seconds")
    
    # Timing
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="When scope was granted")
    expires_at: datetime = Field(..., description="When scope expires")
    
    # Metadata
    granted_by: str = Field(..., description="User who granted the scope")
    is_active: bool = Field(default=True, description="Whether scope is currently active")
    revoked_at: Optional[datetime] = Field(default=None, description="When scope was revoked")
    revoked_by: Optional[str] = Field(default=None, description="User who revoked the scope")


class ApprovalGate:
    """Manages approval requests and session-scoped authorization policies."""
    
    def __init__(
        self,
        state_machine: "TaskStateMachine",
        memory_router: "MemoryRouter",
        emitter: TraceEmitter | None = None,
        trust_registry: "ApprovalTrustRegistry | None" = None,
    ) -> None:
        """Initialize the approval gate.
        
        Args:
            state_machine: TaskStateMachine for state transitions
            memory_router: MemoryRouter for persistence
            emitter: TraceEmitter for observability
            trust_registry: ApprovalTrustRegistry for command trust levels (optional)
        """
        from core.observability import NullTraceEmitter
        
        self.state_machine = state_machine
        self.memory_router = memory_router
        self.emitter = emitter if emitter is not None else NullTraceEmitter()
        self.trust_registry = trust_registry
        
        # In-memory cache for scopes (keyed by session_id)
        self._scope_cache: dict[str, list[ApprovalScope]] = {}
        
        # Pending approval requests (keyed by request_id)
        self._pending_requests: dict[str, ApprovalRequest] = {}
    
    async def _initialize_tables(self) -> None:
        """Create Postgres tables for approval requests and scopes."""
        try:
            # Create approval_requests table
            await self.memory_router.write({
                "content": "",
                "metadata": {
                    "type": "table_creation",
                    "table": "approval_requests",
                    "sql": """
                        CREATE TABLE IF NOT EXISTS approval_requests (
                            request_id VARCHAR(255) PRIMARY KEY,
                            task_id VARCHAR(255) NOT NULL,
                            session_id VARCHAR(255) NOT NULL,
                            
                            action_type VARCHAR(50) NOT NULL,
                            action_description TEXT NOT NULL,
                            action_parameters JSONB DEFAULT '{}',
                            
                            risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
                            reason_for_approval TEXT NOT NULL,
                            
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds >= 30 AND timeout_seconds <= 3600),
                            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                            
                            status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied', 'expired')),
                            approved_by VARCHAR(255),
                            approved_at TIMESTAMP WITH TIME ZONE,
                            denied_reason TEXT,
                            
                            matched_scope_id VARCHAR(255)
                        );
                        
                        CREATE INDEX IF NOT EXISTS idx_approval_requests_task_id ON approval_requests(task_id);
                        CREATE INDEX IF NOT EXISTS idx_approval_requests_session_id ON approval_requests(session_id);
                        CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status);
                        CREATE INDEX IF NOT EXISTS idx_approval_requests_expires_at ON approval_requests(expires_at);
                        CREATE INDEX IF NOT EXISTS idx_approval_requests_created_at ON approval_requests(created_at);
                    """
                }
            })
            
            # Create approval_scopes table
            await self.memory_router.write({
                "content": "",
                "metadata": {
                    "type": "table_creation",
                    "table": "approval_scopes",
                    "sql": """
                        CREATE TABLE IF NOT EXISTS approval_scopes (
                            scope_id VARCHAR(255) PRIMARY KEY,
                            session_id VARCHAR(255) NOT NULL,
                            
                            scope_type VARCHAR(50) NOT NULL CHECK (scope_type IN ('file_write', 'download', 'network', 'command')),
                            scope_pattern VARCHAR(500) NOT NULL,
                            
                            size_limit_mb INTEGER CHECK (size_limit_mb >= 0),
                            time_limit_seconds INTEGER CHECK (time_limit_seconds >= 0),
                            
                            granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                            
                            granted_by VARCHAR(255) NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE,
                            revoked_at TIMESTAMP WITH TIME ZONE,
                            revoked_by VARCHAR(255)
                        );
                        
                        CREATE INDEX IF NOT EXISTS idx_approval_scopes_session_id ON approval_scopes(session_id);
                        CREATE INDEX IF NOT EXISTS idx_approval_scopes_is_active ON approval_scopes(is_active);
                        CREATE INDEX IF NOT EXISTS idx_approval_scopes_expires_at ON approval_scopes(expires_at);
                    """
                }
            })
        except Exception as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    level=TraceLevel.WARNING,
                    component=TraceComponent.ORCHESTRATOR,
                    event_type=TraceEventType.OPERATION_ERROR,
                    message=f"Failed to initialize approval tables: {str(e)}",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
            except Exception as emit_error:
                # Cleanup path — trace emit failure should not crash table initialization
                # Per Rule 17: emit WARNING trace on exception
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trace emit failed during table initialization: {str(emit_error)}",
                        data={"error": str(emit_error)},
                        duration_ms=0,
                    ))
                except Exception:
                    # Nested trace emit failure - don't crash
                    pass
    
    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Request approval for an action.
        
        Args:
            request: The approval request
            
        Returns:
            ApprovalResponse with the decision (may be DENIED if timeout fires)
            
        Raises:
            InvalidStateTransitionError: If task state transition fails
        """
        from core.schemas import Task, TaskStatus
        from core.exceptions import InvalidStateTransitionError
        
        # Check trust registry if available
        if self.trust_registry is not None:
            # Extract command from action_description or action_parameters
            command = request.action_description
            if "command" in request.action_parameters:
                command = request.action_parameters["command"]
            
            try:
                is_trusted = await self.trust_registry.is_trusted(command)
                if is_trusted:
                    # Skip gate, return approved automatically
                    return ApprovalResponse(
                        request_id=request.request_id,
                        task_id=request.task_id,
                        approved=True,
                        decision_reason="Command trusted by trust registry",
                        approved_by="trust_registry",
                    )
            except ApprovalDeniedError:
                # NEVER_ALLOW pattern matched, raise immediately
                raise
            except Exception as trust_error:
                # Cleanup path — trust check failure should not crash approval request
                # Per Rule 17: emit WARNING trace on exception
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trust check failed: {str(trust_error)}",
                        data={"error": str(trust_error)},
                        duration_ms=0,
                    ))
                except Exception:
                    # Nested trace emit failure - don't crash
                    pass
                # Proceed with normal gate logic if trust check fails
        
        # Add to pending queue
        self._pending_requests[request.request_id] = request
        
        # Persist to Postgres
        try:
            await self.memory_router.write({
                "content": request.model_dump_json(),
                "task_id": request.task_id,
                "metadata": {
                    "type": "approval_request",
                    "request_id": request.request_id,
                    "status": request.status,
                }
            })
        except Exception as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.ERROR,
                    message=f"Failed to persist approval request: {str(e)}",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
            except Exception as emit_error:
                # Cleanup path — trace emit failure should not crash approval request
                # Per Rule 17: emit WARNING trace on exception
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trace emit failed during approval request persistence: {str(emit_error)}",
                        data={"error": str(emit_error)},
                        duration_ms=0,
                    ))
                except Exception:
                    # Nested trace emit failure - don't crash
                    pass
        
        # Transition task to AWAITING_APPROVAL
        try:
            # Create a minimal task object for transition
            task = Task(
                task_id=UUID(request.task_id),
                intent=request.action_description,
                complexity_score=0.5,
                priority="normal",  # type: ignore
                current_state=TaskStatus.EXECUTING,
                created_at=request.created_at,
            )
            await self.state_machine.transition(
                task,
                TaskStatus.AWAITING_APPROVAL,
                reason=f"Awaiting approval for {request.action_type.value}",
                actor="approval_gate"
            )
        except InvalidStateTransitionError:
            # Task may already be in AWAITING_APPROVAL or another state
            pass
        except Exception as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.ERROR,
                    message=f"Failed to transition task to AWAITING_APPROVAL: {str(e)}",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
            except Exception as emit_error:
                # Cleanup path — trace emit failure should not crash approval request
                # Per Rule 17: emit WARNING trace on exception
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trace emit failed during task transition: {str(emit_error)}",
                        data={"error": str(emit_error)},
                        duration_ms=0,
                    ))
                except Exception:
                    # Nested trace emit failure - don't crash
                    pass
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message=f"Approval requested for {request.action_type.value}",
                data={
                    "request_id": request.request_id,
                    "task_id": request.task_id,
                    "action_type": request.action_type.value,
                    "risk_level": request.risk_level,
                },
                duration_ms=0,
            ))
        except Exception as emit_error:
            # Cleanup path — trace emit failure should not crash approval request
            # Per Rule 17: emit WARNING trace on exception
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.WARNING,
                    message=f"Trace emit failed during approval request completion: {str(emit_error)}",
                    data={"error": str(emit_error)},
                    duration_ms=0,
                ))
            except Exception:
                # Nested trace emit failure - don't crash
                pass

        # Return pending response (will be resolved later via respond() or timeout)
        return ApprovalResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            approved=False,
            decision_reason="Pending approval",
            approved_by="system",
        )
    
    async def respond(self, request_id: str, approved: bool, responder: str, always_approve: bool = False) -> ApprovalResponse:
        """Respond to a pending approval request.
        
        Args:
            request_id: The request ID to respond to
            approved: Whether the request is approved
            responder: User ID responding to the request
            always_approve: If True and approved, set trust for this command
            
        Returns:
            ApprovalResponse with the decision
            
        Raises:
            WorkerNotFoundError: If request_id not found
            ApprovalDeniedError: If approved is False
            InvalidStateTransitionError: If task state transition fails
        """
        from core.schemas import Task, TaskStatus
        from core.exceptions import InvalidStateTransitionError
        from core.approval_trust import TrustLevel
        
        # Check if request exists
        if request_id not in self._pending_requests:
            raise WorkerNotFoundError(f"Approval request not found: {request_id}")
        
        request = self._pending_requests[request_id]
        
        # Update request status
        if approved:
            request.status = "approved"
            request.approved_by = responder
            request.approved_at = datetime.utcnow()
            
            # Set trust if always_approve is True and trust_registry is available
            if always_approve and self.trust_registry is not None:
                command = request.action_description
                if "command" in request.action_parameters:
                    command = request.action_parameters["command"]
                try:
                    await self.trust_registry.set_trust(command, TrustLevel.PERMANENT_TRUST, scope="permanent")
                except Exception as trust_error:
                    # Cleanup path — trust setting failure should not crash approval response
                    # Per Rule 17: emit WARNING trace on exception
                    try:
                        await self.emitter.emit(TraceEvent(
                            event_id=uuid4(),
                            timestamp=datetime.utcnow(),
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Trust setting failed: {str(trust_error)}",
                            data={"error": str(trust_error)},
                            duration_ms=0,
                        ))
                    except Exception:
                        # Nested trace emit failure - don't crash
                        pass
                    # Trust setting failed, but approval still succeeds
        else:
            request.status = "denied"
            request.approved_by = responder
            request.approved_at = datetime.utcnow()
            request.denied_reason = "Denied by user"
        
        # Persist to Postgres
        try:
            await self.memory_router.write({
                "content": request.model_dump_json(),
                "task_id": request.task_id,
                "metadata": {
                    "type": "approval_request",
                    "request_id": request.request_id,
                    "status": request.status,
                }
            })
        except Exception as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.ERROR,
                    message=f"Failed to persist approval response: {str(e)}",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
            except Exception as emit_error:
                # Cleanup path — trace emit failure should not crash approval response
                # Per Rule 17: emit WARNING trace on exception
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trace emit failed during approval response persistence: {str(emit_error)}",
                        data={"error": str(emit_error)},
                        duration_ms=0,
                    ))
                except Exception:
                    # Nested trace emit failure - don't crash
                    pass
        
        # Create response
        response = ApprovalResponse(
            request_id=request_id,
            task_id=request.task_id,
            approved=approved,
            approved_by=responder,
            approved_at=datetime.utcnow(),
        )
        
        # Transition task state
        try:
            task = Task(
                task_id=UUID(request.task_id),
                intent=request.action_description,
                complexity_score=0.5,
                priority="normal",  # type: ignore
                current_state=TaskStatus.AWAITING_APPROVAL,
                created_at=request.created_at,
            )
            
            if approved:
                await self.state_machine.transition(
                    task,
                    TaskStatus.EXECUTING,
                    reason="Approval granted",
                    actor="approval_gate"
                )
                
                # Emit trace event
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.INFO,
                        message=f"Approval granted by {responder}",
                        data={
                            "request_id": request_id,
                            "task_id": request.task_id,
                            "approved_by": responder,
                        },
                        duration_ms=0,
                    ))
                except Exception as emit_error:
                    # Cleanup path — trace emit failure should not crash approval response
                    # Per Rule 17: emit WARNING trace on exception
                    try:
                        await self.emitter.emit(TraceEvent(
                            event_id=uuid4(),
                            timestamp=datetime.utcnow(),
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Trace emit failed during approval granted trace: {str(emit_error)}",
                            data={"error": str(emit_error)},
                            duration_ms=0,
                        ))
                    except Exception:
                        # Nested trace emit failure - don't crash
                        pass
            else:
                await self.state_machine.transition(
                    task,
                    TaskStatus.DENIED,
                    reason=f"Approval denied by {responder}",
                    actor="approval_gate"
                )
                
                # Emit trace event
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.INFO,
                        message=f"Approval denied by {responder}",
                        data={
                            "request_id": request_id,
                            "task_id": request.task_id,
                            "denied_by": responder,
                        },
                        duration_ms=0,
                    ))
                except Exception as emit_error:
                    # Cleanup path — trace emit failure should not crash approval response
                    # Per Rule 17: emit WARNING trace on exception
                    try:
                        await self.emitter.emit(TraceEvent(
                            event_id=uuid4(),
                            timestamp=datetime.utcnow(),
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Trace emit failed during approval denied trace: {str(emit_error)}",
                            data={"error": str(emit_error)},
                            duration_ms=0,
                        ))
                    except Exception:
                        # Nested trace emit failure - don't crash
                        pass
        except InvalidStateTransitionError:
            # Task may already be in a terminal state
            pass
        except ApprovalDeniedError:
            # Re-raise ApprovalDeniedError
            raise
        except Exception as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.ERROR,
                    message=f"Failed to transition task: {str(e)}",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
            except Exception as emit_error:
                # Cleanup path — trace emit failure should not crash approval response
                # Per Rule 17: emit WARNING trace on exception
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trace emit failed during task transition error: {str(emit_error)}",
                        data={"error": str(emit_error)},
                        duration_ms=0,
                    ))
                except Exception:
                    # Nested trace emit failure - don't crash
                    pass
        
        # Raise error if denied
        if not approved:
            # Remove from pending queue
            del self._pending_requests[request_id]
            raise ApprovalDeniedError(f"Approval denied by {responder}")
        
        return response
    
    async def check_scope(self, session_id: str, action_type: str, parameters: dict) -> bool:
        """Check if a matching scope pre-authorises this action.
        
        Args:
            session_id: Session identifier
            action_type: Type of action (e.g., "file_write")
            parameters: Action parameters
            
        Returns:
            True if a matching scope exists, False otherwise
        """
        if session_id not in self._scope_cache:
            return False
        
        scopes = self._scope_cache[session_id]
        current_time = datetime.utcnow()
        
        for scope in scopes:
            # Check if scope is active and not expired
            if not scope.is_active or scope.expires_at < current_time:
                continue
            
            # Check if scope type matches
            if scope.scope_type != action_type:
                continue
            
            # Simple pattern matching (can be enhanced with glob patterns)
            # For now, we'll do a basic substring match
            if scope.scope_pattern == "*":
                return True
            
            # Check if any parameter value matches the pattern
            for value in parameters.values():
                if isinstance(value, str) and scope.scope_pattern in value:
                    return True
        
        return False
    
    async def add_scope(self, scope: ApprovalScope) -> None:
        """Add a scope to the cache and persist to Postgres.
        
        Args:
            scope: The approval scope to add
        """
        # Add to cache
        if scope.session_id not in self._scope_cache:
            self._scope_cache[scope.session_id] = []
        self._scope_cache[scope.session_id].append(scope)
        
        # Persist to Postgres
        try:
            await self.memory_router.write({
                "content": scope.model_dump_json(),
                "metadata": {
                    "type": "approval_scope",
                    "scope_id": scope.scope_id,
                    "session_id": scope.session_id,
                    "scope_type": scope.scope_type,
                }
            })
        except Exception as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.ERROR,
                    message=f"Failed to persist approval scope: {str(e)}",
                    data={"error": str(e)},
                    duration_ms=0,
                ))
            except Exception as emit_error:
                # Cleanup path — trace emit failure should not crash scope addition
                # Per Rule 17: emit WARNING trace on exception
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trace emit failed during scope addition: {str(emit_error)}",
                        data={"error": str(emit_error)},
                        duration_ms=0,
                    ))
                except Exception:
                    # Nested trace emit failure - don't crash
                    pass
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message=f"Approval scope granted: {scope.scope_id}",
                data={
                    "scope_id": scope.scope_id,
                    "session_id": scope.session_id,
                    "scope_type": scope.scope_type,
                    "granted_by": scope.granted_by,
                },
                duration_ms=0,
            ))
        except Exception as emit_error:
            # Cleanup path — trace emit failure should not crash scope addition
            # Per Rule 17: emit WARNING trace on exception
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.WARNING,
                    message=f"Trace emit failed during scope addition completion: {str(emit_error)}",
                    data={"error": str(emit_error)},
                    duration_ms=0,
                ))
            except Exception:
                # Nested trace emit failure - don't crash
                pass

    async def load_scopes(self, session_id: str) -> None:
        """Load active scopes for a session from Postgres into cache.
        
        Args:
            session_id: Session identifier
        """
        # In a real implementation, this would query Postgres
        # For now, we'll initialize an empty list for the session
        if session_id not in self._scope_cache:
            self._scope_cache[session_id] = []
        
        # TODO: Implement Postgres query to load scopes
        # This would involve querying the approval_scopes table
        # for scopes with matching session_id and is_active=True
        # and expires_at > NOW()
    
    async def expire_pending(self) -> None:
        """Expire pending approval requests that have timed out.
        
        This should be called periodically (e.g., every 60 seconds).
        """
        from core.schemas import Task, TaskStatus
        
        current_time = datetime.utcnow()
        expired_requests = []
        
        # Find expired requests
        for request_id, request in self._pending_requests.items():
            if request.expires_at < current_time:
                expired_requests.append(request_id)
        
        # Process expired requests
        for request_id in expired_requests:
            request = self._pending_requests[request_id]
            
            # Update request status
            request.status = "expired"
            
            # Persist to Postgres
            try:
                await self.memory_router.write({
                    "content": request.model_dump_json(),
                    "task_id": request.task_id,
                    "metadata": {
                        "type": "approval_request",
                        "request_id": request.request_id,
                        "status": request.status,
                    }
                })
            except Exception as e:
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.ERROR,
                        message=f"Failed to persist expired request: {str(e)}",
                        data={"error": str(e)},
                        duration_ms=0,
                    ))
                except Exception as emit_error:
                    # Cleanup path — trace emit failure should not crash expiration processing
                    # Per Rule 17: emit WARNING trace on exception
                    try:
                        await self.emitter.emit(TraceEvent(
                            event_id=uuid4(),
                            timestamp=datetime.utcnow(),
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Trace emit failed during expired request persistence: {str(emit_error)}",
                            data={"error": str(emit_error)},
                            duration_ms=0,
                        ))
                    except Exception:
                        # Nested trace emit failure - don't crash
                        pass
            
            # Transition task to DENIED
            try:
                task = Task(
                    task_id=UUID(request.task_id),
                    intent=request.action_description,
                    complexity_score=0.5,
                    priority="normal",  # type: ignore
                    current_state=TaskStatus.AWAITING_APPROVAL,
                    created_at=request.created_at,
                )
                await self.state_machine.transition(
                    task,
                    TaskStatus.DENIED,
                    reason=f"Approval request expired at {request.expires_at}",
                    actor="approval_gate"
                )
            except Exception as e:
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.ERROR,
                        message=f"Failed to transition expired task: {str(e)}",
                        data={"error": str(e)},
                        duration_ms=0,
                    ))
                except Exception as emit_error:
                    # Cleanup path — trace emit failure should not crash expiration processing
                    # Per Rule 17: emit WARNING trace on exception
                    try:
                        await self.emitter.emit(TraceEvent(
                            event_id=uuid4(),
                            timestamp=datetime.utcnow(),
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.WARNING,
                            message=f"Trace emit failed during expired task transition: {str(emit_error)}",
                            data={"error": str(emit_error)},
                            duration_ms=0,
                        ))
                    except Exception:
                        # Nested trace emit failure - don't crash
                        pass
            
            # Remove from pending queue
            del self._pending_requests[request_id]
            
            # Emit trace event
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.INFO,
                    message=f"Approval request expired: {request_id}",
                    data={
                        "request_id": request_id,
                        "task_id": request.task_id,
                        "expired_at": request.expires_at.isoformat(),
                    },
                    duration_ms=0,
                ))
            except Exception as emit_error:
                # Cleanup path — trace emit failure should not crash expiration processing
                # Per Rule 17: emit WARNING trace on exception
                try:
                    await self.emitter.emit(TraceEvent(
                        event_id=uuid4(),
                        timestamp=datetime.utcnow(),
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.ORCHESTRATOR,
                        level=TraceLevel.WARNING,
                        message=f"Trace emit failed during expired request completion: {str(emit_error)}",
                        data={"error": str(emit_error)},
                        duration_ms=0,
                    ))
                except Exception:
                    # Nested trace emit failure - don't crash
                    pass
