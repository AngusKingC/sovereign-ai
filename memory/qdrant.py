"""
Qdrant vector database backend.

Single responsibility: Manage vector embeddings and semantic search operations
through Qdrant, providing the vector memory layer.
"""

import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from core.memory_router import MemoryBackend
from core.schemas import Task
from core.embedder import OllamaEmbedder
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class QdrantBackend(MemoryBackend):
    """Qdrant backend for vector embeddings and semantic search."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "memory_vectors",
        vector_size: int = 768,
        embedder: OllamaEmbedder | None = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the Qdrant backend with connection details."""
        self.url = url
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.embedder = embedder if embedder is not None else OllamaEmbedder()
        self.client: QdrantClient | None = None
        self._emitter = emitter or MemoryTraceEmitter()

    async def _ensure_connection(self) -> None:
        """Ensure Qdrant client is initialized."""
        if self.client is None:
            self.client = QdrantClient(url=self.url)
            await self._initialize_collection()

    async def _initialize_collection(self) -> None:
        """Create the collection if it doesn't exist."""
        if self.client is None:
            raise RuntimeError("Qdrant client not initialized")

        # Check if collection exists
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """
        Fetch memory relevant to the task from Qdrant.

        Performs semantic search using the task intent as query.
        Returns empty list if connection fails.
        """
        start_time = time.perf_counter()

        try:
            # Emit fetch start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Qdrant memory fetch started",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "qdrant",
                        "task_id": str(task.task_id),
                        "collection_name": self.collection_name,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            await self._ensure_connection()

            if self.client is None:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.MEMORY_FETCH,
                        component=TraceComponent.MEMORY_ROUTER,
                        message="Qdrant memory fetch completed (client not initialized)",
                        level=TraceLevel.WARNING,
                        data={
                            "backend_type": "qdrant",
                            "task_id": str(task.task_id),
                            "records_fetched": 0,
                        },
                        duration_ms=duration_ms,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    pass
                return []

            # Generate embedding for task intent
            try:
                query_vector = await self.embedder.embed(task.intent)
            except Exception as e:
                # Fallback to zero vector on embedder failure
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.EMBEDDING_ERROR,
                        component=TraceComponent.EMBEDDER,
                        message="Embedder failed during fetch, falling back to zero vector",
                        level=TraceLevel.WARNING,
                        data={"error": str(e), "task_intent": task.intent},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    pass
                query_vector = [0.0] * self.vector_size

            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=10,
            )

            result = [
                {
                    "source": "qdrant",
                    "content": hit.payload.get("content", {}),
                    "score": hit.score,
                    "id": str(hit.id),
                }
                for hit in search_result
            ]

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit fetch complete event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Qdrant memory fetch completed",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "qdrant",
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
                    message="Qdrant memory fetch failed",
                    level=TraceLevel.ERROR,
                    data={
                        "backend_type": "qdrant",
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
        Write data to Qdrant as vector embeddings.

        Stores data with embedding vector generated by embedder.
        Falls back to zero vector if embedder fails.
        Silently fails if connection is not available.
        """
        start_time = time.perf_counter()

        try:
            # Emit write start event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_WRITE,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Qdrant memory write started",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "qdrant",
                        "collection_name": self.collection_name,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

            await self._ensure_connection()

            if self.client is None:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.MEMORY_WRITE,
                        component=TraceComponent.MEMORY_ROUTER,
                        message="Qdrant memory write skipped (client not initialized)",
                        level=TraceLevel.WARNING,
                        data={
                            "backend_type": "qdrant",
                        },
                        duration_ms=duration_ms,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    pass
                return

            # Generate embedding for content
            text = data.get("content", "")
            try:
                vector = await self.embedder.embed(text)
            except Exception as e:
                # Fallback to zero vector on embedder failure
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.EMBEDDING_ERROR,
                        component=TraceComponent.EMBEDDER,
                        message="Embedder failed during write, falling back to zero vector",
                        level=TraceLevel.WARNING,
                        data={"error": str(e), "content": text},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    pass
                vector = [0.0] * self.vector_size

            point = PointStruct(
                id=hash(str(data)),  # Simple hash-based ID
                vector=vector,
                payload=data,
            )

            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit write complete event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_WRITE,
                    component=TraceComponent.MEMORY_ROUTER,
                    message="Qdrant memory write completed",
                    level=TraceLevel.INFO,
                    data={
                        "backend_type": "qdrant",
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
                    message="Qdrant memory write failed",
                    level=TraceLevel.ERROR,
                    data={
                        "backend_type": "qdrant",
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
        """Close the Qdrant client and embedder."""
        if self.client:
            self.client.close()
            self.client = None
        await self.embedder.close()


