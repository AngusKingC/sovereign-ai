# Approval Gate Design Document

## Overview
This document defines the approval gate contracts for the Sovereign AI Agent Framework. The approval gate is a security mechanism that requires human authorization before certain high-risk actions can be executed. This design locks in the architectural decisions before implementation in Prompt 14.

## Design Decisions

### 1. On Denial — What Happens to the Task?
**Decision: Fail permanently with user-visible error message**

When an approval request is denied, the task transitions to `FAILED` state with an `ApprovalDeniedError`. The task cannot be retried or returned to `PLANNED` state. This is a hard failure to prevent repeated attempts at unauthorized actions.

**Rationale:**
- Prevents brute-force approval attempts
- Clear audit trail of denied actions
- Forces user to explicitly re-initiate with different parameters if needed
- Aligns with security principle: denied actions should not be automatically retryable

**State Transition:**
```
AWAITING_APPROVAL → FAILED (with ApprovalDeniedError)
```

### 2. On Timeout — What is the Default Behaviour?
**Decision: Auto-deny with configurable timeout duration**

If no response is received within the timeout period, the approval request is automatically denied. The task transitions to `FAILED` state with a `ApprovalTimeoutError`. The default timeout is 5 minutes, but this is configurable per action type.

**Rationale:**
- Security-first: absence of approval = denial
- Prevents indefinite blocking of tasks
- Configurable timeout allows different risk profiles
- Forces user to be present for sensitive operations

**State Transition:**
```
AWAITING_APPROVAL → FAILED (with ApprovalTimeoutError)
```

**Configuration:**
- Default timeout: 300 seconds (5 minutes)
- Per-action-type override: `ApprovalRequest.timeout_seconds`
- Minimum timeout: 30 seconds (prevents abuse)
- Maximum timeout: 3600 seconds (1 hour)

### 3. Who Can Approve — Human Only or Orchestrator Pre-Authorisation?
**Decision: Human-only approval with optional pre-authorisation for low-risk actions**

Approval requests require explicit human approval through CLI, TUI, or Web GUI. The orchestrator cannot pre-authorise actions. However, users can set up "approval scopes" (see section 4) that effectively pre-authorise classes of actions for a session.

**Rationale:**
- Human-in-the-loop for security-critical decisions
- Prevents autonomous escalation of privileges
- Approval scopes provide convenience without compromising security
- Clear audit trail of who approved what

**Approval Sources:**
- CLI: Interactive prompt in terminal
- TUI: Modal dialog in Textual interface
- Web GUI: Approval panel in browser interface
- API: POST to `/api/approvals/{request_id}/approve` (requires authentication)

### 4. Batched Approval Scopes — Can Users Approve a Class of Action for a Session?
**Decision: Yes, session-scoped approval policies are supported**

Users can define approval scopes that pre-authorise classes of actions for the duration of a session. Scopes are time-bound and scope-bound to prevent abuse.

**Supported Scope Types:**
- **File write scope**: "approve all file writes to directory X"
- **Download scope**: "approve all downloads under 4GB"
- **Network scope**: "approve all HTTP requests to domain Y"
- **Command scope**: "approve all shell commands matching pattern Z"

**Scope Constraints:**
- Session-bound: expires when session ends or after timeout
- Size limits: e.g., max 10GB total downloads in scope
- Time limits: e.g., max 1 hour for file write scope
- Revocable: user can revoke scope at any time
- Audit trail: all scope grants and revocations logged

**Scope Schema:**
```python
class ApprovalScope(BaseModel):
    scope_type: Literal["file_write", "download", "network", "command"]
    scope_pattern: str  # e.g., "/tmp/*", "*.example.com", "git *"
    size_limit_mb: int | None = None
    time_limit_seconds: int | None = None
    granted_at: datetime
    expires_at: datetime
    session_id: str
```

**Scope Storage Decision:**
- Runtime scope lookups use an in-memory dict keyed by session_id for fast access
- All scope creates and expiries write through to Postgres immediately for persistence
- On session start, active scopes are loaded from Postgres into the in-memory cache
- On process restart, scopes reload from Postgres automatically to restore state
- This matches the existing SessionManager pattern for consistency across the codebase
- Write-through ensures durability while in-memory cache provides performance

### 5. Expiry Duration — How Long Before an AWAITING_APPROVAL Task Auto-Resolves?
**Decision: 5 minutes default, configurable per action type**

Approval requests expire after 5 minutes of inactivity. This is the same as the timeout behaviour (auto-deny). The expiry is enforced by a background cleanup job that scans for expired requests.

**Rationale:**
- Prevents stale approval requests from accumulating
- Forces timely user attention
- Reduces attack surface for delayed approval attacks
- Configurable for different operational contexts

**Expiry Enforcement:**
- Background job runs every 60 seconds
- Marks expired requests as `EXPIRED` (not `FAILED`)
- Tasks in `AWAITING_APPROVAL` with expired requests transition to `FAILED`

**State Transition:**
```
APPROVAL_REQUEST: PENDING → EXPIRED (after timeout)
TASK: AWAITING_APPROVAL → DENIED (when request expires)
```

### 6. Non-Blocking Guarantee — Approval Must Never Stall Monitor Daemon or Background Jobs
**Decision: Async approval gate with non-blocking task queue**

The approval gate is designed to never block the monitor daemon or background jobs. This is enforced through:

**Architectural Enforcement:**
1. **Async-only design**: All approval operations are async, never blocking
2. **Separate queue**: `AWAITING_APPROVAL` tasks are held in a separate pending queue
3. **Non-blocking monitor**: Monitor daemon continues processing other tasks while waiting for approvals
4. **Timeout protection**: All approval requests have hard timeouts
5. **Background cleanup**: Expired requests are cleaned up asynchronously

**Queue Architecture:**
```
┌─────────────────┐
│  Task Queue     │
│  (Ready tasks)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Orchestrator    │
│  (dispatch)     │
└────────┬────────┘
         │
         ├─→ [No approval needed] → IN_PROGRESS
         │
         └─→ [Approval needed] → AWAITING_APPROVAL
                (held in pending queue)
```

**Monitor Daemon Behaviour:**
- Monitor daemon polls `tasks` table for tasks in `AWAITING_APPROVAL`
- Does not block on approval resolution
- Continues processing other tasks in queue
- Logs pending approvals for visibility

**Background Jobs:**
- Approval expiry cleanup: runs every 60 seconds
- Approval scope cleanup: runs every 300 seconds
- Non-blocking, async execution

## Pydantic Schema Contracts

### ApprovalRequest
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional
from enum import Enum

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
    approved_by: Optional[str] = Field(None, description="Who approved (user ID)")
    approved_at: Optional[datetime] = Field(None, description="When approval was granted")
    denied_reason: Optional[str] = Field(None, description="Reason for denial")
    
    # Scope matching
    matched_scope_id: Optional[str] = Field(None, description="If auto-approved by scope")
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "apr_1234567890",
                "task_id": "task_abc123",
                "session_id": "sess_xyz789",
                "action_type": "file_write",
                "action_description": "Write configuration file to /etc/jarvis/config.yaml",
                "action_parameters": {"path": "/etc/jarvis/config.yaml", "size_bytes": 1024},
                "risk_level": "medium",
                "reason_for_approval": "Writing to system directory requires approval",
                "timeout_seconds": 300,
                "expires_at": "2026-06-09T12:45:00Z",
                "status": "pending"
            }
        }
```

### ApprovalResponse
```python
class ApprovalResponse(BaseModel):
    """Response to an approval request."""
    
    # Identification
    request_id: str = Field(..., description="Request being responded to")
    task_id: str = Field(..., description="Associated task ID")
    
    # Decision
    approved: bool = Field(..., description="Whether the request was approved")
    decision_reason: Optional[str] = Field(None, description="Reason for decision")
    
    # Metadata
    approved_by: str = Field(..., description="User ID who made the decision")
    approved_at: datetime = Field(default_factory=datetime.utcnow, description="When decision was made")
    
    # Scope reference
    scope_id: Optional[str] = Field(None, description="If approved by scope, scope ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "apr_1234567890",
                "task_id": "task_abc123",
                "approved": True,
                "decision_reason": "Approved for testing purposes",
                "approved_by": "user_123",
                "approved_at": "2026-06-09T12:42:30Z"
            }
        }
```

### ApprovalScope
```python
class ApprovalScope(BaseModel):
    """Session-scoped approval policy."""
    
    # Identification
    scope_id: str = Field(..., description="Unique scope identifier")
    session_id: str = Field(..., description="Session this scope applies to")
    
    # Scope definition
    scope_type: Literal["file_write", "download", "network", "command"] = Field(..., description="Type of scope")
    scope_pattern: str = Field(..., description="Pattern matching rule")
    
    # Limits
    size_limit_mb: Optional[int] = Field(None, ge=0, description="Max size in MB")
    time_limit_seconds: Optional[int] = Field(None, ge=0, description="Max duration in seconds")
    
    # Timing
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="When scope was granted")
    expires_at: datetime = Field(..., description="When scope expires")
    
    # Metadata
    granted_by: str = Field(..., description="User who granted the scope")
    is_active: bool = Field(default=True, description="Whether scope is currently active")
    revoked_at: Optional[datetime] = Field(None, description="When scope was revoked")
    revoked_by: Optional[str] = Field(None, description="User who revoked the scope")
    
    class Config:
        json_schema_extra = {
            "example": {
                "scope_id": "scope_abc123",
                "session_id": "sess_xyz789",
                "scope_type": "download",
                "scope_pattern": "*",
                "size_limit_mb": 4096,
                "time_limit_seconds": 3600,
                "granted_at": "2026-06-09T12:40:00Z",
                "expires_at": "2026-06-09T13:40:00Z",
                "granted_by": "user_123",
                "is_active": True
            }
        }
```

## Postgres Table Structure

### approval_requests
```sql
CREATE TABLE approval_requests (
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
    
    matched_scope_id VARCHAR(255),
    
    INDEX idx_task_id (task_id),
    INDEX idx_session_id (session_id),
    INDEX idx_status (status),
    INDEX idx_expires_at (expires_at),
    INDEX idx_created_at (created_at)
);
```

### approval_scopes
```sql
CREATE TABLE approval_scopes (
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
    revoked_by VARCHAR(255),
    
    INDEX idx_session_id (session_id),
    INDEX idx_is_active (is_active),
    INDEX idx_expires_at (expires_at)
);
```

## Integration with TaskStateMachine

### State Transitions Triggered by Approval Gate

The approval gate integrates with TaskStateMachine through the following transitions:

#### 1. Request Approval
**Trigger**: Worker or Orchestrator detects action requiring approval
**Transition**: `IN_PROGRESS` → `AWAITING_APPROVAL`
**Action**: 
- Create `ApprovalRequest` record in Postgres
- Set task status to `AWAITING_APPROVAL`
- Hold task in pending queue
- Emit trace event: `approval_requested`

```python
# Pseudocode (implementation in Prompt 14)
async def request_approval(task_id: Task, action: ApprovalAction) -> None:
    request = ApprovalRequest(
        request_id=generate_id(),
        task_id=task_id,
        action_type=action.type,
        action_description=action.description,
        risk_level=assess_risk(action),
        expires_at=now() + timedelta(seconds=action.timeout_seconds)
    )
    await approval_gate.create_request(request)
    await task_state_machine.transition(task_id, "AWAITING_APPROVAL")
```

#### 2. Approval Granted
**Trigger**: User approves request via CLI/TUI/Web GUI
**Transition**: `AWAITING_APPROVAL` → `IN_PROGRESS`
**Action**:
- Update `ApprovalRequest` status to `approved`
- Record who approved and when
- Resume task execution
- Emit trace event: `approval_granted`

```python
# Pseudocode (implementation in Prompt 14)
async def grant_approval(request_id: str, user_id: str) -> None:
    request = await approval_gate.get_request(request_id)
    response = ApprovalResponse(
        request_id=request_id,
        task_id=request.task_id,
        approved=True,
        approved_by=user_id
    )
    await approval_gate.update_request(request_id, response)
    await task_state_machine.transition(request.task_id, "IN_PROGRESS")
```

#### 3. Approval Denied
**Trigger**: User denies request via CLI/TUI/Web GUI
**Transition**: `AWAITING_APPROVAL` → `DENIED`
**Action**:
- Update `ApprovalRequest` status to `denied`
- Record denial reason
- Transition task to `DENIED` state (terminal state)
- Emit trace event: `approval_denied`

```python
# Pseudocode (implementation in Prompt 14)
async def deny_approval(request_id: str, user_id: str, reason: str) -> None:
    request = await approval_gate.get_request(request_id)
    response = ApprovalResponse(
        request_id=request_id,
        task_id=request.task_id,
        approved=False,
        decision_reason=reason,
        approved_by=user_id
    )
    await approval_gate.update_request(request_id, response)
    await task_state_machine.transition(
        request.task_id, 
        TaskStatus.DENIED,
        reason=f"Approval denied: {reason}",
        actor="approval_gate"
    )
```

#### 4. Approval Expired
**Trigger**: Background cleanup job detects expired request
**Transition**: `AWAITING_APPROVAL` → `DENIED`
**Action**:
- Update `ApprovalRequest` status to `expired`
- Transition task to `DENIED` state (terminal state)
- Emit trace event: `approval_expired`

```python
# Pseudocode (implementation in Prompt 14)
async def expire_request(request_id: str) -> None:
    request = await approval_gate.get_request(request_id)
    await approval_gate.expire_request(request_id)
    await task_state_machine.transition(
        request.task_id,
        TaskStatus.DENIED,
        reason=f"Approval request expired at {request.expires_at}",
        actor="approval_gate"
    )
```

#### 5. Approval Gate Error
**Trigger**: Approval gate itself encounters an error (e.g., database failure)
**Transition**: `AWAITING_APPROVAL` → `FAILED`
**Action**:
- Log error details
- Transition task to `FAILED` state (not `DENIED` - this is a system error, not a user decision)
- Emit trace event: `approval_error`

```python
# Pseudocode (implementation in Prompt 14)
async def handle_approval_error(request_id: str, error: Exception) -> None:
    request = await approval_gate.get_request(request_id)
    await task_state_machine.transition(
        request.task_id,
        TaskStatus.FAILED,
        reason=f"Approval gate error: {str(error)}",
        actor="approval_gate"
    )
```

### TaskStateMachine Integration Points

The TaskStateMachine must be aware of approval states:

```python
# In TaskStateMachine (core/task_state_machine.py)
class TaskState(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"  # NEW STATE
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"  # NEW STATE - terminal state for denied approvals

# Valid transitions
VALID_TRANSITIONS = {
    "PLANNED": ["IN_PROGRESS", "FAILED", "CANCELLED"],
    "IN_PROGRESS": ["COMPLETED", "FAILED", "CANCELLED", "AWAITING_APPROVAL"],  # NEW
    "AWAITING_APPROVAL": ["IN_PROGRESS", "DENIED", "FAILED", "CANCELLED"],  # UPDATED - added DENIED
    "COMPLETED": [],  # Terminal state
    "FAILED": ["PLANNED"],  # Allow retry from failed
    "CANCELLED": [],  # Terminal state
    "DENIED": []  # Terminal state - no retry from denied
}

# Terminal states
TERMINAL_STATES = [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.DENIED]
```

### Trace Events

The approval gate emits the following trace events:

1. **approval_requested**: When an approval request is created
2. **approval_granted**: When an approval is granted
3. **approval_denied**: When an approval is denied
4. **approval_expired**: When an approval request expires
5. **scope_granted**: When an approval scope is granted
6. **scope_revoked**: When an approval scope is revoked

## Security Considerations

### Audit Trail
All approval actions are logged:
- Request creation with full parameters
- Approval/denial decisions with user ID and timestamp
- Scope grants and revocations
- Expiry events

### Access Control
- Only authenticated users can approve requests
- Approval API requires valid session token
- Scope grants are tied to session ID

### Rate Limiting
- Max 10 pending approval requests per session
- Max 1 approval scope grant per minute per session
- Prevents approval spam attacks

### Data Protection
- Approval requests contain sensitive action parameters
- Stored in Postgres with appropriate access controls
- Encrypted at rest (optional, based on deployment)

## Implementation Notes (for Prompt 14)

This design document locks in the contracts. Implementation in Prompt 14 must:

1. Create `core/approval_gate.py` with approval gate logic
2. Create Postgres tables for `approval_requests` and `approval_scopes`
3. Integrate approval gate with TaskStateMachine
4. Add CLI/TUI approval prompts
5. Add Web GUI approval panel (future)
6. Implement background cleanup jobs
7. Add comprehensive tests for all approval flows
8. Update CHANGELOG with implementation details

**No implementation code should be written before this design is reviewed and approved by the user.**
