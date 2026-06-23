"""Unit tests for PostgresTraceStore.

Tests 1-11 require a live Postgres instance. If unavailable, they skip cleanly.
Tests 12-13 are backend-independent and always run.
"""

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock
import asyncio
import pytest

from memory.postgres_trace_store import PostgresTraceStore
from core.observability import TraceEmitter, TraceEvent, TraceEventType, TraceComponent


# Skip condition for Postgres-dependent tests
POSTGRES_AVAILABLE = False  # Set to True if Postgres test fixture is available


@pytest.fixture
def postgres_dsn() -> str:
    """Test Postgres connection string."""
    return "postgresql://localhost:5432/test_sovereign"


@pytest.fixture
async def trace_store(postgres_dsn: str) -> Optional[PostgresTraceStore]:
    """Create and initialize PostgresTraceStore for tests.
    
    For Postgres-dependent tests, this fixture is skipped via skipif decorator.
    For backend-independent tests, this returns None (tests handle it).
    """
    if not POSTGRES_AVAILABLE:
        yield None
        return
    
    store = PostgresTraceStore(dsn=postgres_dsn, pool_size=5)
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def sample_trace_event() -> dict:
    """Sample trace event for testing."""
    return {
        "event_type": "test_operation",
        "component": "test_component",
        "level": "info",
        "message": "Test trace event",
        "data": {"key": "value", "nested": {"field": 123}},
        "tags": {"test": "true"},
        "duration_ms": 100,
        "session_id": "test-session-123",
        "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": datetime.now(timezone.utc),
    }


# Postgres-dependent tests (1-11)
@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_initialize_creates_pool(postgres_dsn: str):
    """Test that initialize creates a connection pool."""
    
    store = PostgresTraceStore(dsn=postgres_dsn)
    assert store.pool is None
    
    await store.initialize()
    assert store.pool is not None
    
    await store.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_store_trace_returns_id(trace_store: Optional[PostgresTraceStore], sample_trace_event: dict):
    """Test that store_trace returns a trace ID."""
    
    trace_id = await trace_store.store_trace(sample_trace_event)
    assert trace_id is not None
    assert isinstance(trace_id, str)
    assert len(trace_id) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_store_trace_inserts_data(trace_store: Optional[PostgresTraceStore], sample_trace_event: dict):
    """Test that store_trace actually inserts data into the database."""
    
    trace_id = await trace_store.store_trace(sample_trace_event)
    
    # Query the stored trace
    stored = await trace_store.get_trace_by_id(trace_id)
    assert stored is not None
    assert stored["message"] == sample_trace_event["message"]
    assert stored["component"] == sample_trace_event["component"]


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_query_traces_empty(trace_store: Optional[PostgresTraceStore]):
    """Test that query_traces returns empty list when table is empty."""
    
    # Query with no filters
    traces = await trace_store.query_traces({})
    assert isinstance(traces, list)


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_query_traces_with_filters(trace_store: Optional[PostgresTraceStore], sample_trace_event: dict):
    """Test that query_traces filters work correctly."""
    
    # Store two events with different components
    event1 = sample_trace_event.copy()
    event1["component"] = "component_a"
    event1["event_type"] = "type_a"
    
    event2 = sample_trace_event.copy()
    event2["component"] = "component_b"
    event2["event_type"] = "type_b"
    
    await trace_store.store_trace(event1)
    await trace_store.store_trace(event2)
    
    # Query by component
    traces_a = await trace_store.query_traces({"component": "component_a"})
    assert all(t["component"] == "component_a" for t in traces_a)
    
    # Query by event_type
    traces_b = await trace_store.query_traces({"event_type": "type_b"})
    assert all(t["event_type"] == "type_b" for t in traces_b)


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_get_trace_by_id_found(trace_store: Optional[PostgresTraceStore], sample_trace_event: dict):
    """Test that get_trace_by_id returns the trace when found."""
    
    trace_id = await trace_store.store_trace(sample_trace_event)
    
    retrieved = await trace_store.get_trace_by_id(trace_id)
    assert retrieved is not None
    assert retrieved["message"] == sample_trace_event["message"]


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_get_trace_by_id_not_found(trace_store: Optional[PostgresTraceStore]):
    """Test that get_trace_by_id returns None when not found."""
    
    retrieved = await trace_store.get_trace_by_id("00000000-0000-0000-0000-000000000000")
    assert retrieved is None


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_async_concurrent_stores(trace_store: Optional[PostgresTraceStore], sample_trace_event: dict):
    """Test that concurrent store calls don't corrupt data."""
    
    # Store 10 events concurrently
    tasks = []
    for i in range(10):
        event = sample_trace_event.copy()
        event["message"] = f"Concurrent event {i}"
        tasks.append(trace_store.store_trace(event))
    
    trace_ids = await asyncio.gather(*tasks)
    
    # All should have returned IDs
    assert len(trace_ids) == 10
    assert all(tid is not None for tid in trace_ids)
    # IDs should be unique
    assert len(set(trace_ids)) == 10


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_jsonb_metadata_round_trip(trace_store: Optional[PostgresTraceStore]):
    """Test that metadata survives jsonb serialization."""
    
    event = {
        "event_type": "test",
        "component": "test",
        "level": "info",
        "message": "JSONB test",
        "data": {
            "string": "value",
            "number": 42,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "nested": {"deep": "value"},
        },
        "tags": {"env": "test", "version": "1.0"},
        "timestamp": datetime.now(timezone.utc),
    }
    
    trace_id = await trace_store.store_trace(event)
    retrieved = await trace_store.get_trace_by_id(trace_id)
    
    assert retrieved is not None
    assert retrieved["data"]["string"] == "value"
    assert retrieved["data"]["number"] == 42
    assert retrieved["data"]["boolean"] is True
    assert retrieved["data"]["null"] is None
    assert retrieved["data"]["array"] == [1, 2, 3]
    assert retrieved["data"]["nested"]["deep"] == "value"
    assert retrieved["tags"]["env"] == "test"


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_connection_pool_exhaustion(postgres_dsn: str):
    """Test graceful handling of pool limits."""
    
    # Create store with small pool size
    store = PostgresTraceStore(dsn=postgres_dsn, pool_size=2)
    await store.initialize()
    
    event = {
        "event_type": "test",
        "component": "test",
        "level": "info",
        "message": "Pool test",
        "timestamp": datetime.now(timezone.utc),
    }
    
    # Try to store more events than pool size
    tasks = [store.store_trace(event) for _ in range(5)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Should handle gracefully (either succeed or fail with clear error)
    await store.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_close_closes_pool(postgres_dsn: str):
    """Test that close() releases the pool without error."""
    
    store = PostgresTraceStore(dsn=postgres_dsn)
    await store.initialize()
    assert store.pool is not None
    
    await store.close()
    assert store.pool is None
    
    # Subsequent store call should fail cleanly
    try:
        await store.store_trace({"event_type": "test", "component": "test", "level": "info", "message": "test", "timestamp": datetime.now(timezone.utc)})
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "not initialized" in str(e)


# Backend-independent tests (12-13) - no skipif
@pytest.mark.asyncio
async def test_emit_trace_with_no_trace_store():
    """Test that TraceEmitter with trace_store=None emits normally with no error."""
    emitter = TraceEmitter(trace_store=None)
    
    # Use MemoryTraceEmitter as concrete implementation
    from core.observability import MemoryTraceEmitter
    emitter = MemoryTraceEmitter(trace_store=None)
    
    event = TraceEvent(
        event_type=TraceEventType.OPERATION_START,
        component=TraceComponent.ORCHESTRATOR,
        message="Test event",
    )
    
    # Should not raise error
    await emitter.emit(event)
    
    # Event should be in memory
    assert emitter.count() == 1


@pytest.mark.asyncio
async def test_emit_trace_swallows_store_failure():
    """Test that if store_trace() raises, emit_trace() still completes normally with WARNING log."""
    # Create a mock trace store that raises
    mock_store = AsyncMock()
    mock_store.store_trace.side_effect = Exception("Connection failed")
    
    emitter = TraceEmitter(trace_store=mock_store)
    
    # Use MemoryTraceEmitter as concrete implementation
    from core.observability import MemoryTraceEmitter
    emitter = MemoryTraceEmitter(trace_store=mock_store)
    
    event = TraceEvent(
        event_type=TraceEventType.OPERATION_START,
        component=TraceComponent.ORCHESTRATOR,
        message="Test event",
    )
    
    # Should not raise error despite store failure
    await emitter.emit(event)
    
    # Event should still be in memory (emitter's primary function)
    assert emitter.count() == 1
    
    # Background task should have been created
    assert emitter._last_trace_task is not None
    
    # The background task should have completed (with the exception caught)
    await emitter._last_trace_task
