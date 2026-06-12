"""
PostgreSQL memory backend.

Single responsibility: Handle all async PostgreSQL operations for structured data storage
using asyncpg, following the Layer 0 memory substrate pattern.
"""

import json
import time
from typing import Any

import asyncpg

from core.memory_router import MemoryBackend
from core.schemas import Task
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class PostgresBackend(MemoryBackend):
    """PostgreSQL backend for structured data storage."""

    def __init__(
        self,
        dsn: str = "postgresql://localhost:5432/sovereign",
        table_name: str = "memory_entries",
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the PostgreSQL backend with connection details."""
        self.dsn = dsn
        self.table_name = table_name
        self.pool: asyncpg.Pool | None = None
        self._emitter = emitter or MemoryTraceEmitter()

    async def _ensure_connection(self) -> None:
        """Ensure connection pool is initialized."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(self.dsn)
            await self._initialize_table()

    async def _initialize_table(self) -> None:
        """Create the memory table if it doesn't exist."""
        if self.pool is None:
            raise RuntimeError("Connection pool not initialized")

        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    task_id UUID,
                    content JSONB,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Create index on task_id for faster queries
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_task_id
                ON {self.table_name}(task_id)
            """)

    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """
        Fetch memory relevant to the task from PostgreSQL.

        Returns entries associated with the task_id.
        Returns empty list if connection fails.
        """
        start_time = time.perf_counter()

        try:
            # Emit fetch start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="PostgreSQL memory fetch started",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "postgres",
                        "task_id": str(task.task_id),
                        "table_name": self.table_name,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            await self._ensure_connection()

            if self.pool is None:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.MEMORY_FETCH,
                        component=TraceComponent.MEMORY_ROUTER,
                        message="PostgreSQL memory fetch completed (pool not initialized)",
                        level=TraceLevel.WARNING,
                        data={
                            "backend_type": "postgres",
                            "task_id": str(task.task_id),
                            "records_fetched": 0,
                        },
                        duration_ms=duration_ms,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    pass
                return []

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT content, metadata, created_at
                    FROM {self.table_name}
                    WHERE task_id = $1
                    ORDER BY created_at DESC
                    LIMIT 100
                    """,
                    str(task.task_id),
                )

            result = [
                {
                    "source": "postgres",
                    "content": dict(row["content"]),
                    "metadata": dict(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"].isoformat(),
                }
                for row in rows
            ]

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit fetch complete event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="PostgreSQL memory fetch completed",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "postgres",
                        "task_id": str(task.task_id),
                        "records_fetched": len(result),
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            return result
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="PostgreSQL memory fetch failed",
                    level=TraceLevel.ERROR,
                    data={
                        "backend_type": "postgres",
                        "task_id": str(task.task_id),
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception:
                pass  # Trace failure should not crash main path
            return []

    async def write(self, data: dict[str, Any]) -> None:
        """
        Write data to PostgreSQL.

        Stores the data as JSONB with optional task_id and metadata.
        Silently fails if connection is not available.
        """
        start_time = time.perf_counter()

        try:
            # Emit write start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_WRITE,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="PostgreSQL memory write started",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "postgres",
                        "table_name": self.table_name,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            await self._ensure_connection()

            if self.pool is None:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.MEMORY_WRITE,
                        component=TraceComponent.MEMORY_ROUTER,
                        message="PostgreSQL memory write skipped (pool not initialized)",
                        level=TraceLevel.WARNING,
                        data={
                            "backend_type": "postgres",
                        },
                        duration_ms=duration_ms,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    pass
                return

            task_id = data.get("task_id")
            content = {k: v for k, v in data.items() if k not in ["task_id", "metadata"]}
            metadata = data.get("metadata", {})

            async with self.pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self.table_name} (task_id, content, metadata)
                    VALUES ($1, $2, $3)
                    """,
                    str(task_id) if task_id else None,
                    json.dumps(content),
                    json.dumps(metadata),
                )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit write complete event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_WRITE,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="PostgreSQL memory write completed",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "postgres",
                        "records_written": 1,
                    },
                    duration_ms=duration_ms,
                )
                await self._emitter.emit(event)
            except Exception:
                pass
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_WRITE,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="PostgreSQL memory write failed",
                    level=TraceLevel.ERROR,
                    data={
                        "backend_type": "postgres",
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception:
                pass  # Trace failure should not crash main path
            # Silently fail on connection errors
            pass

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching the given prefix."""
        # Stub implementation - returns empty list for now
        return []

    async def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None

