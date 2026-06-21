"""
Concrete retention layer targeting Postgres trace events, task history, Qdrant vectors, and Obsidian mirror files.

Single responsibility: Provide storage-specific pruning logic for different data types.
Distinct from core/retention.py (generic rule engine stub) — this file contains actual
storage-specific pruning logic with dry-run mode and MonitorDaemon integration hook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.retention import RetentionReport

if TYPE_CHECKING:
    from core.observability import TraceEmitter
    from core.memory_router import MemoryRouter


class RetentionConfig(BaseModel):
    """Configuration for retention manager."""
    trace_events_ttl_days: int = 90
    task_history_ttl_days: int = 365
    keep_worker_ratings: bool = True  # never prune ratings — small table
    qdrant_ttl_days: int = 90
    obsidian_archive_ttl_days: int = 90  # move to /archive/, never delete
    dry_run: bool = False


class RetentionManager:
    """
    Concrete retention layer targeting Postgres trace events, task history, Qdrant vectors,
    and Obsidian mirror files.
    """

    def __init__(
        self,
        memory_router: MemoryRouter,
        config: RetentionConfig | None = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the retention manager.
        
        Args:
            memory_router: The memory router for data access
            config: Retention configuration (uses defaults if None)
            emitter: Trace emitter for observability
        """
        self._memory_router = memory_router
        self._config = config or RetentionConfig()
        self._emitter = emitter or MemoryTraceEmitter()

    async def prune_trace_events(self, dry_run: bool | None = None) -> int:
        """
        Delete trace event records older than config.trace_events_ttl_days.
        
        Args:
            dry_run: If True, count matching records without deleting. If None, use self._config.dry_run.
            
        Returns:
            Number of records pruned (or counted in dry-run mode)
        """
        use_dry_run = dry_run if dry_run is not None else self._config.dry_run
        
        # Stub implementation - actual Postgres query happens in Phase 10
        # For now, we'll call memory router with the operation
        response = await self._memory_router.write({
            "op": "trace_events_prune",
            "older_than_days": self._config.trace_events_ttl_days,
            "dry_run": use_dry_run,
        })
        count = response.get("count", 0) if response else 0

        # Emit trace event per batch (not per record)
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_TRACE_EVENTS_PRUNED,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.INFO,
                message=f"Trace events pruned: {count} records",
                data={
                    "count": count,
                    "dry_run": use_dry_run,
                    "ttl_days": self._config.trace_events_ttl_days,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Trace failure should not abort operation
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.WARNING,
                message=f"Trace emission failed: {type(e).__name__}: {e}",
                data={"exception_type": type(e).__name__, "exception_message": str(e)},
                duration_ms=0,
            ))

        return count

    async def prune_task_history(self, dry_run: bool | None = None) -> int:
        """
        Delete task history records older than config.task_history_ttl_days.
        Never prune tasks in AWAITING_APPROVAL or IN_PROGRESS state.
        
        Args:
            dry_run: If True, count matching records without deleting. If None, use self._config.dry_run.
            
        Returns:
            Number of records pruned (or counted in dry-run mode)
        """
        use_dry_run = dry_run if dry_run is not None else self._config.dry_run
        
        # Stub implementation - actual Postgres query happens in Phase 10
        # For now, we'll call memory router with the operation
        response = await self._memory_router.write({
            "op": "task_history_prune",
            "older_than_days": self._config.task_history_ttl_days,
            "dry_run": use_dry_run,
            "skip_states": ["awaiting_approval", "in_progress"],  # Never prune these
        })
        count = response.get("count", 0) if response else 0

        # Emit trace event per batch (not per record)
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_TASK_HISTORY_PRUNED,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.INFO,
                message=f"Task history pruned: {count} records",
                data={
                    "count": count,
                    "dry_run": use_dry_run,
                    "ttl_days": self._config.task_history_ttl_days,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Trace failure should not abort operation
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.WARNING,
                message=f"Trace emission failed: {type(e).__name__}: {e}",
                data={"exception_type": type(e).__name__, "exception_message": str(e)},
                duration_ms=0,
            ))

        return count

    async def prune_qdrant_vectors(self, dry_run: bool | None = None) -> int:
        """
        Delete Qdrant vector entries older than config.qdrant_ttl_days.
        
        Args:
            dry_run: If True, count matching records without deleting. If None, use self._config.dry_run.
            
        Returns:
            Number of records pruned (or counted in dry-run mode)
        """
        use_dry_run = dry_run if dry_run is not None else self._config.dry_run
        
        # Call memory router with qdrant_prune operation - router handles dispatch
        response = await self._memory_router.write({
            "op": "qdrant_prune",
            "older_than_days": self._config.qdrant_ttl_days,
            "dry_run": use_dry_run,
        })
        count = response.get("count", 0) if response else 0

        # Emit trace event per batch (not per record)
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_QDRANT_PRUNED,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.INFO,
                message=f"Qdrant vectors pruned: {count} records",
                data={
                    "count": count,
                    "dry_run": use_dry_run,
                    "ttl_days": self._config.qdrant_ttl_days,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Trace failure should not abort operation
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.WARNING,
                message=f"Trace emission failed: {type(e).__name__}: {e}",
                data={"exception_type": type(e).__name__, "exception_message": str(e)},
                duration_ms=0,
            ))

        return count

    async def archive_obsidian_notes(self, dry_run: bool | None = None) -> int:
        """
        Move Obsidian daily note files older than config.obsidian_archive_ttl_days to /archive/ subfolder.
        Never delete — archive only.
        
        Args:
            dry_run: If True, count matching records without archiving. If None, use self._config.dry_run.
            
        Returns:
            Number of records archived (or counted in dry-run mode)
        """
        use_dry_run = dry_run if dry_run is not None else self._config.dry_run
        
        # Call memory router with obsidian_archive operation - router handles dispatch
        response = await self._memory_router.write({
            "op": "obsidian_archive",
            "older_than_days": self._config.obsidian_archive_ttl_days,
            "dry_run": use_dry_run,
        })
        count = response.get("count", 0) if response else 0

        # Emit trace event per batch (not per record)
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_OBSIDIAN_ARCHIVED,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.INFO,
                message=f"Obsidian notes archived: {count} records",
                data={
                    "count": count,
                    "dry_run": use_dry_run,
                    "ttl_days": self._config.obsidian_archive_ttl_days,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Trace failure should not abort operation
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.WARNING,
                message=f"Trace emission failed: {type(e).__name__}: {e}",
                data={"exception_type": type(e).__name__, "exception_message": str(e)},
                duration_ms=0,
            ))

        return count

    async def run_all(self, dry_run: bool | None = None) -> RetentionReport:
        """
        Run all four prune methods in order.
        
        Args:
            dry_run: If True, count matching records without deleting/archiving. If None, use self._config.dry_run.
            
        Returns:
            RetentionReport with accumulated counts
        """
        from datetime import datetime
        
        report = RetentionReport(
            run_at=datetime.utcnow(),
            rules_applied=4,
            records_expired=0,
            records_archived=0,
            records_deleted=0,
            errors=[],
        )

        # Emit start event
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_RUN_STARTED,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.INFO,
                message="Retention manager run started",
                data={"dry_run": dry_run if dry_run is not None else self._config.dry_run},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Trace failure should not abort run
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.WARNING,
                message=f"Trace emission failed: {type(e).__name__}: {e}",
                data={"exception_type": type(e).__name__, "exception_message": str(e)},
                duration_ms=0,
            ))

        # Run all four prune methods
        try:
            report.records_deleted += await self.prune_trace_events(dry_run)
        except Exception as e:
            report.errors.append(f"prune_trace_events failed: {str(e)}")

        try:
            report.records_deleted += await self.prune_task_history(dry_run)
        except Exception as e:
            report.errors.append(f"prune_task_history failed: {str(e)}")

        try:
            report.records_deleted += await self.prune_qdrant_vectors(dry_run)
        except Exception as e:
            report.errors.append(f"prune_qdrant_vectors failed: {str(e)}")

        try:
            report.records_archived += await self.archive_obsidian_notes(dry_run)
        except Exception as e:
            report.errors.append(f"archive_obsidian_notes failed: {str(e)}")

        report.records_expired = report.records_deleted + report.records_archived

        # Emit completion event
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_RUN_COMPLETED,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.INFO,
                message="Retention manager run completed",
                data={
                    "records_expired": report.records_expired,
                    "records_archived": report.records_archived,
                    "records_deleted": report.records_deleted,
                    "errors_count": len(report.errors),
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception as e:
            # Trace failure should not abort run
            # Per Rule 17: broad except requires inline comment + WARNING trace
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.RETENTION_MANAGER,
                level=TraceLevel.WARNING,
                message=f"Trace emission failed: {type(e).__name__}: {e}",
                data={"exception_type": type(e).__name__, "exception_message": str(e)},
                duration_ms=0,
            ))

        return report

    async def schedule_hook(self) -> None:
        """
        Entry point for MonitorDaemon to call on schedule.
        Simply calls run_all().
        """
        await self.run_all()
