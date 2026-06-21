"""
Qdrant backend tests.

Single responsibility: Test Qdrant vector database backend operations,
connection management, and vector search functionality.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from unittest.mock import Mock, AsyncMock, patch

from core.schemas import Task, TaskPriority
from memory.qdrant import QdrantBackend
from core.embedder import OllamaEmbedder


class TestQdrantBackend:
    """Test QdrantBackend functionality."""

    @pytest.fixture
    def qdrant_backend(self):
        """Create a qdrant backend with test configuration."""
        return QdrantBackend(
            vector_size=768,
            url="http://localhost:6333",
            collection_name="test_memory_vectors",
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

    def test_backend_initialization(self, qdrant_backend):
        """Test backend initializes with correct configuration."""
        assert qdrant_backend.url == "http://localhost:6333"
        assert qdrant_backend.collection_name == "test_memory_vectors"
        assert qdrant_backend.vector_size == 768
        assert qdrant_backend.client is None

    def test_fetch_without_connection(self, qdrant_backend, sample_task):
        """Test fetch returns empty list when no connection."""
        import asyncio

        # Should not raise error, just return empty list
        memory = asyncio.run(qdrant_backend.fetch(sample_task))
        assert memory == []

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_write_without_connection(self, qdrant_backend):
        """Test write silently fails when no connection."""
        import asyncio

        data = {"content": "test data", "task_id": str(uuid4())}

        # Should not raise error, just silently fail
        asyncio.run(qdrant_backend.write(data))

    def test_close_without_connection(self, qdrant_backend):
        """Test close works even without connection."""
        import asyncio

        # Should not raise error
        asyncio.run(qdrant_backend.close())
        assert qdrant_backend.client is None

    def test_backend_implements_interface(self, qdrant_backend):
        """Test that backend implements MemoryBackend interface."""
        from core.memory_router import MemoryBackend

        assert isinstance(qdrant_backend, MemoryBackend)
        assert hasattr(qdrant_backend, "fetch")
        assert hasattr(qdrant_backend, "write")

    def test_vector_size_configuration(self, qdrant_backend):
        """Test that vector size is configurable."""
        custom_backend = QdrantBackend(vector_size=1536)
        assert custom_backend.vector_size == 1536

    def test_collection_name_configuration(self, qdrant_backend):
        """Test that collection name is configurable."""
        custom_backend = QdrantBackend(vector_size=768, collection_name="custom_collection")
        assert custom_backend.collection_name == "custom_collection"

    def test_url_configuration(self, qdrant_backend):
        """Test that URL is configurable."""
        custom_backend = QdrantBackend(vector_size=768, url="http://custom:6333")
        assert custom_backend.url == "http://custom:6333"

    @pytest.mark.asyncio
    async def test_write_calls_embedder_with_correct_text(self):
        """Test that write() calls embedder with correct text."""
        mock_embedder = Mock(spec=OllamaEmbedder)
        mock_embedder.embed = AsyncMock(return_value=[0.1] * 768)
        mock_embedder.close = AsyncMock()
        
        backend = QdrantBackend(vector_size=768, embedder=mock_embedder)
        
        data = {"content": "test content", "task_id": str(uuid4())}
        
        # Mock Qdrant client to avoid actual connection
        with patch('memory.qdrant.QdrantClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.get_collections.return_value = Mock(collections=[])
            
            await backend.write(data)
            
            # Verify embedder was called with correct text
            mock_embedder.embed.assert_called_once_with("test content")
    
    @pytest.mark.asyncio
    async def test_fetch_calls_embedder_with_task_intent(self):
        """Test that fetch() calls embedder with task.intent."""
        mock_embedder = Mock(spec=OllamaEmbedder)
        mock_embedder.embed = AsyncMock(return_value=[0.1] * 768)
        mock_embedder.close = AsyncMock()
        
        backend = QdrantBackend(vector_size=768, embedder=mock_embedder)
        
        task = Task(
            task_id=uuid4(),
            intent="test intent",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )
        
        # Mock Qdrant client to avoid actual connection
        with patch('memory.qdrant.QdrantClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.get_collections.return_value = Mock(collections=[])
            mock_client.search.return_value = []
            
            await backend.fetch(task)
            
            # Verify embedder was called with task intent
            mock_embedder.embed.assert_called_once_with("test intent")
    
    @pytest.mark.asyncio
    async def test_embedder_failure_during_write_falls_back_to_zero_vector(self):
        """Test that embedder failure during write() falls back to zero vector."""
        mock_embedder = Mock(spec=OllamaEmbedder)
        mock_embedder.embed = AsyncMock(side_effect=RuntimeError("Embedder failed"))
        mock_embedder.close = AsyncMock()
        
        backend = QdrantBackend(vector_size=768, embedder=mock_embedder)
        
        data = {"content": "test content", "task_id": str(uuid4())}
        
        # Mock Qdrant client
        with patch('memory.qdrant.QdrantClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.get_collections.return_value = Mock(collections=[])
            
            # Mock emit_trace to avoid actual trace emission during test
            with patch('core.observability.emit_trace'):
                await backend.write(data)
                
                # Verify upsert was called with zero vector (core behavior)
                mock_client.upsert.assert_called_once()
                upsert_call = mock_client.upsert.call_args
                vector = upsert_call[1]["points"][0].vector
                assert vector == [0.0] * 768
    
    @pytest.mark.asyncio
    async def test_embedder_failure_during_fetch_falls_back_to_zero_vector(self):
        """Test that embedder failure during fetch() falls back to zero vector."""
        mock_embedder = Mock(spec=OllamaEmbedder)
        mock_embedder.embed = AsyncMock(side_effect=RuntimeError("Embedder failed"))
        mock_embedder.close = AsyncMock()
        
        backend = QdrantBackend(vector_size=768, embedder=mock_embedder)
        
        task = Task(
            task_id=uuid4(),
            intent="test intent",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(timezone.utc),
        )
        
        # Mock Qdrant client
        with patch('memory.qdrant.QdrantClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.get_collections.return_value = Mock(collections=[])
            mock_client.search.return_value = []
            
            # Mock emit_trace to avoid actual trace emission during test
            with patch('core.observability.emit_trace'):
                await backend.fetch(task)
                
                # Verify search was called with zero vector (core behavior)
                mock_client.search.assert_called_once()
                search_call = mock_client.search.call_args
                vector = search_call[1]["query_vector"]
                assert vector == [0.0] * 768

