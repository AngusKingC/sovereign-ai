"""Tests for memory scoping functionality."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from core.memory_router import MemoryRouter, ScopedMemoryRouter
from core.observability import MemoryTraceEmitter
from core.schemas import StrategicContext, EscalationDecision, WorkerOutput, Task


class MockMemoryBackend:
    """Mock memory backend for testing."""

    def __init__(self):
        self.storage = []

    async def fetch(self, task: Task) -> list[dict]:
        """Return all stored memory (simplified for testing)."""
        return self.storage.copy()

    async def write(self, data: dict) -> None:
        """Store data in memory."""
        self.storage.append(data)


@pytest.fixture
def mock_backend():
    """Create a mock memory backend."""
    return MockMemoryBackend()


@pytest.fixture
def task():
    """Create a sample task for testing."""
    return Task(
        task_id=uuid4(),
        intent="test_task",
        complexity_score=0.5,
        priority="normal",
        current_state="received",
        created_at=datetime.now(timezone.utc),
    )


class TestScopedMemoryRouter:
    """Tests for ScopedMemoryRouter class."""

    def test_global_scope_prefixes_keys(self, mock_backend, task):
        """Test that global scope prefixes keys with 'global:'."""
        emitter = MemoryTraceEmitter()
        router = MemoryRouter(backends={"mock": mock_backend}, emitter=emitter)
        scoped_router = ScopedMemoryRouter(router, "global", emitter=emitter)

        import asyncio

        asyncio.run(scoped_router.write({"test_key": "test_value"}))

        assert len(mock_backend.storage) == 1
        assert "global:test_key" in mock_backend.storage[0]

    def test_worker_scope_prefixes_keys(self, mock_backend, task):
        """Test that worker scope prefixes keys with 'worker:w1:'."""
        emitter = MemoryTraceEmitter()
        router = MemoryRouter(backends={"mock": mock_backend}, emitter=emitter)
        scoped_router = ScopedMemoryRouter(router, "worker:w1", emitter=emitter)

        import asyncio

        asyncio.run(scoped_router.write({"test_key": "test_value"}))

        assert len(mock_backend.storage) == 1
        assert "worker:w1:test_key" in mock_backend.storage[0]

    def test_fetch_emits_trace_event(self, mock_backend, task):
        """Test that fetch() emits a trace event via the injected emitter."""
        emitter = MemoryTraceEmitter()
        router = MemoryRouter(backends={"mock": mock_backend}, emitter=emitter)
        scoped_router = ScopedMemoryRouter(router, "global", emitter=emitter)

        import asyncio

        asyncio.run(scoped_router.fetch(task))

        events = emitter.get_events()
        assert len(events) > 0

    def test_write_emits_trace_event(self, mock_backend, task):
        """Test that write() emits a trace event via the injected emitter."""
        emitter = MemoryTraceEmitter()
        router = MemoryRouter(backends={"mock": mock_backend}, emitter=emitter)
        scoped_router = ScopedMemoryRouter(router, "global", emitter=emitter)

        import asyncio

        asyncio.run(scoped_router.write({"test_key": "test_value"}))

        events = emitter.get_events()
        assert len(events) > 0

    def test_cross_scope_read_raises_permission_error(self, mock_backend, task):
        """Test that cross-scope read raises PermissionError."""
        emitter = MemoryTraceEmitter()
        router = MemoryRouter(backends={"mock": mock_backend}, emitter=emitter)
        scoped_router = ScopedMemoryRouter(router, "worker:w1", emitter=emitter)

        # Pre-populate backend with data from another worker scope
        mock_backend.storage.append({"worker:w2:test_key": "test_value"})

        import asyncio

        with pytest.raises(PermissionError, match="Cross-scope access denied"):
            asyncio.run(scoped_router.fetch(task))

    def test_global_scope_can_read_any_key(self, mock_backend, task):
        """Test that global scope can read any key without cross-scope restriction."""
        emitter = MemoryTraceEmitter()
        router = MemoryRouter(backends={"mock": mock_backend}, emitter=emitter)
        scoped_router = ScopedMemoryRouter(router, "global", emitter=emitter)

        # Pre-populate backend with data from worker scopes
        mock_backend.storage.append({"worker:w1:test_key": "test_value"})
        mock_backend.storage.append({"worker:w2:test_key": "test_value"})

        import asyncio

        # Should not raise PermissionError
        result = asyncio.run(scoped_router.fetch(task))
        assert len(result) == 2

    def test_different_scopes_do_not_share_key_space(self, mock_backend, task):
        """Test that two ScopedMemoryRouter instances with different scopes do not share key space."""
        emitter1 = MemoryTraceEmitter()
        emitter2 = MemoryTraceEmitter()
        router = MemoryRouter(backends={"mock": mock_backend}, emitter=emitter1)
        scoped_router1 = ScopedMemoryRouter(router, "worker:w1", emitter=emitter1)
        scoped_router2 = ScopedMemoryRouter(router, "worker:w2", emitter=emitter2)

        import asyncio

        asyncio.run(scoped_router1.write({"test_key": "value1"}))
        asyncio.run(scoped_router2.write({"test_key": "value2"}))

        assert len(mock_backend.storage) == 2
        # Both writes should be stored with their respective prefixes
        keys = [list(entry.keys())[0] for entry in mock_backend.storage]
        assert "worker:w1:test_key" in keys
        assert "worker:w2:test_key" in keys


class TestStrategicContext:
    """Tests for StrategicContext schema."""

    def test_strategic_context_validates_correctly(self):
        """Test that StrategicContext validates with all required fields."""
        context = StrategicContext(
            active_goals=["goal1"],
            pending_tasks=[],
            completed_today=["task1"],
            blocked_tasks=[],
            worker_performance={"worker1": 0.9},
            cloud_spend_today=0.0,
            open_questions=["question1"],
            last_updated=datetime.now(timezone.utc),
            escalation_history=[],
        )
        assert context.context_id is not None
        assert len(context.active_goals) == 1
        assert context.cloud_spend_today == 0.0

    def test_strategic_context_cloud_spend_rejects_negative(self):
        """Test that StrategicContext.cloud_spend_today rejects negative values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StrategicContext(
                active_goals=[],
                pending_tasks=[],
                completed_today=[],
                blocked_tasks=[],
                worker_performance={},
                cloud_spend_today=-1.0,  # Invalid
                open_questions=[],
                last_updated=datetime.now(timezone.utc),
                escalation_history=[],
            )

    def test_strategic_context_last_updated_serializes_to_json(self):
        """Test that StrategicContext.last_updated serialises to JSON correctly."""
        context = StrategicContext(
            active_goals=[],
            pending_tasks=[],
            completed_today=[],
            blocked_tasks=[],
            worker_performance={},
            cloud_spend_today=0.0,
            open_questions=[],
            last_updated=datetime(2026, 1, 1, 12, 0, 0),
            escalation_history=[],
        )
        json_data = context.model_dump()
        assert "last_updated" in json_data
        assert json_data["last_updated"] == "2026-01-01T12:00:00"


class TestEscalationDecision:
    """Tests for EscalationDecision schema."""

    def test_escalation_decision_constructs_correctly(self):
        """Test that EscalationDecision constructs with all required fields."""
        decision = EscalationDecision(
            task_id=uuid4(),
            should_escalate=True,
            reasons=["low confidence"],
            suggested_model="gpt-4o",
            estimated_cost=0.5,
        )
        assert decision.should_escalate is True
        assert decision.estimated_cost == 0.5
        assert decision.tier == "cloud"
        assert decision.to_model == ""
        assert decision.metadata == {}

    def test_escalation_decision_estimated_cost_defaults_to_zero(self):
        """Test that EscalationDecision.estimated_cost defaults to 0.0."""
        decision = EscalationDecision(
            task_id=uuid4(),
            should_escalate=True,
            reasons=["low confidence"],
            suggested_model="gpt-4o",
        )
        assert decision.estimated_cost == 0.0


class TestWorkerOutput:
    """Tests for WorkerOutput schema."""

    def test_worker_output_constructs_with_metadata_default(self):
        """Test that WorkerOutput constructs with metadata={} by default."""
        output = WorkerOutput(
            worker_id="worker1",
            task_id=uuid4(),
            content="test content",
            confidence=0.9,
            model_used="gpt-4o",
            tokens_used=100,
        )
        assert output.metadata == {}

    def test_worker_output_accepts_metadata_dict(self):
        """Test that WorkerOutput accepts metadata={"denied": True} without error."""
        output = WorkerOutput(
            worker_id="worker1",
            task_id=uuid4(),
            content="test content",
            confidence=0.9,
            model_used="gpt-4o",
            tokens_used=100,
            metadata={"denied": True},
        )
        assert output.metadata == {"denied": True}


class TestMemoryRouterTraceEvents:
    """Tests for MemoryRouter trace event field names."""

    def test_memory_router_trace_events_use_correct_field_names(self, mock_backend, task):
        """Test that MemoryRouter trace events use correct field names (event_type, component, level, message, data, duration_ms)."""
        emitter = MemoryTraceEmitter()
        router = MemoryRouter(backends={"mock": mock_backend}, emitter=emitter)

        import asyncio

        asyncio.run(router.fetch(task))

        events = emitter.get_events()
        assert len(events) > 0
        # Check that events have the correct TraceEvent schema fields
        for event in events:
            assert hasattr(event, "event_type")
            assert hasattr(event, "component")
            assert hasattr(event, "level")
            assert hasattr(event, "message")
            assert hasattr(event, "data")
            assert hasattr(event, "duration_ms")
            # Check that old schema fields do NOT exist
            assert not hasattr(event, "layer")
            assert not hasattr(event, "payload")
            assert not hasattr(event, "success")
