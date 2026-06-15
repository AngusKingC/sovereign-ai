"""Core observability layer for the Sovereign AI Agent Framework.

This module provides TraceEvent models and observability infrastructure
to ensure all components emit structured events for monitoring, debugging,
and auditing purposes.

Architecture Compliance:
- No global state
- Pydantic models for all data structures
- Async-first event emission
- Typed interfaces
"""

from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4


class TraceLevel(str, Enum):
    """Severity levels for trace events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TraceComponent(str, Enum):
    """Components that can emit trace events."""
    # Core components
    MEMORY_ROUTER = "memory_router"
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    EMBEDDER = "embedder"
    SYSTEM = "system"
    
    # Adapters
    ADAPTER = "adapter"
    ADAPTER_FALLBACK_CHAIN = "adapter_fallback_chain"
    
    # Interfaces
    CLI = "cli"
    WEB_GUI = "web_gui"
    STANDALONE_GUI = "standalone_gui"
    
    # Commands
    COMMAND_REGISTRY = "command_registry"
    COMMAND_HANDLER = "command_handler"

    # Instruction versioning
    INSTRUCTION_VERSIONING = "instruction_versioning"
    TRACE_OPTIMISER = "trace_optimiser"

    # Skills
    GIT_SKILL = "git_skill"
    DOCKER_SKILL = "docker_skill"
    HTTP_CLIENT_SKILL = "http_client_skill"
    PDF_SKILL = "pdf_skill"
    SPREADSHEET_SKILL = "spreadsheet_skill"
    CLIPBOARD_SKILL = "clipboard_skill"
    CALCULATOR_SKILL = "calculator_skill"

    # Approval
    APPROVAL_TRUST = "approval_trust"

    # Multi-worker
    MULTI_WORKER = "multi_worker"

    # A2A
    A2A = "a2a"

    # Retention
    RETENTION = "retention"
    RETENTION_MANAGER = "retention_manager"


class TraceEventType(str, Enum):
    """Types of trace events."""
    # Lifecycle events
    COMPONENT_START = "component_start"
    COMPONENT_STOP = "component_stop"
    
    # Operation events
    OPERATION_START = "operation_start"
    OPERATION_COMPLETE = "operation_complete"
    OPERATION_ERROR = "operation_error"
    
    # Data events
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_TRANSFORM = "data_transform"
    
    # Command events
    COMMAND_RECEIVED = "command_received"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    
    # Adapter events
    ADAPTER_CALL = "adapter_call"
    ADAPTER_RESPONSE = "adapter_response"
    ADAPTER_ERROR = "adapter_error"
    ADAPTER_FALLBACK = "adapter_fallback"
    ADAPTER_UNAVAILABLE = "adapter_unavailable"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"
    
    # Memory events
    MEMORY_ACCESS = "memory_access"
    MEMORY_WRITE = "memory_write"
    MEMORY_FETCH = "memory_fetch"
    
    # Embedder events
    EMBEDDING_REQUEST = "embedding_request"
    EMBEDDING_COMPLETE = "embedding_complete"
    EMBEDDING_ERROR = "embedding_error"
    
    # Approval trust events
    TRUST_GRANTED = "trust_granted"
    TRUST_REVOKED = "trust_revoked"
    TRUST_BLOCKED = "trust_blocked"
    
    # Multi-worker events
    MULTI_WORKER_DISPATCH_STARTED = "multi_worker_dispatch_started"
    MULTI_WORKER_ORCHESTRATOR_MODEL_RELEASED = "multi_worker_orchestrator_model_released"
    MULTI_WORKER_WORKER_FAILED = "multi_worker_worker_failed"
    MULTI_WORKER_WORKER_MODEL_ENSURED = "multi_worker_worker_model_ensured"
    MULTI_WORKER_WORKER_MODEL_RELEASED = "multi_worker_worker_model_released"
    MULTI_WORKER_DISPATCH_COMPLETED = "multi_worker_dispatch_completed"
    MULTI_WORKER_WINNER_SELECTED = "multi_worker_winner_selected"
    
    # Worker events
    WORKER_PROMPT_BUILD = "worker_prompt_build"
    WORKER_OUTPUT_PARSE = "worker_output_parse"
    
    # Orchestrator events
    ORCHESTRATOR_ROUTING_START = "orchestrator_routing_start"
    ORCHESTRATOR_ROUTING_COMPLETE = "orchestrator_routing_complete"
    ORCHESTRATOR_WORKER_REGISTERED = "orchestrator_worker_registered"
    ORCHESTRATOR_WORKER_DEREGISTERED = "orchestrator_worker_deregistered"
    
    # Scratchpad events
    SCRATCHPAD_CREATED = "scratchpad_created"
    SCRATCHPAD_ENTRY_ADDED = "scratchpad_entry_added"
    SCRATCHPAD_COMPACTED = "scratchpad_compacted"
    SCRATCHPAD_DELETED = "scratchpad_deleted"
    
    # System events
    SYSTEM_PROFILING_START = "system_profiling_start"
    SYSTEM_PROFILING_COMPLETE = "system_profiling_complete"
    SYSTEM_PROFILING_ERROR = "system_profiling_error"
    
    # Model registry events
    MODEL_REGISTRY_LOAD = "model_registry_load"
    MODEL_REGISTRY_LOAD_COMPLETE = "model_registry_load_complete"
    MODEL_REGISTRY_REGISTER = "model_registry_register"
    MODEL_REGISTRY_RECOMMEND = "model_registry_recommend"
    MODEL_REGISTRY_DOWNLOAD_UPDATE = "model_registry_download_update"
    
    # Resource manager events
    RESOURCE_SNAPSHOT = "resource_snapshot"
    RESOURCE_LOAD_REQUEST = "resource_load_request"
    RESOURCE_LOAD_APPROVED = "resource_load_approved"
    RESOURCE_LOAD_DENIED = "resource_load_denied"
    RESOURCE_EVICT = "resource_evict"
    RESOURCE_PIN = "resource_pin"
    RESOURCE_UNPIN = "resource_unpin"
    RESOURCE_APPROVAL_REQUESTED = "resource_approval_requested"
    
    # Model acquisition events
    MODEL_SEARCH = "model_search"
    MODEL_METADATA_FETCH = "model_metadata_fetch"
    MODEL_DOWNLOAD_START = "model_download_start"
    MODEL_DOWNLOAD_PROGRESS = "model_download_progress"
    MODEL_DOWNLOAD_COMPLETE = "model_download_complete"
    MODEL_DOWNLOAD_FAILED = "model_download_failed"
    MODEL_DELETE = "model_delete"
    MODEL_ALTERNATIVES_LISTED = "model_alternatives_listed"
    
    # System events
    SYSTEM_STATUS = "system_status"
    RESOURCE_USAGE = "resource_usage"

    # Instruction versioning events
    PROPOSAL_COLLISION_SKIPPED = "proposal_collision_skipped"
    TRACE_SCORE_COMPUTED = "trace_score_computed"
    TRACE_UPDATE_TRIGGERED = "trace_update_triggered"

    # Skill events
    GIT_COMMAND = "git_command"
    DOCKER_COMMAND = "docker_command"
    HTTP_REQUEST = "http_request"
    PDF_OPERATION = "pdf_operation"
    SPREADSHEET_OPERATION = "spreadsheet_operation"
    CLIPBOARD_OPERATION = "clipboard_operation"
    CALCULATOR_OPERATION = "calculator_operation"

    # A2A events
    A2A_SUBMIT_STARTED = "a2a_submit_started"
    A2A_SUBMIT_COMPLETED = "a2a_submit_completed"
    A2A_SUBMIT_FAILED = "a2a_submit_failed"
    A2A_CIRCULAR_DEPENDENCY_DETECTED = "a2a_circular_dependency_detected"
    A2A_CHILDREN_CANCELLED = "a2a_children_cancelled"

    # Retention events
    RETENTION_RUN_STARTED = "retention_run_started"
    RETENTION_RUN_COMPLETED = "retention_run_completed"
    RETENTION_RECORD_ARCHIVED = "retention_record_archived"
    RETENTION_RECORD_DELETED = "retention_record_deleted"
    RETENTION_RULE_ADDED = "retention_rule_added"
    RETENTION_TRACE_EVENTS_PRUNED = "retention_trace_events_pruned"
    RETENTION_TASK_HISTORY_PRUNED = "retention_task_history_pruned"
    RETENTION_QDRANT_PRUNED = "retention_qdrant_pruned"
    RETENTION_OBSIDIAN_ARCHIVED = "retention_obsidian_archived"


class TraceEvent(BaseModel):
    """A single trace event emitted by a component.
    
    This model represents a structured event that can be emitted by any
    component in the system for observability purposes.
    """
    
    # Event identification
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_type: TraceEventType = Field(description="Type of event")
    component: TraceComponent = Field(description="Component that emitted the event")
    level: TraceLevel = Field(default=TraceLevel.INFO, description="Severity level")
    
    # Event metadata
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    correlation_id: Optional[UUID] = Field(default=None, description="Correlation ID for related events")
    
    # Event data
    message: str = Field(description="Human-readable event message")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured event data")
    tags: Dict[str, str] = Field(default_factory=dict, description="Event tags for filtering")
    
    # Performance tracking
    duration_ms: Optional[int] = Field(default=None, description="Operation duration in milliseconds")
    
    # Error information
    error_type: Optional[str] = Field(default=None, description="Error type if this is an error event")
    error_message: Optional[str] = Field(default=None, description="Error message if this is an error event")
    error_stack: Optional[str] = Field(default=None, description="Error stack trace if available")
    
    model_config = ConfigDict(use_enum_values=True)


class TraceContext(BaseModel):
    """Context for trace events.
    
    This context is passed to event emitters to provide consistent
    metadata across related events.
    """
    
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID for related events")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    component: TraceComponent = Field(description="Component emitting events")
    tags: Dict[str, str] = Field(default_factory=dict, description="Default tags for all events")
    
    def create_event(
        self,
        event_type: TraceEventType,
        message: str,
        level: TraceLevel = TraceLevel.INFO,
        data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_stack: Optional[str] = None,
    ) -> TraceEvent:
        """Create a TraceEvent with this context.
        
        Args:
            event_type: Type of event
            message: Human-readable message
            level: Severity level
            data: Structured event data
            duration_ms: Operation duration
            error_type: Error type if error event
            error_message: Error message if error event
            error_stack: Error stack trace if available
            
        Returns:
            Configured TraceEvent
        """
        return TraceEvent(
            event_type=event_type,
            component=self.component,
            level=level,
            session_id=self.session_id,
            correlation_id=self.correlation_id,
            message=message,
            data=data or {},
            tags=self.tags.copy(),
            duration_ms=duration_ms,
            error_type=error_type,
            error_message=error_message,
            error_stack=error_stack,
        )


class TraceEmitter:
    """Interface for trace event emitters.
    
    Components implement this interface to emit trace events.
    """
    
    async def emit(self, event: TraceEvent) -> None:
        """Emit a trace event.
        
        Args:
            event: The trace event to emit
        """
        raise NotImplementedError
    
    async def emit_with_context(
        self,
        context: TraceContext,
        event_type: TraceEventType,
        message: str,
        level: TraceLevel = TraceLevel.INFO,
        data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_stack: Optional[str] = None,
    ) -> None:
        """Emit a trace event with a context.
        
        Args:
            context: Trace context
            event_type: Type of event
            message: Human-readable message
            level: Severity level
            data: Structured event data
            duration_ms: Operation duration
            error_type: Error type if error event
            error_message: Error message if error event
            error_stack: Error stack trace if available
        """
        event = context.create_event(
            event_type=event_type,
            message=message,
            level=level,
            data=data,
            duration_ms=duration_ms,
            error_type=error_type,
            error_message=error_message,
            error_stack=error_stack,
        )
        await self.emit(event)


class ConsoleTraceEmitter(TraceEmitter):
    """Console-based trace emitter for development and CLI.
    
    This emitter writes trace events to stdout/stderr for immediate
    visibility in CLI environments.
    """
    
    async def emit(self, event: TraceEvent) -> None:
        """Emit a trace event to console."""
        # Format: [TIMESTAMP] [LEVEL] [COMPONENT] EVENT_TYPE: message
        timestamp = event.timestamp.isoformat()
        level = str(event.level).upper()
        component = str(event.component)
        event_type = str(event.event_type)
        
        print(f"[{timestamp}] [{level}] [{component}] {event_type}: {event.message}")
        
        if event.data:
            print(f"  Data: {event.data}")
        
        if event.duration_ms:
            print(f"  Duration: {event.duration_ms}ms")
        
        if event.error_type:
            print(f"  Error: {event.error_type}: {event.error_message}")
            if event.error_stack:
                print(f"  Stack: {event.error_stack}")


class MemoryTraceEmitter(TraceEmitter):
    """In-memory trace emitter for testing and short-lived sessions.
    
    This emitter stores trace events in memory for programmatic access.
    """
    
    def __init__(self) -> None:
        """Initialize the memory emitter."""
        self._events: list[TraceEvent] = []
    
    async def emit(self, event: TraceEvent) -> None:
        """Emit a trace event to memory."""
        self._events.append(event)
    
    def get_events(
        self,
        component: Optional[TraceComponent] = None,
        event_type: Optional[TraceEventType] = None,
        level: Optional[TraceLevel] = None,
        limit: Optional[int] = None,
    ) -> list[TraceEvent]:
        """Get stored events with optional filtering.
        
        Args:
            component: Filter by component
            event_type: Filter by event type
            level: Filter by level
            limit: Maximum number of events to return
            
        Returns:
            Filtered list of events
        """
        events = self._events
        
        if component:
            events = [e for e in events if e.component == component]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if level:
            events = [e for e in events if e.level == level]
        
        if limit:
            events = events[-limit:]
        
        return events
    
    def clear(self) -> None:
        """Clear all stored events."""
        self._events.clear()
    
    def count(self) -> int:
        """Get the number of stored events."""
        return len(self._events)


class NullTraceEmitter(TraceEmitter):
    """No-op trace emitter for components that don't need tracing.
    
    This emitter silently absorbs all trace events without any side effects.
    Useful for testing or when tracing is disabled.
    """
    
    async def emit(self, event: TraceEvent) -> None:
        """Silently absorb trace events (no-op)."""
        pass


# Global trace emitter instance
# NOTE: This is a known violation of the "No global state" architecture law.
# Refactoring to dependency injection would require significant changes across
# the codebase. This is documented for future cleanup.
_global_emitter: Optional[TraceEmitter] = None


def get_trace_emitter() -> TraceEmitter:
    """Get the global trace emitter instance.
    
    Returns:
        Global trace emitter (defaults to ConsoleTraceEmitter)
    """
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = ConsoleTraceEmitter()
    return _global_emitter


def set_trace_emitter(emitter: TraceEmitter) -> None:
    """Set the global trace emitter instance.
    
    Args:
        emitter: The trace emitter to use globally
    """
    global _global_emitter
    _global_emitter = emitter


async def emit_trace(
    event_type: TraceEventType,
    component: TraceComponent,
    message: str,
    level: TraceLevel = TraceLevel.INFO,
    data: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
    duration_ms: Optional[int] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    error_stack: Optional[str] = None,
) -> None:
    """Emit a trace event using the global emitter.
    
    Args:
        event_type: Type of event
        component: Component emitting the event
        message: Human-readable message
        level: Severity level
        data: Structured event data
        session_id: Session identifier
        correlation_id: Correlation ID for related events
        duration_ms: Operation duration
        error_type: Error type if error event
        error_message: Error message if error event
        error_stack: Error stack trace if available
    """
    emitter = get_trace_emitter()
    event = TraceEvent(
        event_type=event_type,
        component=component,
        level=level,
        session_id=session_id,
        correlation_id=correlation_id,
        message=message,
        data=data or {},
        duration_ms=duration_ms,
        error_type=error_type,
        error_message=error_message,
        error_stack=error_stack,
    )
    await emitter.emit(event)
