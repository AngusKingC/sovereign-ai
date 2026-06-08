"""
Backend router tests.

Single responsibility: Test memory backend routing logic,
data type classification, and backend selection.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest

from core.memory_router import MemoryBackend
from core.schemas import Task, TaskPriority
from memory.router import BackendRouter, DataType


class MockBackend(MemoryBackend):
    """Mock backend for testing."""

    def __init__(self) -> None:
        self.storage: list[dict[str, Any]] = []

    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """Fetch mock data."""
        return [{"source": "mock", "data": "test"}]

    async def write(self, data: dict[str, Any]) -> None:
        """Write to storage."""
        self.storage.append(data)


class TestDataType:
    """Test DataType enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert DataType.STRUCTURED.value == "STRUCTURED"
        assert DataType.VECTOR.value == "VECTOR"
        assert DataType.DOCUMENT.value == "DOCUMENT"
        assert DataType.ALL.value == "ALL"


class TestBackendRouter:
    """Test BackendRouter functionality."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock backend."""
        return MockBackend()

    @pytest.fixture
    def sample_task(self):
        """Create a sample task."""
        return Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

    def test_router_initialization(self):
        """Test router initializes with backends."""
        postgres = MockBackend()
        qdrant = MockBackend()
        obsidian = MockBackend()

        router = BackendRouter(
            postgres=postgres,
            qdrant=qdrant,
            obsidian=obsidian,
        )

        assert router.postgres == postgres
        assert router.qdrant == qdrant
        assert router.obsidian == obsidian

    def test_router_initialization_with_none(self):
        """Test router initializes with None backends."""
        router = BackendRouter()
        assert router.postgres is None
        assert router.qdrant is None
        assert router.obsidian is None

    def test_get_backend_for_structured(self, mock_backend):
        """Test getting backend for STRUCTURED data type."""
        router = BackendRouter(postgres=mock_backend)
        backend = router.get_backend_for_type(DataType.STRUCTURED)
        assert backend == mock_backend

    def test_get_backend_for_vector(self, mock_backend):
        """Test getting backend for VECTOR data type."""
        router = BackendRouter(qdrant=mock_backend)
        backend = router.get_backend_for_type(DataType.VECTOR)
        assert backend == mock_backend

    def test_get_backend_for_document(self, mock_backend):
        """Test getting backend for DOCUMENT data type."""
        router = BackendRouter(obsidian=mock_backend)
        backend = router.get_backend_for_type(DataType.DOCUMENT)
        assert backend == mock_backend

    def test_get_backend_for_all_returns_none(self, mock_backend):
        """Test getting backend for ALL returns None."""
        router = BackendRouter(obsidian=mock_backend)
        backend = router.get_backend_for_type(DataType.ALL)
        assert backend is None

    def test_write_to_structured_backend(self, mock_backend):
        """Test writing to STRUCTURED backend."""
        router = BackendRouter(postgres=mock_backend)

        import asyncio

        data = {"content": "test"}
        asyncio.run(router.write(data, DataType.STRUCTURED))

        assert len(mock_backend.storage) == 1
        assert mock_backend.storage[0] == data

    def test_write_to_vector_backend(self, mock_backend):
        """Test writing to VECTOR backend."""
        router = BackendRouter(qdrant=mock_backend)

        import asyncio

        data = {"content": "test"}
        asyncio.run(router.write(data, DataType.VECTOR))

        assert len(mock_backend.storage) == 1

    def test_write_to_document_backend(self, mock_backend):
        """Test writing to DOCUMENT backend."""
        router = BackendRouter(obsidian=mock_backend)

        import asyncio

        data = {"content": "test"}
        asyncio.run(router.write(data, DataType.DOCUMENT))

        assert len(mock_backend.storage) == 1

    def test_write_to_all_backends(self):
        """Test writing to ALL backends writes to all available."""
        postgres = MockBackend()
        qdrant = MockBackend()
        obsidian = MockBackend()

        router = BackendRouter(
            postgres=postgres,
            qdrant=qdrant,
            obsidian=obsidian,
        )

        import asyncio

        data = {"content": "test"}
        asyncio.run(router.write(data, DataType.ALL))

        assert len(postgres.storage) == 1
        assert len(qdrant.storage) == 1
        assert len(obsidian.storage) == 1

    def test_write_to_all_with_partial_backends(self):
        """Test writing to ALL with only some backends available."""
        postgres = MockBackend()
        obsidian = MockBackend()

        router = BackendRouter(
            postgres=postgres,
            qdrant=None,
            obsidian=obsidian,
        )

        import asyncio

        data = {"content": "test"}
        asyncio.run(router.write(data, DataType.ALL))

        assert len(postgres.storage) == 1
        assert len(obsidian.storage) == 1

    def test_write_to_missing_backend(self):
        """Test writing to a missing backend does nothing."""
        router = BackendRouter(postgres=None)

        import asyncio

        data = {"content": "test"}
        # Should not raise an error
        asyncio.run(router.write(data, DataType.STRUCTURED))

    def test_fetch_from_structured_backend(self, mock_backend, sample_task):
        """Test fetching from STRUCTURED backend."""
        router = BackendRouter(postgres=mock_backend)

        import asyncio

        memory = asyncio.run(router.fetch(sample_task, DataType.STRUCTURED))

        assert len(memory) == 1
        assert memory[0]["source"] == "mock"

    def test_fetch_from_all_backends(self, sample_task):
        """Test fetching from ALL backends aggregates results."""
        postgres = MockBackend()
        qdrant = MockBackend()
        obsidian = MockBackend()

        router = BackendRouter(
            postgres=postgres,
            qdrant=qdrant,
            obsidian=obsidian,
        )

        import asyncio

        memory = asyncio.run(router.fetch(sample_task, DataType.ALL))

        # Each backend returns 1 item, so total should be 3
        assert len(memory) == 3

    def test_fetch_from_missing_backend(self, sample_task):
        """Test fetching from missing backend returns empty list."""
        router = BackendRouter(postgres=None)

        import asyncio

        memory = asyncio.run(router.fetch(sample_task, DataType.STRUCTURED))

        assert memory == []

    def test_has_backend_true(self, mock_backend):
        """Test has_backend returns True when backend exists."""
        router = BackendRouter(postgres=mock_backend)
        assert router.has_backend(DataType.STRUCTURED) is True

    def test_has_backend_false(self):
        """Test has_backend returns False when backend missing."""
        router = BackendRouter(postgres=None)
        assert router.has_backend(DataType.STRUCTURED) is False

    def test_has_backend_all_type(self):
        """Test has_backend for ALL type returns False."""
        router = BackendRouter(postgres=MockBackend())
        assert router.has_backend(DataType.ALL) is False

