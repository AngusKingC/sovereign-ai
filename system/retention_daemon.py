"""
Background daemon for scheduled retention policy enforcement.

Single responsibility: Run RetentionEngine on a configurable schedule as a background task.
"""

import asyncio

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.retention import RetentionEngine, RetentionReport


class RetentionDaemon:
    """Background daemon that runs RetentionEngine on a schedule."""

    def __init__(
        self,
        engine: RetentionEngine,
        interval_seconds: int = 3600,  # default: run hourly
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the retention daemon.
        
        Args:
            engine: The retention engine to run
            interval_seconds: Seconds between runs (default: 3600 = 1 hour)
            emitter: Trace emitter for observability
        """
        self._engine = engine
        self._interval = interval_seconds
        self._emitter = emitter or MemoryTraceEmitter()
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """
        Start the daemon background loop.
        """
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._loop())

        # Emit start event
        try:
            event = TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.RETENTION,
                level=TraceLevel.INFO,
                message="Retention daemon started",
                data={"interval_seconds": self._interval},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Trace failure should not abort start
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.RETENTION_DAEMON,
                level=TraceLevel.WARNING,
                message=f"Trace emission failed: {type(e).__name__}: {e}",
                data={"exception_type": type(e).__name__, "exception_message": str(e)},
                duration_ms=0,
            ))

    async def stop(self) -> None:
        """
        Stop the daemon background loop.
        """
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass  # Expected on cancellation

        # Emit stop event
        try:
            event = TraceEvent(
                event_type=TraceEventType.COMPONENT_STOP,
                component=TraceComponent.RETENTION,
                level=TraceLevel.INFO,
                message="Retention daemon stopped",
                data={},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Trace failure should not abort stop
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.RETENTION_DAEMON,
                level=TraceLevel.WARNING,
                message=f"Trace emission failed: {type(e).__name__}: {e}",
                data={"exception_type": type(e).__name__, "exception_message": str(e)},
                duration_ms=0,
            ))

    async def _loop(self) -> None:
        """
        Background loop that runs retention engine on schedule.
        """
        try:
            while self._running:
                await self._engine.run()
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            # Exit cleanly on cancellation
            pass

    async def run_once(self) -> RetentionReport:
        """
        Run the retention engine once without starting the daemon.
        
        Returns:
            RetentionReport from the run
        """
        return await self._engine.run()
