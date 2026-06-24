"""Tests for the observability layer."""

import pytest
from core.observability import (
    TraceEvent,
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceContext,
    ConsoleTraceEmitter,
    MemoryTraceEmitter,
    set_trace_emitter,
    get_trace_emitter,
    emit_trace,
)


class TestTraceEvent:
    """Tests for TraceEvent model."""
    
    def test_trace_event_creation(self) -> None:
        """Test creating a basic trace event."""
        event = TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Test event",
            level=TraceLevel.INFO,
        )
        
        assert event.event_type == TraceEventType.COMMAND_RECEIVED
        assert event.component == TraceComponent.COMMAND_HANDLER
        assert event.message == "Test event"
        assert event.level == TraceLevel.INFO
        assert event.event_id is not None
        assert event.timestamp is not None
    
    def test_trace_event_with_data(self) -> None:
        """Test creating a trace event with data."""
        event = TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.MEMORY_ROUTER,
            message="Operation completed",
            level=TraceLevel.INFO,
            data={"operation": "read", "key": "test"},
            duration_ms=100,
        )
        
        assert event.data == {"operation": "read", "key": "test"}
        assert event.duration_ms == 100
    
    def test_trace_event_with_error(self) -> None:
        """Test creating a trace event with error information."""
        event = TraceEvent(
            event_type=TraceEventType.OPERATION_ERROR,
            component=TraceComponent.ADAPTER,
            message="Adapter call failed",
            level=TraceLevel.ERROR,
            error_type="ConnectionError",
            error_message="Could not connect to adapter",
            error_stack="Traceback...",
        )
        
        assert event.error_type == "ConnectionError"
        assert event.error_message == "Could not connect to adapter"
        assert event.error_stack == "Traceback..."


class TestTraceContext:
    """Tests for TraceContext model."""
    
    def test_trace_context_creation(self) -> None:
        """Test creating a trace context."""
        context = TraceContext(
            session_id="test-session",
            component=TraceComponent.CLI,
            tags={"environment": "test"},
        )
        
        assert context.session_id == "test-session"
        assert context.component == TraceComponent.CLI
        assert context.tags == {"environment": "test"}
        assert context.correlation_id is not None
    
    def test_trace_context_create_event(self) -> None:
        """Test creating an event from context."""
        context = TraceContext(
            session_id="test-session",
            component=TraceComponent.CLI,
        )
        
        event = context.create_event(
            event_type=TraceEventType.COMMAND_RECEIVED,
            message="Test command",
            level=TraceLevel.INFO,
            data={"command": "test"},
        )
        
        assert event.session_id == "test-session"
        assert event.component == TraceComponent.CLI
        assert event.correlation_id == context.correlation_id
        assert event.message == "Test command"


class TestMemoryTraceEmitter:
    """Tests for MemoryTraceEmitter."""
    
    @pytest.mark.asyncio
    async def test_memory_emitter_emit(self) -> None:
        """Test emitting events to memory."""
        emitter = MemoryTraceEmitter()
        event = TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Test event",
            level=TraceLevel.INFO,
        )
        
        await emitter.emit(event)
        
        assert emitter.count() == 1
        events = emitter.get_events()
        assert len(events) == 1
        assert events[0].message == "Test event"
    
    @pytest.mark.asyncio
    async def test_memory_emitter_filter_by_component(self) -> None:
        """Test filtering events by component."""
        emitter = MemoryTraceEmitter()
        
        await emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.CLI,
            message="CLI event",
            level=TraceLevel.INFO,
        ))
        
        await emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Handler event",
            level=TraceLevel.INFO,
        ))
        
        cli_events = emitter.get_events(component=TraceComponent.CLI)
        assert len(cli_events) == 1
        assert cli_events[0].component == TraceComponent.CLI
    
    @pytest.mark.asyncio
    async def test_memory_emitter_filter_by_level(self) -> None:
        """Test filtering events by level."""
        emitter = MemoryTraceEmitter()
        
        await emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.CLI,
            message="Info event",
            level=TraceLevel.INFO,
        ))
        
        await emitter.emit(TraceEvent(
            event_type=TraceEventType.OPERATION_ERROR,
            component=TraceComponent.CLI,
            message="Error event",
            level=TraceLevel.ERROR,
        ))
        
        error_events = emitter.get_events(level=TraceLevel.ERROR)
        assert len(error_events) == 1
        assert error_events[0].level == TraceLevel.ERROR
    
    @pytest.mark.asyncio
    async def test_memory_emitter_clear(self) -> None:
        """Test clearing events from memory."""
        emitter = MemoryTraceEmitter()
        
        await emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.CLI,
            message="Test event",
            level=TraceLevel.INFO,
        ))
        
        assert emitter.count() == 1
        emitter.clear()
        assert emitter.count() == 0


class TestGlobalEmitter:
    """Tests for global trace emitter."""
    
    @pytest.mark.asyncio
    async def test_get_trace_emitter_default(self) -> None:
        """Test getting default global emitter."""
        # Reset global emitter to None to ensure default behavior
        from core.observability import set_trace_emitter
        set_trace_emitter(None)  # type: ignore[arg-type]
        
        emitter = get_trace_emitter()
        assert isinstance(emitter, ConsoleTraceEmitter)
    
    @pytest.mark.asyncio
    async def test_set_trace_emitter(self) -> None:
        """Test setting global emitter."""
        custom_emitter = MemoryTraceEmitter()
        set_trace_emitter(custom_emitter)
        
        emitter = get_trace_emitter()
        assert isinstance(emitter, MemoryTraceEmitter)
        assert emitter is custom_emitter
        
        # Reset to default
        set_trace_emitter(ConsoleTraceEmitter())
    
    @pytest.mark.asyncio
    async def test_emit_trace(self) -> None:
        """Test emitting trace using global function."""
        memory_emitter = MemoryTraceEmitter()
        set_trace_emitter(memory_emitter)
        
        await emit_trace(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.CLI,
            message="Test trace",
            level=TraceLevel.INFO,
        )
        
        assert memory_emitter.count() == 1
        events = memory_emitter.get_events()
        assert events[0].message == "Test trace"
        
        # Reset to default
        set_trace_emitter(ConsoleTraceEmitter())


class TestConsoleTraceEmitter:
    """Tests for ConsoleTraceEmitter."""
    
    @pytest.mark.asyncio
    async def test_console_emitter_emit(self) -> None:
        """Test emitting to console (should not raise)."""
        emitter = ConsoleTraceEmitter()
        event = TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.CLI,
            message="Test event",
            level=TraceLevel.INFO,
        )
        
        # Should not raise any exceptions
        await emitter.emit(event)

