"""
Data retention and memory housekeeping.

Single responsibility: Enforce configurable TTLs on memory data, archive expired records,
and provide a retention engine for scheduled cleanup operations.
"""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.memory_router import MemoryRouter


class RetentionRule(BaseModel):
    """Rule for data retention policy."""
    scope: str  # "global", "worker:{id}", or "*" for all scopes
    data_type: str  # "task", "trace", "scratchpad", "vector", "note", or "*"
    ttl_seconds: int  # seconds after creation/last_updated before expiry
    archive: bool = True  # if True, archive before delete; if False, hard delete


class RetentionReport(BaseModel):
    """Report from a retention engine run."""
    run_at: datetime
    rules_applied: int
    records_expired: int
    records_archived: int
    records_deleted: int
    errors: list[str] = Field(default_factory=list)


class RetentionEngine:
    """Engine for enforcing data retention policies."""

    def __init__(
        self,
        memory_router: "MemoryRouter",
        rules: list[RetentionRule],
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the retention engine.
        
        Args:
            memory_router: The memory router for data access
            rules: List of retention rules to apply
            emitter: Trace emitter for observability
        """
        self._memory_router = memory_router
        self._rules = rules
        self._emitter = emitter or MemoryTraceEmitter()

    async def run(self) -> RetentionReport:
        """
        Run retention policy enforcement.
        
        Returns:
            RetentionReport with counts and any errors
        """
        report = RetentionReport(
            run_at=datetime.now(timezone.utc),
            rules_applied=0,
            records_expired=0,
            records_archived=0,
            records_deleted=0,
        )

        # Emit start event
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_RUN_STARTED,
                component=TraceComponent.RETENTION,
                level=TraceLevel.INFO,
                message="Retention run started",
                data={"rules_count": len(self._rules)},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass  # Trace failure should not abort run

        for rule in self._rules:
            report.rules_applied += 1

            try:
                # Scan for expired records
                expired_records = await self._scan(rule)
                report.records_expired += len(expired_records)

                # Process each expired record
                for record in expired_records:
                    try:
                        if rule.archive:
                            await self._archive(record)
                            report.records_archived += 1

                        await self._delete(record)
                        report.records_deleted += 1
                    except Exception as e:
                        error_msg = f"Failed to process record {record.get('id', 'unknown')}: {str(e)}"
                        report.errors.append(error_msg)
            except Exception as e:
                error_msg = f"Failed to apply rule {rule.scope}:{rule.data_type}: {str(e)}"
                report.errors.append(error_msg)

        # Emit completion event
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_RUN_COMPLETED,
                component=TraceComponent.RETENTION,
                level=TraceLevel.INFO,
                message="Retention run completed",
                data={
                    "rules_applied": report.rules_applied,
                    "records_expired": report.records_expired,
                    "records_archived": report.records_archived,
                    "records_deleted": report.records_deleted,
                    "errors_count": len(report.errors),
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass  # Trace failure should not abort run

        return report

    async def _scan(self, rule: RetentionRule) -> list[dict[str, Any]]:
        """
        Scan for expired records matching the rule.
        
        Args:
            rule: The retention rule to apply
            
        Returns:
            List of expired record dicts
        """
        # Stub implementation for Phase 10
        # In Phase 10, this will query Postgres/Qdrant directly
        # For now, we'll call memory_router.fetch() and filter in Python
        
        # Create a dummy task for the fetch call
        from core.schemas import Task, TaskPriority
        from uuid import uuid4
        
        dummy_task = Task(
            task_id=uuid4(),
            intent=f"{rule.scope}:{rule.data_type}",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )

        try:
            records = await self._memory_router.fetch(dummy_task)
        except Exception:
            # If fetch fails, return empty list
            return []

        # Filter records older than TTL
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=rule.ttl_seconds)
        expired = []

        for record in records:
            # Check created_at or last_updated
            created_at = record.get("created_at")
            last_updated = record.get("last_updated", created_at)

            timestamp = last_updated if last_updated else created_at

            if timestamp and timestamp < cutoff_time:
                # Ensure record has required fields
                if "id" in record and "scope" in record and "data_type" in record:
                    expired.append(record)

        return expired

    async def _archive(self, record: dict[str, Any]) -> None:
        """
        Archive a record before deletion.
        
        Args:
            record: The record to archive
        """
        archive_key = f"archive:{record['scope']}:{record['data_type']}:{record['id']}"
        
        await self._memory_router.write({"key": archive_key, "data": record})

        # Emit archive event
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_RECORD_ARCHIVED,
                component=TraceComponent.RETENTION,
                level=TraceLevel.INFO,
                message="Record archived",
                data={
                    "record_id": record.get("id"),
                    "scope": record.get("scope"),
                    "data_type": record.get("data_type"),
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass  # Trace failure should not abort run

    async def _delete(self, record: dict[str, Any]) -> None:
        """
        Delete a record from memory.
        
        Args:
            record: The record to delete
        """
        # Stub implementation for Phase 10
        # In Phase 10, this will delete from Postgres/Qdrant
        # For now, we'll write a deletion marker
        
        delete_key = f"deleted:{record['scope']}:{record['data_type']}:{record['id']}"
        
        await self._memory_router.write({"key": delete_key, "deleted": True})

        # Emit delete event
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_RECORD_DELETED,
                component=TraceComponent.RETENTION,
                level=TraceLevel.INFO,
                message="Record deleted",
                data={
                    "record_id": record.get("id"),
                    "scope": record.get("scope"),
                    "data_type": record.get("data_type"),
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass  # Trace failure should not abort run

    async def get_rules(self) -> list[RetentionRule]:
        """
        Get a copy of the current retention rules.
        
        Returns:
            Copy of the rules list
        """
        return list(self._rules)

    async def add_rule(self, rule: RetentionRule) -> None:
        """
        Add a retention rule.
        
        Args:
            rule: The rule to add
        """
        self._rules.append(rule)

        # Emit rule added event
        try:
            event = TraceEvent(
                event_type=TraceEventType.RETENTION_RULE_ADDED,
                component=TraceComponent.RETENTION,
                level=TraceLevel.INFO,
                message="Retention rule added",
                data={
                    "scope": rule.scope,
                    "data_type": rule.data_type,
                    "ttl_seconds": rule.ttl_seconds,
                    "archive": rule.archive,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass  # Trace failure should not abort run
