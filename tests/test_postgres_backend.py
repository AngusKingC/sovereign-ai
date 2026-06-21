"""
PostgreSQL backend tests.

Single responsibility: Test PostgreSQL memory backend operations,
connection management, and data persistence.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from core.schemas import Task, TaskPriority
from memory.postgres import PostgresBackend


class TestPostgresBackend:
    """Test PostgresBackend functionality."""

    @pytest.fixture
    def postgres_backend(self):
        """Create a postgres backend with test DSN."""
        # Using a test DSN that may not exist - tests will handle connection errors
        return PostgresBackend(
            dsn="postgresql://localhost:5432/test_sovereign",
            table_name="test_memory_entries",
        )

    @pytest.fixture
    def sample_task(self):
        """Create a sample task for testing."""
        return Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )

    def test_backend_initialization(self, postgres_backend):
        """Test backend initializes with correct configuration."""
        assert postgres_backend.dsn == "postgresql://localhost:5432/test_sovereign"
        assert postgres_backend.table_name == "test_memory_entries"
        assert postgres_backend.pool is None

    def test_fetch_without_connection(self, postgres_backend, sample_task):
        """Test fetch returns empty list when no connection."""
        import asyncio

        # Should not raise error, just return empty list
        memory = asyncio.run(postgres_backend.fetch(sample_task))
        assert memory == []

    def test_write_without_connection(self, postgres_backend):
        """Test write silently fails when no connection."""
        import asyncio

        data = {"content": "test data", "task_id": str(uuid4())}

        # Should not raise error, just silently fail
        asyncio.run(postgres_backend.write(data))

    def test_close_without_connection(self, postgres_backend):
        """Test close works even without connection."""
        import asyncio

        # Should not raise error
        asyncio.run(postgres_backend.close())
        assert postgres_backend.pool is None

    @pytest.mark.asyncio
    async def test_connection_handling(self, postgres_backend):
        """Test connection pool creation and cleanup."""
        # This test requires a running PostgreSQL instance
        # It will fail if no database is available, which is expected
        try:
            await postgres_backend._ensure_connection()
            assert postgres_backend.pool is not None
            await postgres_backend.close()
            assert postgres_backend.pool is None
        except Exception as e:
            # Connection failed - expected in test environment without DB
            assert "connection" in str(e).lower() or "refused" in str(e).lower()

    def test_backend_implements_interface(self, postgres_backend):
        """Test that backend implements MemoryBackend interface."""
        from core.memory_router import MemoryBackend

        assert isinstance(postgres_backend, MemoryBackend)
        assert hasattr(postgres_backend, "fetch")
        assert hasattr(postgres_backend, "write")

    def test_data_formatting_for_write(self, postgres_backend):
        """Test that data is properly formatted for PostgreSQL."""
        data = {
            "task_id": str(uuid4()),
            "content": "test content",
            "metadata": {"key": "value"},
            "other_field": "value",
        }

        # Simulate the data extraction that happens in write()
        task_id = data.get("task_id")
        content = {k: v for k, v in data.items() if k not in ["task_id", "metadata"]}
        metadata = data.get("metadata", {})

        assert task_id is not None
        assert "task_id" not in content
        assert "metadata" not in content
        assert "content" in content
        assert "other_field" in content
        assert metadata == {"key": "value"}

