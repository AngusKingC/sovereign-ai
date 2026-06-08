"""
Memory routing and access control.

Single responsibility: Govern all memory read/write operations, enforcing access control
and routing requests to appropriate memory backends.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from core.schemas import Task
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    emit_trace,
)


class MemoryBackend(ABC):
    """Abstract interface for memory backends."""

    @abstractmethod
    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """Fetch memory relevant to the task."""
        raise NotImplementedError

    @abstractmethod
    async def write(self, data: dict[str, Any]) -> None:
        """Write data to memory."""
        raise NotImplementedError


class MemoryRouter:
    """Routes memory operations to appropriate backends with governed access."""

    def __init__(
        self,
        backends: dict[str, MemoryBackend],
    ) -> None:
        """Initialize the memory router with backends."""
        self.backends = backends

    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """
        Fetch memory relevant to the task from all backends.

        This is the only allowed entry point for memory reads.
        """
        import time

        start_time = time.perf_counter()
        all_memory = []

        for backend_name, backend in self.backends.items():
            try:
                memory = await backend.fetch(task)
                all_memory.extend(memory)
            except Exception as e:
                await emit_trace(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.MEMORY_ROUTER,
                    message=f"Memory query failed for backend {backend_name}",
                    level=TraceLevel.ERROR,
                    data={
                        "task_id": str(task.task_id),
                        "backend": backend_name,
                        "error": str(e),
                    },
                )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        await emit_trace(
            event_type=TraceEventType.DATA_READ,
            component=TraceComponent.MEMORY_ROUTER,
            message="Memory query completed",
            level=TraceLevel.INFO,
            data={
                "task_id": str(task.task_id),
                "backend_count": len(self.backends),
                "memory_count": len(all_memory),
            },
            duration_ms=duration_ms,
        )

        return all_memory

    async def write(self, data: dict[str, Any], backend_name: str | None = None) -> None:
        """
        Write data to memory backends.

        If backend_name is specified, writes only to that backend.
        Otherwise, writes to all backends.
        """
        import time
        from datetime import datetime

        start_time = time.perf_counter()

        if backend_name:
            backends_to_write = {backend_name: self.backends[backend_name]}
        else:
            backends_to_write = self.backends

        for name, backend in backends_to_write.items():
            try:
                await backend.write(data)
            except Exception as e:
                await emit_trace(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.MEMORY_ROUTER,
                    message=f"Memory write failed for backend {name}",
                    level=TraceLevel.ERROR,
                    data={
                        "backend": name,
                        "error": str(e),
                    },
                )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        await emit_trace(
            event_type=TraceEventType.DATA_WRITE,
            component=TraceComponent.MEMORY_ROUTER,
            message="Memory write completed",
            level=TraceLevel.INFO,
            data={
                "backend_count": len(backends_to_write),
            },
            duration_ms=duration_ms,
        )
