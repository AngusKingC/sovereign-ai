"""Verbosity manager for controlling trace event emission.

This module provides a verbosity manager that gates which trace events
are surfaced based on a configurable level (SILENT, NORMAL, VERBOSE, DEBUG).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from core.observability import (
    MemoryTraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceComponent,
    TraceLevel,
)

if TYPE_CHECKING:
    from core.observability import TraceEmitter


class VerbosityLevel(str, Enum):
    """Verbosity levels for trace event filtering."""
    SILENT = "silent"
    NORMAL = "normal"
    VERBOSE = "verbose"
    DEBUG = "debug"


class VerbosityManager:
    """
    Manages verbosity level for trace event filtering.

    core/ layer: imports only from core/ (observability).
    Constructor-injected emitter pattern per global_rules.md Rule 2.
    """

    def __init__(
        self,
        level: VerbosityLevel = VerbosityLevel.NORMAL,
        emitter: TraceEmitter | None = None,
    ) -> None:
        self._level = level
        self._emitter = emitter or MemoryTraceEmitter()

    async def set_level(self, level: VerbosityLevel) -> None:
        """Update verbosity level and emit trace event."""
        self._level = level
        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.VERBOSITY_CHANGED,
                component=TraceComponent.VERBOSITY,
                level=TraceLevel.INFO,
                message=f"Verbosity level changed to {level.value}",
                data={"new_level": level.value},
                duration_ms=0,
            ))
        except Exception:
            # Don't crash if emitter fails
            pass

    def should_emit(self, event_type: str | TraceEventType) -> bool:
        """
        Returns True if the event passes at the current level.

        SILENT → nothing passes
        NORMAL → passes: orchestrator_routing_start, orchestrator_routing_complete, operation_error, escalation_triggered
        VERBOSE → NORMAL events plus: worker_prompt_build, worker_output_parse, trace_score_computed
        DEBUG → everything passes
        """
        # Convert enum to string if needed
        if isinstance(event_type, TraceEventType):
            event_type = event_type.value

        if self._level == VerbosityLevel.SILENT:
            return False

        if self._level == VerbosityLevel.NORMAL:
            normal_events = {
                "orchestrator_routing_start",
                "orchestrator_routing_complete",
                "operation_error",
                "escalation_triggered",
            }
            return event_type in normal_events

        if self._level == VerbosityLevel.VERBOSE:
            normal_events = {
                "orchestrator_routing_start",
                "orchestrator_routing_complete",
                "operation_error",
                "escalation_triggered",
            }
            verbose_events = {
                "worker_prompt_build",
                "worker_output_parse",
                "trace_score_computed",
            }
            return event_type in normal_events or event_type in verbose_events

        if self._level == VerbosityLevel.DEBUG:
            return True

        return False

    def filter_events(self, events: list[TraceEvent]) -> list[TraceEvent]:
        """Filters a list through should_emit."""
        return [event for event in events if self.should_emit(event.event_type)]
