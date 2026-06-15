"""Tests for retention manager."""

import pytest
from unittest.mock import Mock, AsyncMock

from system.retention_manager import RetentionConfig, RetentionManager
from core.observability import MemoryTraceEmitter


@pytest.mark.asyncio
class TestRetentionConfig:
    """Tests for RetentionConfig model."""

    async def test_retention_config_constructs_with_correct_defaults(self) -> None:
        """Test that RetentionConfig constructs with correct defaults."""
        config = RetentionConfig()
        
        assert config.trace_events_ttl_days == 90
        assert config.dry_run is False

    async def test_retention_config_keep_worker_ratings_defaults_to_true(self) -> None:
        """Test that RetentionConfig.keep_worker_ratings defaults to True."""
        config = RetentionConfig()
        
        assert config.keep_worker_ratings is True


@pytest.mark.asyncio
class TestRetentionManager:
    """Tests for RetentionManager class."""

    async def test_prune_trace_events_calls_memory_router_and_returns_count(self) -> None:
        """Test that prune_trace_events() calls memory router and returns count."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 10})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        count = await manager.prune_trace_events()
        
        assert count == 10
        mock_router.write.assert_called_once()
        call_args = mock_router.write.call_args[0][0]
        assert call_args["op"] == "trace_events_prune"
        assert call_args["older_than_days"] == 90
        assert call_args["dry_run"] is False

    async def test_prune_trace_events_dry_run_returns_count_without_deleting(self) -> None:
        """Test that prune_trace_events(dry_run=True) returns count without deleting."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 10})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        count = await manager.prune_trace_events(dry_run=True)
        
        assert count == 10
        call_args = mock_router.write.call_args[0][0]
        assert call_args["dry_run"] is True

    async def test_prune_trace_events_emits_retention_trace_events_pruned_event(self) -> None:
        """Test that prune_trace_events() emits RETENTION_TRACE_EVENTS_PRUNED trace event."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 10})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        await manager.prune_trace_events()
        
        events = emitter.get_events()
        prune_events = [e for e in events if e.event_type == "retention_trace_events_pruned"]
        assert len(prune_events) > 0

    async def test_prune_task_history_skips_tasks_in_awaiting_approval_state(self) -> None:
        """Test that prune_task_history() skips tasks in AWAITING_APPROVAL state."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 5})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        count = await manager.prune_task_history()
        
        call_args = mock_router.write.call_args[0][0]
        assert "awaiting_approval" in call_args["skip_states"]

    async def test_prune_task_history_skips_tasks_in_in_progress_state(self) -> None:
        """Test that prune_task_history() skips tasks in IN_PROGRESS state."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 5})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        count = await manager.prune_task_history()
        
        call_args = mock_router.write.call_args[0][0]
        assert "in_progress" in call_args["skip_states"]

    async def test_prune_task_history_dry_run_returns_count_without_deleting(self) -> None:
        """Test that prune_task_history(dry_run=True) returns count without deleting."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 5})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        count = await manager.prune_task_history(dry_run=True)
        
        assert count == 5
        call_args = mock_router.write.call_args[0][0]
        assert call_args["dry_run"] is True

    async def test_prune_qdrant_vectors_calls_memory_router_with_correct_qdrant_prune_op(self) -> None:
        """Test that prune_qdrant_vectors() calls memory router with correct qdrant_prune op."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 20})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        count = await manager.prune_qdrant_vectors()
        
        mock_router.write.assert_called_once()
        call_args = mock_router.write.call_args[0][0]
        assert call_args["op"] == "qdrant_prune"
        assert call_args["older_than_days"] == 90

    async def test_archive_obsidian_notes_calls_memory_router_with_correct_obsidian_archive_op(self) -> None:
        """Test that archive_obsidian_notes() calls memory router with correct obsidian_archive op."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 15})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        count = await manager.archive_obsidian_notes()
        
        mock_router.write.assert_called_once()
        call_args = mock_router.write.call_args[0][0]
        assert call_args["op"] == "obsidian_archive"
        assert call_args["older_than_days"] == 90

    async def test_run_all_returns_retention_report_with_accumulated_counts(self) -> None:
        """Test that run_all() returns RetentionReport with accumulated counts."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 10})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        report = await manager.run_all()
        
        assert report.rules_applied == 4
        assert report.records_deleted == 30  # 10 + 10 + 10 (trace_events + task_history + qdrant)
        assert report.records_archived == 10  # obsidian_notes
        assert report.records_expired == 40  # deleted + archived

    async def test_run_all_catches_per_method_errors_and_appends_to_report_errors(self) -> None:
        """Test that run_all() catches per-method errors and appends to report.errors."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(side_effect=Exception("test error"))
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        report = await manager.run_all()
        
        assert len(report.errors) == 4  # All four methods failed
        assert report.rules_applied == 4

    async def test_run_all_emits_retention_run_started_trace_event(self) -> None:
        """Test that run_all() emits RETENTION_RUN_STARTED trace event."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 10})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        await manager.run_all()
        
        events = emitter.get_events()
        start_events = [e for e in events if e.event_type == "retention_run_started"]
        assert len(start_events) > 0

    async def test_run_all_emits_retention_run_completed_trace_event(self) -> None:
        """Test that run_all() emits RETENTION_RUN_COMPLETED trace event."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 10})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        await manager.run_all()
        
        events = emitter.get_events()
        complete_events = [e for e in events if e.event_type == "retention_run_completed"]
        assert len(complete_events) > 0

    async def test_schedule_hook_calls_run_all(self) -> None:
        """Test that schedule_hook() calls run_all()."""
        emitter = MemoryTraceEmitter()
        mock_router = Mock()
        mock_router.write = AsyncMock(return_value={"count": 10})
        
        manager = RetentionManager(mock_router, emitter=emitter)
        
        # Mock run_all to track if it was called
        original_run_all = manager.run_all
        call_count = [0]
        
        async def mock_run_all(*args, **kwargs):
            call_count[0] += 1
            return await original_run_all(*args, **kwargs)
        
        manager.run_all = mock_run_all
        
        await manager.schedule_hook()
        
        assert call_count[0] == 1
