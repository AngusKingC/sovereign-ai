"""Postgres-based trace store for persistent trace event storage.

This module provides a Postgres backend for storing trace events,
using asyncpg for connection pooling and async I/O.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import asyncpg
import logging

logger = logging.getLogger(__name__)


class PostgresTraceStore:
    """Postgres-backed trace store for persistent trace event storage.
    
    This class provides async methods for storing and querying trace events
    in a Postgres database, using connection pooling for production use.
    """

    def __init__(self, dsn: str, pool_size: int = 10) -> None:
        """Initialize the Postgres trace store.
        
        Args:
            dsn: Postgres connection string (e.g., "postgresql://user:pass@host/db")
            pool_size: Maximum number of connections in the pool (default: 10)
        """
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
        self.pool_size = pool_size

    async def initialize(self) -> None:
        """Set up connection pool and schema."""
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            max_size=self.pool_size,
        )
        
        # Create table if not exists
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    timestamp TIMESTAMPTZ NOT NULL,
                    event_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    data JSONB,
                    tags JSONB,
                    duration_ms INTEGER,
                    error_type TEXT,
                    error_message TEXT,
                    error_stack TEXT,
                    session_id TEXT,
                    correlation_id UUID
                );
                
                CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces(timestamp);
                CREATE INDEX IF NOT EXISTS idx_traces_event_type ON traces(event_type);
                CREATE INDEX IF NOT EXISTS idx_traces_component ON traces(component);
                CREATE INDEX IF NOT EXISTS idx_traces_session_id ON traces(session_id);
            """)

    async def close(self) -> None:
        """Close the connection pool cleanly."""
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def store_trace(self, event: Dict[str, Any]) -> str:
        """Store trace event, return trace ID.
        
        Args:
            event: Trace event dictionary with all trace fields
            
        Returns:
            The trace ID (UUID as string)
        """
        if self.pool is None:
            raise RuntimeError("PostgresTraceStore not initialized. Call initialize() first.")
        
        async with self.pool.acquire() as conn:
            trace_id = await conn.fetchval("""
                INSERT INTO traces (
                    timestamp, event_type, component, level, message,
                    data, tags, duration_ms, error_type, error_message,
                    error_stack, session_id, correlation_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id
            """,
                event.get("timestamp", datetime.now(timezone.utc)),
                event.get("event_type"),
                event.get("component"),
                event.get("level"),
                event.get("message"),
                event.get("data", {}),
                event.get("tags", {}),
                event.get("duration_ms"),
                event.get("error_type"),
                event.get("error_message"),
                event.get("error_stack"),
                event.get("session_id"),
                event.get("correlation_id"),
            )
        
        return str(trace_id)

    async def query_traces(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query traces by filters.
        
        Args:
            filters: Dictionary of filter conditions (e.g., event_type, component,
                    timestamp range, session_id, etc.)
            
        Returns:
            List of matching trace events as dictionaries
        """
        if self.pool is None:
            raise RuntimeError("PostgresTraceStore not initialized. Call initialize() first.")
        
        # Build WHERE clause from filters
        conditions = []
        params = []
        param_idx = 1
        
        if "event_type" in filters:
            conditions.append(f"event_type = ${param_idx}")
            params.append(filters["event_type"])
            param_idx += 1
        
        if "component" in filters:
            conditions.append(f"component = ${param_idx}")
            params.append(filters["component"])
            param_idx += 1
        
        if "level" in filters:
            conditions.append(f"level = ${param_idx}")
            params.append(filters["level"])
            param_idx += 1
        
        if "session_id" in filters:
            conditions.append(f"session_id = ${param_idx}")
            params.append(filters["session_id"])
            param_idx += 1
        
        if "timestamp_start" in filters:
            conditions.append(f"timestamp >= ${param_idx}")
            params.append(filters["timestamp_start"])
            param_idx += 1
        
        if "timestamp_end" in filters:
            conditions.append(f"timestamp <= ${param_idx}")
            params.append(filters["timestamp_end"])
            param_idx += 1
        
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT id, timestamp, event_type, component, level, message,
                       data, tags, duration_ms, error_type, error_message,
                       error_stack, session_id, correlation_id
                FROM traces
                WHERE {where_clause}
                ORDER BY timestamp DESC
            """, *params)
        
        return [dict(row) for row in rows]

    async def get_trace_by_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get trace by ID.
        
        Args:
            trace_id: UUID of the trace event
            
        Returns:
            Trace event as dictionary, or None if not found
        """
        if self.pool is None:
            raise RuntimeError("PostgresTraceStore not initialized. Call initialize() first.")
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, timestamp, event_type, component, level, message,
                       data, tags, duration_ms, error_type, error_message,
                       error_stack, session_id, correlation_id
                FROM traces
                WHERE id = $1
            """, trace_id)
        
        return dict(row) if row else None
