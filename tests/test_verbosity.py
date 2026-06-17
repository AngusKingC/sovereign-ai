"""Tests for core/verbosity.py"""

import pytest

from core.observability import MemoryTraceEmitter, TraceEvent, TraceEventType, TraceComponent, TraceLevel
from core.verbosity import VerbosityLevel, VerbosityManager

pytestmark = pytest.mark.asyncio


class TestVerbosityLevel:
    """Test VerbosityLevel enum values."""

    def test_verbosity_level_enum_values(self) -> None:
        """Verify enum has correct values."""
        assert VerbosityLevel.SILENT.value == "silent"
        assert VerbosityLevel.NORMAL.value == "normal"
        assert VerbosityLevel.VERBOSE.value == "verbose"
        assert VerbosityLevel.DEBUG.value == "debug"


class TestVerbosityManager:
    """Test VerbosityManager class."""

    async def test_default_level_is_normal(self) -> None:
        """Default level should be NORMAL."""
        manager = VerbosityManager()
        assert manager._level == VerbosityLevel.NORMAL

    async def test_set_level_updates_level_and_emits_verbosity_changed(self) -> None:
        """set_level should update level and emit trace event."""
        emitter = MemoryTraceEmitter()
        manager = VerbosityManager(emitter=emitter)
        
        await manager.set_level(VerbosityLevel.VERBOSE)
        
        assert manager._level == VerbosityLevel.VERBOSE
        events = emitter.get_events()
        assert len(events) == 1
        assert events[0].event_type == TraceEventType.VERBOSITY_CHANGED
        assert events[0].component == TraceComponent.VERBOSITY
        assert "verbose" in events[0].message

    async def test_silent_blocks_all_events_including_task_started(self) -> None:
        """SILENT should block all events."""
        manager = VerbosityManager(level=VerbosityLevel.SILENT)
        
        assert not manager.should_emit("orchestrator_routing_start")
        assert not manager.should_emit("orchestrator_routing_complete")
        assert not manager.should_emit("operation_error")
        assert not manager.should_emit("any_event")

    async def test_normal_passes_task_started_blocks_tool_call_start(self) -> None:
        """NORMAL should pass orchestrator_routing_start but block worker_prompt_build."""
        manager = VerbosityManager(level=VerbosityLevel.NORMAL)
        
        assert manager.should_emit("orchestrator_routing_start")
        assert manager.should_emit("orchestrator_routing_complete")
        assert manager.should_emit("operation_error")
        assert manager.should_emit("escalation_triggered")
        
        assert not manager.should_emit("worker_prompt_build")
        assert not manager.should_emit("worker_output_parse")
        assert not manager.should_emit("trace_score_computed")

    async def test_verbose_passes_tool_call_start_blocks_debug_event(self) -> None:
        """VERBOSE should pass worker_prompt_build but block low-level debug events."""
        manager = VerbosityManager(level=VerbosityLevel.VERBOSE)
        
        assert manager.should_emit("orchestrator_routing_start")
        assert manager.should_emit("worker_prompt_build")
        assert manager.should_emit("worker_output_parse")
        assert manager.should_emit("trace_score_computed")
        
        assert not manager.should_emit("debug_internal_operation")
        assert not manager.should_emit("low_level_metric")

    async def test_debug_passes_everything(self) -> None:
        """DEBUG should pass all events."""
        manager = VerbosityManager(level=VerbosityLevel.DEBUG)
        
        assert manager.should_emit("orchestrator_routing_start")
        assert manager.should_emit("worker_prompt_build")
        assert manager.should_emit("debug_internal_operation")
        assert manager.should_emit("any_event")

    async def test_filter_events_returns_only_events_that_pass_should_emit(self) -> None:
        """filter_events should return only events that pass should_emit."""
        emitter = MemoryTraceEmitter()
        manager = VerbosityManager(level=VerbosityLevel.NORMAL, emitter=emitter)
        
        events = [
            TraceEvent(
                event_type=TraceEventType.ORCHESTRATOR_ROUTING_START,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message="task_started",
                data={},
                duration_ms=0,
            ),
            TraceEvent(
                event_type=TraceEventType.WORKER_PROMPT_BUILD,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="tool_call_start",
                data={},
                duration_ms=0,
            ),
        ]
        
        filtered = manager.filter_events(events)
        assert len(filtered) == 1
        assert filtered[0].message == "task_started"

    async def test_filter_events_on_empty_list_returns_empty_list(self) -> None:
        """filter_events on empty list should return empty list."""
        manager = VerbosityManager()
        
        filtered = manager.filter_events([])
        assert filtered == []
