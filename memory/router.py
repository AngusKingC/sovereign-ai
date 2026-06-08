"""
Memory backend router.

Single responsibility: Route memory operations to appropriate backends
(Postgres, Qdrant, Obsidian) based on data type and access patterns.
"""

from enum import Enum
from typing import Any

from core.memory_router import MemoryBackend
from core.schemas import Task


class DataType(str, Enum):
    """Types of data for routing decisions."""
    STRUCTURED = "STRUCTURED"  # Goes to Postgres
    VECTOR = "VECTOR"  # Goes to Qdrant
    DOCUMENT = "DOCUMENT"  # Goes to Obsidian
    ALL = "ALL"  # Goes to all backends


class BackendRouter:
    """Routes memory operations to appropriate backends based on data type."""

    def __init__(
        self,
        postgres: MemoryBackend | None = None,
        qdrant: MemoryBackend | None = None,
        obsidian: MemoryBackend | None = None,
    ) -> None:
        """Initialize the router with available backends."""
        self.postgres = postgres
        self.qdrant = qdrant
        self.obsidian = obsidian

    def get_backend_for_type(self, data_type: DataType) -> MemoryBackend | None:
        """Get the appropriate backend for a given data type."""
        if data_type == DataType.STRUCTURED:
            return self.postgres
        elif data_type == DataType.VECTOR:
            return self.qdrant
        elif data_type == DataType.DOCUMENT:
            return self.obsidian
        elif data_type == DataType.ALL:
            return None  # Special case: use all backends
        return None

    async def write(self, data: dict[str, Any], data_type: DataType) -> None:
        """
        Write data to the appropriate backend based on data type.

        For DataType.ALL, writes to all available backends.
        """
        if data_type == DataType.ALL:
            backends = [b for b in [self.postgres, self.qdrant, self.obsidian] if b is not None]
            for backend in backends:
                await backend.write(data)
        else:
            backend = self.get_backend_for_type(data_type)
            if backend:
                await backend.write(data)

    async def fetch(self, task: Task, data_type: DataType = DataType.ALL) -> list[dict[str, Any]]:
        """
        Fetch memory from appropriate backends based on data type.

        For DataType.ALL, fetches from all available backends and aggregates results.
        """
        if data_type == DataType.ALL:
            backends = [b for b in [self.postgres, self.qdrant, self.obsidian] if b is not None]
            all_memory = []
            for backend in backends:
                memory = await backend.fetch(task)
                all_memory.extend(memory)
            return all_memory
        else:
            backend = self.get_backend_for_type(data_type)
            if backend:
                return await backend.fetch(task)
            return []

    def has_backend(self, data_type: DataType) -> bool:
        """Check if a backend is available for the given data type."""
        backend = self.get_backend_for_type(data_type)
        return backend is not None

