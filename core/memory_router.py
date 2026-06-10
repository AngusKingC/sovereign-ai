"""
Memory routing and access control.

Single responsibility: Govern all memory read/write operations, enforcing access control
and routing requests to appropriate memory backends.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from core.exceptions import CrossScopeAccessError
from core.schemas import StrategicContext, Task
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    emit_trace,
)

if TYPE_CHECKING:
    from core.observability import TraceEmitter


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
        emitter: "TraceEmitter | None" = None,
    ) -> None:
        """Initialize the memory router with backends."""
        self.backends = backends
        if emitter is None:
            from core.observability import MemoryTraceEmitter
            self.emitter = MemoryTraceEmitter()
        else:
            self.emitter = emitter

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
                try:
                    await self.emitter.emit(
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
                except Exception:
                    pass

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            await self.emitter.emit(
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
        except Exception:
            pass

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
                try:
                    await self.emitter.emit(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.MEMORY_ROUTER,
                        message=f"Memory write failed for backend {name}",
                        level=TraceLevel.ERROR,
                        data={
                            "backend": name,
                            "error": str(e),
                        },
                    )
                except Exception:
                    pass

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            await self.emitter.emit(
                event_type=TraceEventType.DATA_WRITE,
                component=TraceComponent.MEMORY_ROUTER,
                message="Memory write completed",
                level=TraceLevel.INFO,
                data={
                    "backend_count": len(backends_to_write),
                },
                duration_ms=duration_ms,
            )
        except Exception:
            pass

    async def scoped_write(
        self,
        key: str,
        value: str,
        scope: str,
        caller_id: str,
    ) -> None:
        """Write to a scoped memory partition with access control.
        
        Args:
            key: The key to write
            value: The value to write
            scope: Either "global" or "worker:{worker_id}"
            caller_id: The ID of the caller attempting the write
            
        Raises:
            CrossScopeAccessError: If caller does not have write access to the scope
        """
        # Enforce scope access rules
        if scope == "global":
            if caller_id != "orchestrator":
                raise CrossScopeAccessError(caller_id=caller_id, scope=scope)
        elif scope.startswith("worker:"):
            worker_id = scope.split(":", 1)[1]
            if caller_id != worker_id:
                raise CrossScopeAccessError(caller_id=caller_id, scope=scope)
        else:
            raise ValueError(f"Invalid scope: {scope}")
        
        # Write to backend with namespaced key
        namespaced_key = f"{scope}:{key}"
        await self.write({"key": namespaced_key, "value": value})
        
        # Emit trace event
        try:
            await self.emitter.emit(
                event_type=TraceEventType.DATA_WRITE,
                component=TraceComponent.MEMORY_ROUTER,
                message="Scoped memory write completed",
                level=TraceLevel.INFO,
                data={
                    "scope": scope,
                    "key": key,
                    "caller_id": caller_id,
                },
            )
        except Exception:
            pass

    async def scoped_read(
        self,
        key: str,
        scope: str,
        caller_id: str,
    ) -> str | None:
        """Read from a scoped memory partition with access control.
        
        Args:
            key: The key to read
            scope: Either "global" or "worker:{worker_id}"
            caller_id: The ID of the caller attempting the read
            
        Returns:
            The value if found, None otherwise
            
        Raises:
            CrossScopeAccessError: If caller does not have read access to the scope
        """
        # Enforce scope access rules
        if scope == "global":
            # Any caller may read global scope
            pass
        elif scope.startswith("worker:"):
            worker_id = scope.split(":", 1)[1]
            if caller_id != worker_id:
                raise CrossScopeAccessError(caller_id=caller_id, scope=scope)
        else:
            raise ValueError(f"Invalid scope: {scope}")
        
        # Read from backend with namespaced key
        namespaced_key = f"{scope}:{key}"
        try:
            # For now, we'll use a simple approach - read from the first backend
            # In a full implementation, this would query the appropriate backend
            if "postgres" in self.backends:
                # Try to read from postgres backend
                # This is a simplified implementation - actual implementation would
                # depend on the backend's read API
                pass
        except Exception:
            pass
        
        # Emit trace event
        try:
            await self.emitter.emit(
                event_type=TraceEventType.DATA_READ,
                component=TraceComponent.MEMORY_ROUTER,
                message="Scoped memory read completed",
                level=TraceLevel.INFO,
                data={
                    "scope": scope,
                    "key": key,
                    "caller_id": caller_id,
                },
            )
        except Exception:
            pass
        
        # For now, return None - actual implementation would fetch from backend
        return None

    async def get_global_context(self, caller_id: str) -> StrategicContext | None:
        """Read the global StrategicContext.
        
        Args:
            caller_id: The ID of the caller attempting the read
            
        Returns:
            StrategicContext if found, None otherwise
        """
        # Any caller may read global context
        try:
            # Read from backend
            namespaced_key = "global:strategic_context"
            # Simplified implementation - actual would query backend
            return None
        except Exception:
            return None

    async def set_global_context(
        self,
        context: StrategicContext,
        caller_id: str,
    ) -> None:
        """Write the global StrategicContext.
        
        Args:
            context: The StrategicContext to persist
            caller_id: The ID of the caller attempting the write
            
        Raises:
            CrossScopeAccessError: If caller is not the orchestrator
        """
        # Only orchestrator may write global context
        if caller_id != "orchestrator":
            raise CrossScopeAccessError(caller_id=caller_id, scope="global")
        
        # Persist to backend
        namespaced_key = "global:strategic_context"
        import json
        await self.write({"key": namespaced_key, "value": context.model_dump_json()})
        
        # Emit trace event
        try:
            await self.emitter.emit(
                event_type=TraceEventType.DATA_WRITE,
                component=TraceComponent.MEMORY_ROUTER,
                message="Global context updated",
                level=TraceLevel.INFO,
                data={
                    "context_id": context.context_id,
                    "caller_id": caller_id,
                },
            )
        except Exception:
            pass
