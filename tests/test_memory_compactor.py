"""
Tests for MemoryCompactor and tier-aware memory management.

Tests the hot/warm/cold memory tier system with periodic background compaction.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from core.memory_compactor import MemoryCompactor, MemoryTier, TieredMemoryEntry
from core.memory_router import MemoryRouter, MemoryBackend
from core.schemas import Task
from core.observability import MemoryTraceEmitter


class TestMemoryCompactor:
    """Test suite for MemoryCompactor."""
    
    @pytest.fixture
    def mock_memory_router(self):
        """Create a mock memory router."""
        router = AsyncMock(spec=MemoryRouter)
        router.write = AsyncMock()
        return router
    
    @pytest.fixture
    def emitter(self):
        """Create a MemoryTraceEmitter for testing."""
        return MemoryTraceEmitter()
    
    @pytest.fixture
    def compactor(self, mock_memory_router, emitter):
        """Create a MemoryCompactor with mock dependencies."""
        return MemoryCompactor(
            memory_router=mock_memory_router,
            hot_limit=2,
            warm_threshold_days=1,
            cold_threshold_days=7,
            emitter=emitter,
        )
    
    @pytest.mark.asyncio
    async def test_put_adds_entry_to_hot_store_with_tier_hot(self, compactor):
        """Test that put() adds entry to hot store with tier=HOT."""
        await compactor.put("key1", {"data": "value1"}, "global")
        assert "global:key1" in compactor._hot_store
        assert compactor._hot_store["global:key1"].tier == MemoryTier.HOT
    
    @pytest.mark.asyncio
    async def test_get_returns_value_from_hot_store_when_present(self, compactor):
        """Test that get() returns value from hot store when present."""
        await compactor.put("key1", {"data": "value1"}, "global")
        result = compactor.get("key1", "global")
        assert result == {"data": "value1"}
    
    def test_get_returns_none_when_key_not_in_hot_store(self, compactor):
        """Test that get() returns None when key not in hot store."""
        result = compactor.get("nonexistent", "global")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_increments_access_count_on_hit(self, compactor):
        """Test that get() increments access_count on hit."""
        await compactor.put("key1", {"data": "value1"}, "global")
        compactor.get("key1", "global")
        assert compactor._hot_store["global:key1"].access_count == 1
        compactor.get("key1", "global")
        assert compactor._hot_store["global:key1"].access_count == 2
    
    @pytest.mark.asyncio
    async def test_get_updates_last_accessed_on_hit(self, compactor):
        """Test that get() updates last_accessed on hit."""
        await compactor.put("key1", {"data": "value1"}, "global")
        original_last_accessed = compactor._hot_store["global:key1"].last_accessed
        import time
        time.sleep(0.01)  # Small delay to ensure time difference
        compactor.get("key1", "global")
        assert compactor._hot_store["global:key1"].last_accessed > original_last_accessed
    
    @pytest.mark.asyncio
    async def test_put_triggers_eviction_when_hot_store_exceeds_hot_limit(self, compactor):
        """Test that put() triggers eviction when hot store exceeds hot_limit."""
        await compactor.put("key1", {"data": "value1"}, "global")
        await compactor.put("key2", {"data": "value2"}, "global")
        await compactor.put("key3", {"data": "value3"}, "global")  # Should trigger eviction
        assert len(compactor._hot_store) <= 2
    
    @pytest.mark.asyncio
    async def test_evict_from_hot_moves_recently_accessed_entry_to_warm_tier(self, compactor):
        """Test that _evict_from_hot() moves recently accessed entry to warm tier."""
        await compactor.put("key1", {"data": "value1"}, "global")
        await compactor.put("key2", {"data": "value2"}, "global")
        # Access key1 to make it more recently accessed
        compactor.get("key1", "global")
        # Trigger eviction by adding third entry
        await compactor.put("key3", {"data": "value3"}, "global")
        # Check that router.write was called with warm prefix
        assert compactor._router.write.called
        call_args = compactor._router.write.call_args
        prefixed_key = list(call_args[0][0].keys())[0]
        assert prefixed_key.startswith("warm:")
    
    @pytest.mark.asyncio
    async def test_evict_from_hot_moves_old_entry_to_cold_tier(self, compactor):
        """Test that _evict_from_hot() moves old entry to cold tier."""
        await compactor.put("key1", {"data": "value1"}, "global")
        # Manually set last_accessed to be old
        compactor._hot_store["global:key1"].last_accessed = datetime.utcnow() - timedelta(days=2)
        await compactor.put("key2", {"data": "value2"}, "global")
        # Trigger eviction by adding third entry
        await compactor.put("key3", {"data": "value3"}, "global")
        # Check that router.write was called with cold prefix
        assert compactor._router.write.called
        call_args = compactor._router.write.call_args
        prefixed_key = list(call_args[0][0].keys())[0]
        assert prefixed_key.startswith("cold:")
    
    @pytest.mark.asyncio
    async def test_evict_from_hot_removes_evicted_entry_from_hot_store(self, compactor):
        """Test that _evict_from_hot() removes evicted entry from hot store."""
        await compactor.put("key1", {"data": "value1"}, "global")
        await compactor.put("key2", {"data": "value2"}, "global")
        # Trigger eviction by adding third entry
        await compactor.put("key3", {"data": "value3"}, "global")
        # One entry should have been removed
        assert len(compactor._hot_store) == 2
    
    @pytest.mark.asyncio
    async def test_compact_moves_entries_older_than_warm_threshold_to_warm_tier(self, compactor):
        """Test that compact() moves entries older than warm_threshold to warm tier."""
        await compactor.put("key1", {"data": "value1"}, "global")
        # Manually set last_accessed to be old
        compactor._hot_store["global:key1"].last_accessed = datetime.utcnow() - timedelta(days=2)
        summary = await compactor.compact("global")
        assert summary["moved_to_warm"] == 1
        assert "global:key1" not in compactor._hot_store
    
    @pytest.mark.asyncio
    async def test_compact_moves_entries_older_than_cold_threshold_to_cold_tier(self, compactor):
        """Test that compact() moves entries older than cold_threshold to cold tier."""
        await compactor.put("key1", {"data": "value1"}, "global")
        # Manually set last_accessed to be very old
        compactor._hot_store["global:key1"].last_accessed = datetime.utcnow() - timedelta(days=10)
        summary = await compactor.compact("global")
        assert summary["moved_to_cold"] == 1
        assert "global:key1" not in compactor._hot_store
    
    @pytest.mark.asyncio
    async def test_compact_returns_correct_summary_dict_with_moved_counts(self, compactor):
        """Test that compact() returns correct summary dict with moved counts."""
        await compactor.put("key1", {"data": "value1"}, "global")
        await compactor.put("key2", {"data": "value2"}, "global")
        # Set different ages
        compactor._hot_store["global:key1"].last_accessed = datetime.utcnow() - timedelta(days=2)
        compactor._hot_store["global:key2"].last_accessed = datetime.utcnow() - timedelta(days=10)
        summary = await compactor.compact("global")
        assert summary["moved_to_warm"] == 1
        assert summary["moved_to_cold"] == 1
        assert summary["remaining_hot"] == 0
    
    @pytest.mark.asyncio
    async def test_compact_emits_trace_event_with_summary(self, compactor, emitter):
        """Test that compact() emits a trace event with summary."""
        await compactor.put("key1", {"data": "value1"}, "global")
        compactor._hot_store["global:key1"].last_accessed = datetime.utcnow() - timedelta(days=2)
        summary = await compactor.compact("global")
        # Wait for async trace event emission
        await asyncio.sleep(0.01)
        events = emitter.get_events()
        assert len(events) > 0
        compact_event = [e for e in events if "Compaction complete" in e.message][0]
        assert "moved_to_warm" in compact_event.data
        assert "moved_to_cold" in compact_event.data
    
    @pytest.mark.asyncio
    async def test_start_background_compaction_does_not_start_second_task_if_already_running(self, compactor):
        """Test that start_background_compaction() does not start a second task if already running."""
        await compactor.start_background_compaction(1, "global")
        initial_running = compactor._running
        await compactor.start_background_compaction(1, "global")
        assert compactor._running == initial_running
        compactor.stop_background_compaction()
    
    @pytest.mark.asyncio
    async def test_stop_background_compaction_sets_running_flag_to_false(self, compactor):
        """Test that stop_background_compaction() sets running flag to False."""
        await compactor.start_background_compaction(1, "global")
        assert compactor._running is True
        compactor.stop_background_compaction()
        assert compactor._running is False
    
    def test_tiered_memory_entry_validates_correctly_with_all_required_fields(self):
        """Test that TieredMemoryEntry validates correctly with all required fields."""
        entry = TieredMemoryEntry(
            key="test_key",
            value={"data": "test"},
            tier=MemoryTier.HOT,
            access_count=0,
            last_accessed=datetime.utcnow(),
            created_at=datetime.utcnow(),
            scope="global",
        )
        assert entry.key == "test_key"
        assert entry.value == {"data": "test"}
        assert entry.tier == MemoryTier.HOT


class TestMemoryRouterIntegration:
    """Test suite for MemoryRouter integration with MemoryCompactor."""
    
    @pytest.fixture
    def mock_backend(self):
        """Create a mock memory backend."""
        backend = AsyncMock(spec=MemoryBackend)
        backend.fetch = AsyncMock(return_value=[])
        backend.write = AsyncMock()
        return backend
    
    @pytest.fixture
    def emitter(self):
        """Create a MemoryTraceEmitter for testing."""
        return MemoryTraceEmitter()
    
    @pytest.fixture
    def compactor(self, emitter):
        """Create a MemoryCompactor with mock dependencies."""
        mock_router = AsyncMock()
        mock_router.write = AsyncMock()
        return MemoryCompactor(
            memory_router=mock_router,
            hot_limit=50,
            warm_threshold_days=1,
            cold_threshold_days=7,
            emitter=emitter,
        )
    
    @pytest.fixture
    def router_with_compactor(self, mock_backend, compactor):
        """Create a MemoryRouter with compactor."""
        return MemoryRouter(
            backends={"test": mock_backend},
            compactor=compactor,
        )
    
    @pytest.fixture
    def router_without_compactor(self, mock_backend):
        """Create a MemoryRouter without compactor."""
        return MemoryRouter(
            backends={"test": mock_backend},
            compactor=None,
        )
    
    @pytest.fixture
    def task(self):
        """Create a test task."""
        return Task(
            task_id=uuid4(),
            intent="test task",
            complexity_score=0.5,
            priority="normal",
            current_state="received",
            created_at=datetime.now(),
        )
    
    @pytest.mark.asyncio
    async def test_memory_router_with_compactor_checks_hot_store_before_backend_on_fetch(
        self, router_with_compactor, compactor, task
    ):
        """Test that MemoryRouter with compactor checks hot store before backend on fetch."""
        # Populate hot store
        await compactor.put("test task", {"cached": "data"}, "global")
        # Fetch should return hot store result without calling backend
        result = await router_with_compactor.fetch(task)
        assert len(result) == 1
        assert result[0] == {"cached": "data"}
        # Backend should not have been called
        assert router_with_compactor.backends["test"].fetch.call_count == 0
    
    @pytest.mark.asyncio
    async def test_memory_router_with_compactor_populates_hot_store_after_backend_fetch(
        self, router_with_compactor, compactor, mock_backend, task
    ):
        """Test that MemoryRouter with compactor populates hot store after backend fetch."""
        # Backend returns data
        mock_backend.fetch.return_value = [{"backend": "data"}]
        # Fetch should populate hot store
        result = await router_with_compactor.fetch(task)
        assert len(result) == 1
        assert result[0] == {"backend": "data"}
        # Check hot store was populated
        hot_result = compactor.get("test task", "global")
        assert hot_result is not None
    
    @pytest.mark.asyncio
    async def test_memory_router_without_compactor_behaves_identically_to_before(
        self, router_without_compactor, mock_backend, task
    ):
        """Test that MemoryRouter without compactor behaves identically to before (no regression)."""
        mock_backend.fetch.return_value = [{"backend": "data"}]
        result = await router_without_compactor.fetch(task)
        assert len(result) == 1
        assert result[0] == {"backend": "data"}
        # Backend should have been called
        assert mock_backend.fetch.call_count == 1
