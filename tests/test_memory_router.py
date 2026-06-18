"""
Memory router tests.

Single responsibility: Test memory routing logic, access control enforcement,
and backend selection for various data types and operations.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.memory_router import MemoryBackend, MemoryRouter
from core.schemas import Task, TaskPriority
from core.observability import MemoryTraceEmitter, TraceEventType


class MockMemoryBackend(MemoryBackend):
    """Mock memory backend for testing."""

    def __init__(self) -> None:
        self.storage: list[dict[str, Any]] = []

    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """Fetch memory - returns mock data."""
        return [{"content": f"Memory for {task.intent}", "source": "mock"}]

    async def write(self, data: dict[str, Any]) -> None:
        """Write data to storage."""
        self.storage.append(data)

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching the given prefix."""
        # Stub implementation - returns empty list for now
        return []


class TestMemoryBackend:
    """Test MemoryBackend abstract interface."""

    def test_backend_requires_fetch_implementation(self):
        """Test that backends must implement fetch."""
        class IncompleteBackend(MemoryBackend):
            async def write(self, data: dict[str, Any]) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteBackend()

    def test_backend_requires_write_implementation(self):
        """Test that backends must implement write."""
        class IncompleteBackend(MemoryBackend):
            async def fetch(self, task: Task) -> list[dict[str, Any]]:
                return []

        with pytest.raises(TypeError):
            IncompleteBackend()


class TestMemoryRouter:
    """Test MemoryRouter functionality."""

    @pytest.fixture
    def trace_emitter(self):
        """Create a memory trace emitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def mock_backend(self):
        """Create a mock memory backend."""
        return MockMemoryBackend()

    @pytest.fixture
    def sample_task(self):
        """Create a sample task for testing."""
        return Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

    def test_memory_router_initialization(self, mock_backend):
        """Test memory router initializes with backends."""
        router = MemoryRouter(
            backends={"mock": mock_backend},
        )
        assert router.backends == {"mock": mock_backend}

    def test_fetch_from_single_backend(self, mock_backend, sample_task):
        """Test fetching memory from a single backend."""
        router = MemoryRouter(
            backends={"mock": mock_backend},
        )

        import asyncio

        memory = asyncio.run(router.fetch(sample_task))

        assert len(memory) == 1
        assert memory[0]["content"] == f"Memory for {sample_task.intent}"

    def test_fetch_from_multiple_backends(self, sample_task):
        """Test fetching memory from multiple backends."""
        backend1 = MockMemoryBackend()
        backend2 = MockMemoryBackend()

        router = MemoryRouter(
            backends={"backend1": backend1, "backend2": backend2},
        )

        import asyncio

        memory = asyncio.run(router.fetch(sample_task))

        assert len(memory) == 2  # One from each backend

    def test_write_to_single_backend(self, mock_backend):
        """Test writing data to a single backend."""
        router = MemoryRouter(
            backends={"mock": mock_backend},
        )

        import asyncio

        data = {"content": "test data", "id": str(uuid4())}
        asyncio.run(router.write(data, backend_name="mock"))

        assert len(mock_backend.storage) == 1
        assert mock_backend.storage[0]["content"] == "test data"

    def test_write_to_all_backends(self):
        """Test writing data to all backends."""
        backend1 = MockMemoryBackend()
        backend2 = MockMemoryBackend()

        router = MemoryRouter(
            backends={"backend1": backend1, "backend2": backend2},
        )

        import asyncio

        data = {"content": "test data", "id": str(uuid4())}
        asyncio.run(router.write(data))

        assert len(backend1.storage) == 1
        assert len(backend2.storage) == 1

    def test_tracing_on_fetch(self, trace_emitter, mock_backend, sample_task):
        """Test that fetch operations emit trace events."""
        router = MemoryRouter(
            backends={"mock": mock_backend},
            emitter=trace_emitter,
        )

        import asyncio

        asyncio.run(router.fetch(sample_task))

        events = trace_emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.MEMORY_FETCH for event in events)

    def test_tracing_on_write(self, trace_emitter, mock_backend):
        """Test that write operations emit trace events."""
        router = MemoryRouter(
            backends={"mock": mock_backend},
            emitter=trace_emitter,
        )

        import asyncio

        data = {"content": "test data", "id": str(uuid4())}
        asyncio.run(router.write(data))

        events = trace_emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.MEMORY_WRITE for event in events)

    def test_postgres_backend_parameter(self, mock_backend):
        """Test that postgres_backend parameter is accepted and converted to backends dict."""
        router = MemoryRouter(
            backends={},
            postgres_backend=mock_backend,
        )
        assert "postgres" in router.backends
        assert router.backends["postgres"] == mock_backend
