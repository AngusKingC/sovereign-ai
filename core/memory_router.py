"""
Memory routing and access control.

Single responsibility: Govern all memory read/write operations, enforcing access control
and routing requests to appropriate memory backends.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from core.schemas import Task
from core.observability import (
    TraceComponent,
    TraceLevel,
    TraceEventType,
    TraceEvent,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.memory_compactor import MemoryCompactor

if TYPE_CHECKING:
    from core.observability import TraceEmitter


class MemoryScope(str, Enum):
    """Memory scope for scoping access."""
    GLOBAL = "global"
    WORKER = "worker"


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

    @abstractmethod
    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching the given prefix."""
        raise NotImplementedError


class ScopedMemoryRouter:
    """Memory router with scope-based key prefixing and access control."""

    def __init__(
        self,
        router: "MemoryRouter",
        scope: str,
        emitter: "TraceEmitter | None" = None,
    ) -> None:
        """Initialize the scoped memory router.

        Args:
            router: The underlying memory router to delegate to
            scope: The scope for this router (e.g., "global" or "worker:{worker_id}")
            emitter: Trace emitter for events
        """
        self._router = router
        self._scope = scope
        self._emitter = emitter or MemoryTraceEmitter()

    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """Fetch memory relevant to the task with scope prefixing.

        Args:
            task: The task to fetch memory for

        Returns:
            List of memory entries with scope-prefixed keys
        """
        import time

        start_time = time.perf_counter()

        # Prefix task intent with scope for backend queries
        scoped_task = Task(
            task_id=task.task_id,
            intent=f"{self._scope}:{task.intent}",
            complexity_score=task.complexity_score,
            priority=task.priority,
            current_state=task.current_state,
            created_at=task.created_at,
        )

        memory = await self._router.fetch(scoped_task)

        # Cross-scope guard: filter out keys from other worker scopes
        if self._scope.startswith("worker:"):
            filtered_memory = []
            for entry in memory:
                for key in entry.keys():
                    if key.startswith("worker:") and not key.startswith(f"{self._scope}:"):
                        raise PermissionError(
                            f"Cross-scope access denied: {self._scope} cannot read {key}"
                        )
                filtered_memory.append(entry)
            memory = filtered_memory

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.MEMORY_FETCH,
            component=TraceComponent.MEMORY_ROUTER,
            level=TraceLevel.INFO,
            message="Scoped memory fetch completed",
            data={
                "task_id": str(task.task_id),
                "scope": self._scope,
                "memory_count": len(memory),
            },
            duration_ms=duration_ms,
        )
        await self._emitter.emit(event)

        return memory

    async def write(self, data: dict[str, Any]) -> None:
        """Write data to memory with scope prefixing.

        Args:
            data: The data to write (keys will be prefixed with scope)
        """
        import time

        start_time = time.perf_counter()

        # Prefix all keys with scope
        scoped_data = {f"{self._scope}:{key}": value for key, value in data.items()}

        await self._router.write(scoped_data)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.MEMORY_WRITE,
            component=TraceComponent.MEMORY_ROUTER,
            level=TraceLevel.INFO,
            message="Scoped memory write completed",
            data={
                "scope": self._scope,
                "key_count": len(scoped_data),
            },
            duration_ms=duration_ms,
        )
        await self._emitter.emit(event)


class MemoryRouter:
    """Routes memory operations to appropriate backends with governed access."""

    def __init__(
        self,
        backends: dict[str, MemoryBackend] | None = None,
        emitter: "TraceEmitter | None" = None,
        compactor: "MemoryCompactor | None" = None,
        postgres_backend: MemoryBackend | None = None,
    ) -> None:
        """Initialize the memory router with backends.

        Args:
            backends: Dictionary of backend name to backend instance. Optional;
                      defaults to empty dict. If postgres_backend is also
                      provided, it is added under the "postgres" key.
            emitter: Trace emitter for events
            compactor: Optional memory compactor for tiered memory management
            postgres_backend: Optional single postgres backend (converted to backends dict for compatibility)
        """
        backends = backends or {}
        if postgres_backend is not None:
            backends = backends.copy()
            backends["postgres"] = postgres_backend
        self.backends = backends
        self.emitter = emitter or MemoryTraceEmitter()
        self._compactor = compactor

    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        """
        Fetch memory relevant to the task from all backends.

        This is the only allowed entry point for memory reads.
        """
        import time

        start_time = time.perf_counter()
        all_memory = []

        # Check hot store first if compactor is configured
        if self._compactor:
            scope = "global"
            key = task.intent
            if ":" in task.intent:
                parts = task.intent.split(":", 1)
                if parts[0] in ["global", "worker", "warm", "cold"]:
                    scope = parts[0]
                    key = parts[1]
            
            hot_result = self._compactor.get(key, scope)
            if hot_result is not None:
                all_memory.append(hot_result)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                event = TraceEvent(
                    event_type=TraceEventType.MEMORY_FETCH,
                    component=TraceComponent.MEMORY_ROUTER,
                    level=TraceLevel.INFO,
                    message="Memory fetch from hot store completed",
                    data={
                        "task_id": str(task.task_id),
                        "backend_count": len(self.backends),
                        "memory_count": len(all_memory),
                        "source": "hot_store",
                    },
                    duration_ms=duration_ms,
                )
                await self.emitter.emit(event)
                return all_memory

        for backend_name, backend in self.backends.items():
            try:
                memory = await backend.fetch(task)
                all_memory.extend(memory)
            except Exception as e:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.MEMORY_ROUTER,
                    level=TraceLevel.ERROR,
                    message="Memory fetch error",
                    data={
                        "task_id": str(task.task_id),
                        "backend": backend_name,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self.emitter.emit(event)

        # Store each memory entry in hot store if compactor is configured
        if self._compactor:
            for entry in all_memory:
                await self._compactor.put(key, entry, scope)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.MEMORY_FETCH,
            component=TraceComponent.MEMORY_ROUTER,
            level=TraceLevel.INFO,
            message="Memory fetch completed",
            data={
                "task_id": str(task.task_id),
                "backend_count": len(self.backends),
                "memory_count": len(all_memory),
            },
            duration_ms=duration_ms,
        )
        await self.emitter.emit(event)

        return all_memory

    async def write(self, data: dict[str, Any], backend_name: str | None = None) -> None:
        """
        Write data to memory backends.

        If backend_name is specified, writes only to that backend.
        Otherwise, writes to all backends.
        """
        import time

        start_time = time.perf_counter()

        if backend_name:
            backends_to_write = {backend_name: self.backends[backend_name]}
        else:
            backends_to_write = self.backends

        for name, backend in backends_to_write.items():
            try:
                await backend.write(data)
            except Exception as e:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.MEMORY_ROUTER,
                    level=TraceLevel.ERROR,
                    message="Memory write error",
                    data={
                        "backend": name,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self.emitter.emit(event)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.MEMORY_WRITE,
            component=TraceComponent.MEMORY_ROUTER,
            level=TraceLevel.INFO,
            message="Memory write completed",
            data={
                "backend_count": len(backends_to_write),
            },
            duration_ms=duration_ms,
        )
        await self.emitter.emit(event)

    async def list_keys(self, prefix: str) -> list[str]:
        """
        List all keys matching the given prefix from all backends.

        Args:
            prefix: The key prefix to match

        Returns:
            List of matching keys from all backends
        """
        import time

        start_time = time.perf_counter()
        all_keys = []

        for backend_name, backend in self.backends.items():
            try:
                keys = await backend.list_keys(prefix)
                all_keys.extend(keys)
            except Exception as e:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.MEMORY_ROUTER,
                    level=TraceLevel.ERROR,
                    message="List keys error",
                    data={
                        "prefix": prefix,
                        "backend": backend_name,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self.emitter.emit(event)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.MEMORY_ACCESS,
            component=TraceComponent.MEMORY_ROUTER,
            level=TraceLevel.INFO,
            message="List keys completed",
            data={
                "prefix": prefix,
                "key_count": len(all_keys),
            },
            duration_ms=duration_ms,
        )
        await self.emitter.emit(event)

        return all_keys

    async def fetch_by_filter(
        self,
        filter: dict[str, Any],
        collection: str | None = None,
        limit: int | None = None,
        filter_func: Any = None,
    ) -> list[dict[str, Any]]:
        """Fetch memory entries matching a filter dictionary.

        This is the document-store-style query interface. Callers that need
        filtered retrieval (by collection, by document_id, by arbitrary filter
        dict, or by a callable filter_func) should use this method instead of
        fetch(task), which is for task-based routing queries.

        Args:
            filter: Dictionary of key-value pairs to match against stored entries.
            collection: Optional collection/scope name to restrict the search.
            limit: Optional maximum number of results to return.
            filter_func: Optional callable that takes a dict and returns bool.
                         If provided, only entries where filter_func(entry) is True are returned.

        Returns:
            List of matching memory entries (dicts).
        """
        import time
        from datetime import datetime
        from uuid import uuid4

        start_time = time.perf_counter()
        all_results: list[dict[str, Any]] = []

        for backend_name, backend in self.backends.items():
            try:
                # Backends implement fetch(task: Task). We construct a minimal
                # Task from the filter dict so the existing backend interface
                # works without modification.
                from core.schemas import Task, TaskPriority, TaskStatus
                task = Task(
                    task_id=uuid4(),
                    intent=str(filter),
                    complexity_score=0.0,
                    priority=TaskPriority.NORMAL,
                    current_state=TaskStatus.RECEIVED,
                    created_at=datetime.utcnow(),
                )
                results = await backend.fetch(task)
                # Apply filter matching in Python (backends don't support filtered queries natively)
                for entry in results:
                    content = entry.get("content", entry)
                    if isinstance(content, dict):
                        match = all(content.get(k) == v for k, v in filter.items())
                    else:
                        match = True  # Can't filter, return as-is
                    if match and filter_func is not None:
                        match = filter_func(entry)
                    if match:
                        all_results.append(entry)
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.DATA_READ,
                        component=TraceComponent.MEMORY_ROUTER,
                        level=TraceLevel.WARNING,
                        message=f"fetch_by_filter backend error: {backend_name}",
                        data={"error": str(e)},
                        duration_ms=0,
                    )
                    await self.emitter.emit(event)
                except Exception:
                    pass

        # Apply limit
        if limit is not None:
            all_results = all_results[:limit]

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            event = TraceEvent(
                event_type=TraceEventType.DATA_READ,
                component=TraceComponent.MEMORY_ROUTER,
                level=TraceLevel.INFO,
                message="fetch_by_filter completed",
                data={"filter": filter, "collection": collection, "result_count": len(all_results)},
                duration_ms=duration_ms,
            )
            await self.emitter.emit(event)
        except Exception:
            pass

        return all_results

    async def write_to_collection(
        self,
        data: dict[str, Any],
        collection: str,
        document_id: str | None = None,
    ) -> None:
        """Write data to a named collection.

        This is the document-store-style write interface. Callers that need
        to write to a specific collection (ratings, evaluations, instructions,
        etc.) with an optional document_id should use this method instead of
        write(data), which writes to all backends without collection scoping.

        Args:
            data: Dictionary of data to write.
            collection: Collection/scope name (e.g., "ratings", "evaluations").
            document_id: Optional document identifier. If provided, the data
                         dict is augmented with collection and document_id fields.
        """
        import time

        start_time = time.perf_counter()

        # Augment data with collection and document_id metadata
        write_data = data.copy()
        write_data["_collection"] = collection
        if document_id is not None:
            write_data["_document_id"] = document_id

        for backend_name, backend in self.backends.items():
            try:
                await backend.write(write_data)
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.DATA_WRITE,
                        component=TraceComponent.MEMORY_ROUTER,
                        level=TraceLevel.WARNING,
                        message=f"write_to_collection backend error: {backend_name}",
                        data={"collection": collection, "error": str(e)},
                        duration_ms=0,
                    )
                    await self.emitter.emit(event)
                except Exception:
                    pass

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            event = TraceEvent(
                event_type=TraceEventType.DATA_WRITE,
                component=TraceComponent.MEMORY_ROUTER,
                level=TraceLevel.INFO,
                message="write_to_collection completed",
                data={"collection": collection, "document_id": document_id},
                duration_ms=duration_ms,
            )
            await self.emitter.emit(event)
        except Exception:
            pass

    async def get_global_context(self, caller_id: str = "orchestrator") -> "StrategicContext | None":
        """Get the shared global StrategicContext.

        Args:
            caller_id: Identifier of the caller (for access control logging).

        Returns:
            StrategicContext if set, None otherwise.
        """
        from core.schemas import StrategicContext
        results = await self.fetch_by_filter(
            filter={"_collection": "global_context"},
            collection="global_context",
            limit=1,
        )
        if results:
            content = results[0].get("content", results[0])
            if isinstance(content, dict) and "context" in content:
                return StrategicContext(**content["context"])
        return None

    async def set_global_context(self, context: Any, caller_id: str = "orchestrator") -> None:
        """Set the shared global StrategicContext.

        Args:
            context: StrategicContext to store.
            caller_id: Identifier of the caller (for access control logging).
        """
        await self.write_to_collection(
            data={"context": context.model_dump() if hasattr(context, "model_dump") else context},
            collection="global_context",
            document_id="current",
        )
