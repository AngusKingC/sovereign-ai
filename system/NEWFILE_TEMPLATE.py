"""
Template for new system/ layer files.
Copy this file when creating a new system/ module.
Replace all placeholder names with your actual class and method names.
Delete this docstring before committing.

MANDATORY: Read C:\Jarvis\BEFORE_YOU_CODE.md before writing any code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.observability import MemoryTraceEmitter, TraceEvent, TraceEventType, TraceComponent, TraceLevel
from core.schemas import Task  # add other schemas as needed

if TYPE_CHECKING:
    from core.observability import TraceEmitter
    from core.memory_router import MemoryRouter


class NewSystemClass:
    """
    Replace with your class name and docstring.
    system/ layer: may import from core/ and system/ only.
    Never import from adapters/, workers/, cli/, or web/.
    """

    def __init__(
        self,
        memory_router: MemoryRouter,
        # add other dependencies here
        emitter: TraceEmitter | None = None,
    ) -> None:
        self._router = memory_router
        self._emitter = emitter or MemoryTraceEmitter()
        # initialise other state here

    async def example_method(self) -> None:
        """Replace with your actual method."""
        await self._emitter.emit(TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.ORCHESTRATOR,  # use the closest matching component
            level=TraceLevel.INFO,
            message="Example operation completed",
            data={"key": "value"},
            duration_ms=0,
        ))
