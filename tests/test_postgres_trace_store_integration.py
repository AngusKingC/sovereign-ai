"""Integration tests for Postgres trace store end-to-end flow.

Tests the complete trace emit → store → query pipeline.
"""

import pytest

from memory.postgres_trace_store import PostgresTraceStore
from memory.router import BackendRouter
from core.observability import MemoryTraceEmitter, TraceEvent, TraceEventType, TraceComponent


# Skip condition for Postgres-dependent integration tests
POSTGRES_AVAILABLE = False  # Set to True if Postgres test fixture is available


@pytest.mark.asyncio
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="Postgres test fixture not available in CI environment")
async def test_trace_emit_to_store_e2e():
    """End-to-end test: emit → store → query.
    
    This test verifies the complete pipeline:
    1. Initialize BackendRouter with PostgresTraceStore
    2. Create TraceEmitter with memory_router
    3. Emit a trace event (fire-and-forget)
    4. Await the background task directly for deterministic timing
    5. Query stored traces
    6. Verify event matches
    7. Call trace_store.close() for cleanup
    """
    # Setup
    postgres_dsn = "postgresql://localhost:5432/test_sovereign"
    trace_store = PostgresTraceStore(dsn=postgres_dsn)
    await trace_store.initialize()
    
    router = BackendRouter(trace_store=trace_store)
    emitter = MemoryTraceEmitter(memory_router=router)
    
    # Emit (fire-and-forget; await the stored task handle deterministically
    # rather than guessing with a sleep)
    event = TraceEvent(
        event_type=TraceEventType.OPERATION_START,
        component=TraceComponent.ORCHESTRATOR,
        message="Integration test event",
        data={"key": "value"},
    )
    await emitter.emit(event)
    await emitter._last_trace_task
    
    # Query
    traces = await trace_store.query_traces({"event_type": "operation_start"})
    
    # Verify
    assert len(traces) >= 1
    # Find our specific event by message
    our_trace = next((t for t in traces if t["message"] == "Integration test event"), None)
    assert our_trace is not None
    assert our_trace["data"]["key"] == "value"
    
    # Teardown
    await trace_store.close()


@pytest.mark.asyncio
async def test_trace_emit_with_no_backend_router():
    """Test that TraceEmitter works when BackendRouter has no trace_store.
    
    This verifies graceful degradation when the trace store is not configured.
    """
    # Setup - BackendRouter without trace_store
    router = BackendRouter(trace_store=None)
    emitter = MemoryTraceEmitter(memory_router=router)
    
    # Emit
    event = TraceEvent(
        event_type=TraceEventType.OPERATION_START,
        component=TraceComponent.ORCHESTRATOR,
        message="Test event with no backend",
    )
    await emitter.emit(event)
    
    # Verify - event should still be in memory
    assert emitter.count() == 1
    assert emitter.get_events()[0].message == "Test event with no backend"
