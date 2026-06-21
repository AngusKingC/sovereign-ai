"""
Memory compactor for tiered memory management.

Single responsibility: Manage hot/warm/cold memory tiers with periodic background compaction.
Hot tier is in-context (dict). Warm tier is Qdrant (semantic search). Cold tier is Postgres archival.
"""

import asyncio
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from core.observability import (
    TraceComponent,
    TraceLevel,
    TraceEventType,
    MemoryTraceEmitter,
    TraceEvent,
)

if TYPE_CHECKING:
    from core.observability import TraceEmitter
    from core.memory_router import MemoryRouter


class MemoryTier(str, Enum):
    """Memory tier classification."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class TieredMemoryEntry(BaseModel):
    """A memory entry with tier information."""
    key: str
    value: dict
    tier: MemoryTier = MemoryTier.HOT
    access_count: int = 0
    last_accessed: datetime
    created_at: datetime
    scope: str = "global"


class MemoryCompactor:
    """Manages hot/warm/cold memory tiers with periodic background compaction."""

    def __init__(
        self,
        memory_router: "MemoryRouter",
        hot_limit: int = 50,
        warm_threshold_days: int = 1,
        cold_threshold_days: int = 7,
        emitter: "TraceEmitter | None" = None,
    ) -> None:
        """Initialize the memory compactor.

        Args:
            memory_router: The memory router to use for warm/cold tier writes
            hot_limit: Maximum number of entries in hot tier before eviction
            warm_threshold_days: Days after which entries move from hot to warm
            cold_threshold_days: Days after which entries move from warm to cold
            emitter: Trace emitter for events
        """
        self._router = memory_router
        self._hot_limit = hot_limit
        self._warm_threshold = timedelta(days=warm_threshold_days)
        self._cold_threshold = timedelta(days=cold_threshold_days)
        self._emitter = emitter or MemoryTraceEmitter()
        self._hot_store: dict[str, TieredMemoryEntry] = {}
        self._running = False

    def get(self, key: str, scope: str) -> dict | None:
        """Get a value from the hot store.

        Args:
            key: The key to look up
            scope: The scope for the key

        Returns:
            The value if found in hot store, None otherwise
        """
        full_key = f"{scope}:{key}"
        if full_key in self._hot_store:
            entry = self._hot_store[full_key]
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            
            # Emit trace event (fire and forget, don't await)
            start_time = time.perf_counter()
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            event = TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.MEMORY_ROUTER,
                level=TraceLevel.INFO,
                message=f"Hot store hit: {key}",
                data={
                    "key": key,
                    "scope": scope,
                    "access_count": entry.access_count,
                },
                duration_ms=duration_ms,
            )
            # Don't await - fire and forget
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._emitter.emit(event))
            except RuntimeError:
                # No event loop running, skip emission
                pass
            
            return entry.value
        return None

    async def put(self, key: str, value: dict, scope: str) -> None:
        """Put a value into the hot store.

        Args:
            key: The key to store
            value: The value to store
            scope: The scope for the key
        """
        full_key = f"{scope}:{key}"
        
        # Evict if hot store exceeds limit
        if len(self._hot_store) >= self._hot_limit and full_key not in self._hot_store:
            await self._evict_from_hot()
        
        entry = TieredMemoryEntry(
            key=key,
            value=value,
            tier=MemoryTier.HOT,
            access_count=0,
            last_accessed=datetime.utcnow(),
            created_at=datetime.utcnow(),
            scope=scope,
        )
        self._hot_store[full_key] = entry
        
        # Emit trace event (fire and forget, don't await)
        start_time = time.perf_counter()
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.MEMORY_ROUTER,
            level=TraceLevel.INFO,
            message=f"Hot store put: {key}",
            data={
                "key": key,
                "scope": scope,
                "hot_store_size": len(self._hot_store),
            },
            duration_ms=duration_ms,
        )
        # Don't await - fire and forget
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._emitter.emit(event))
        except RuntimeError:
            # No event loop running, skip emission
            pass

    async def _evict_from_hot(self) -> None:
        """Evict the least recently used entry from hot store.

        Moves the entry to warm or cold tier based on age.
        """
        if not self._hot_store:
            return
        
        # Find entry with lowest access_count
        entry_to_evict = min(self._hot_store.values(), key=lambda e: e.access_count)
        full_key = f"{entry_to_evict.scope}:{entry_to_evict.key}"
        
        # Determine destination tier based on age
        age = datetime.utcnow() - entry_to_evict.last_accessed
        if age < self._warm_threshold:
            destination_tier = MemoryTier.WARM
            prefix = "warm"
        else:
            destination_tier = MemoryTier.COLD
            prefix = "cold"
        
        # Write to backend with tier prefix
        prefixed_key = f"{prefix}:{full_key}"
        asyncio.create_task(self._router.write({prefixed_key: entry_to_evict.value}))
        
        # Remove from hot store
        del self._hot_store[full_key]
        
        # Emit trace event (fire and forget, don't await)
        start_time = time.perf_counter()
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.MEMORY_ROUTER,
            level=TraceLevel.INFO,
            message=f"Evicted from hot to {destination_tier.value}: {entry_to_evict.key}",
            data={
                "key": entry_to_evict.key,
                "scope": entry_to_evict.scope,
                "destination_tier": destination_tier.value,
                "access_count": entry_to_evict.access_count,
                "age_days": age.days,
            },
            duration_ms=duration_ms,
        )
        # Don't await - fire and forget
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._emitter.emit(event))
        except RuntimeError:
            # No event loop running, skip emission
            pass

    async def compact(self, scope: str) -> dict:
        """Compact memory for a given scope.

        Moves entries older than thresholds to appropriate tiers.

        Args:
            scope: The scope to compact

        Returns:
            Summary dict with moved counts
        """
        moved_to_warm = 0
        moved_to_cold = 0
        now = datetime.utcnow()
        
        keys_to_remove = []
        for full_key, entry in self._hot_store.items():
            if entry.scope != scope:
                continue
            
            age = now - entry.last_accessed
            if age >= self._cold_threshold:
                # Move to cold
                prefixed_key = f"cold:{full_key}"
                asyncio.create_task(self._router.write({prefixed_key: entry.value}))
                keys_to_remove.append(full_key)
                moved_to_cold += 1
            elif age >= self._warm_threshold:
                # Move to warm
                prefixed_key = f"warm:{full_key}"
                asyncio.create_task(self._router.write({prefixed_key: entry.value}))
                keys_to_remove.append(full_key)
                moved_to_warm += 1
        
        for key in keys_to_remove:
            del self._hot_store[key]
        
        summary = {
            "moved_to_warm": moved_to_warm,
            "moved_to_cold": moved_to_cold,
            "remaining_hot": len(self._hot_store),
        }
        
        # Emit trace event (fire and forget, don't await)
        start_time = time.perf_counter()
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event = TraceEvent(
            event_type=TraceEventType.OPERATION_COMPLETE,
            component=TraceComponent.MEMORY_ROUTER,
            level=TraceLevel.INFO,
            message=f"Compaction complete for scope: {scope}",
            data={
                "scope": scope,
                **summary,
            },
            duration_ms=duration_ms,
        )
        # Don't await - fire and forget
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._emitter.emit(event))
        except RuntimeError:
            # No event loop running, skip emission
            pass
        
        return summary

    async def start_background_compaction(self, interval_seconds: int, scope: str) -> None:
        """Start background compaction task.

        Args:
            interval_seconds: Interval between compactions
            scope: The scope to compact
        """
        if self._running:
            return
        
        self._running = True
        
        async def compaction_loop():
            while self._running:
                await asyncio.sleep(interval_seconds)
                if self._running:
                    self.compact(scope)
        
        asyncio.create_task(compaction_loop())

    def stop_background_compaction(self) -> None:
        """Stop background compaction task."""
        self._running = False
