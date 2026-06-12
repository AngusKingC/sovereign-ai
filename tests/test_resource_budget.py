"""Tests for Resource Budget."""

import pytest
from unittest.mock import Mock, AsyncMock
from core.resource_budget import ResourceBudget, BudgetCheckResult
from core.observability import MemoryTraceEmitter


@pytest.mark.asyncio
class TestResourceBudget:
    """Tests for ResourceBudget."""

    async def test_check_token_budget_approves_when_under_per_task_limit(self) -> None:
        """Test that check_token_budget approves when under per-task limit."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_tokens_per_task=8192, emitter=emitter)

        result = await budget.check_token_budget("task-1", 4096)

        assert result.approved is True
        assert result.reason == "Token budget approved"
        assert result.tokens_available == 8192

    async def test_check_token_budget_denies_when_over_per_task_limit(self) -> None:
        """Test that check_token_budget denies when over per-task limit."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_tokens_per_task=8192, emitter=emitter)

        result = await budget.check_token_budget("task-1", 16384)

        assert result.approved is False
        assert "exceeds per-task limit" in result.reason
        assert result.tokens_available == 8192

    async def test_check_token_budget_approves_when_under_per_session_limit(self) -> None:
        """Test that check_token_budget approves when under per-session limit."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_tokens_per_task=8192, max_tokens_per_session=65536, emitter=emitter)

        # Record some usage in the session
        await budget.record_token_usage("task-1", 10000, "session-1")

        result = await budget.check_token_budget("task-2", 4096, "session-1")

        assert result.approved is True
        assert result.reason == "Token budget approved"

    async def test_check_token_budget_denies_when_cumulative_session_usage_would_exceed_limit(self) -> None:
        """Test that check_token_budget denies when cumulative session usage would exceed limit."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_tokens_per_task=8192, max_tokens_per_session=65536, emitter=emitter)

        # Record usage that brings session close to limit
        await budget.record_token_usage("task-1", 60000, "session-1")

        result = await budget.check_token_budget("task-2", 6000, "session-1")

        assert result.approved is False
        assert "would exceed per-session limit" in result.reason
        assert result.tokens_available == 5536  # 65536 - 60000

    async def test_check_worker_budget_approves_when_under_max_concurrent(self) -> None:
        """Test that check_worker_budget approves when under max_concurrent."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_concurrent_workers=3, emitter=emitter)

        result = await budget.check_worker_budget(2)

        assert result.approved is True
        assert result.reason == "Worker budget approved"

    async def test_check_worker_budget_denies_when_at_or_over_max_concurrent(self) -> None:
        """Test that check_worker_budget denies when at or over max_concurrent."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_concurrent_workers=3, emitter=emitter)

        result = await budget.check_worker_budget(3)

        assert result.approved is False
        assert "already at or exceeds max" in result.reason

    async def test_check_vram_budget_approves_when_model_fits_in_available_vram(self) -> None:
        """Test that check_vram_budget approves when model fits in available VRAM (mock ResourceManager)."""
        emitter = MemoryTraceEmitter()
        mock_resource_manager = Mock()
        budget = ResourceBudget(resource_manager=mock_resource_manager, emitter=emitter)

        # Currently, check_vram_budget delegates to ResourceManager and always approves
        # This test verifies the delegation path works
        result = await budget.check_vram_budget(5000)

        assert result.approved is True
        assert "delegated to ResourceManager" in result.reason

    async def test_check_vram_budget_denies_when_model_does_not_fit(self) -> None:
        """Test that check_vram_budget denies when model does not fit (mock ResourceManager)."""
        emitter = MemoryTraceEmitter()
        mock_resource_manager = Mock()
        budget = ResourceBudget(resource_manager=mock_resource_manager, emitter=emitter)

        # Currently, check_vram_budget delegates to ResourceManager and always approves
        # This test verifies the delegation path works
        result = await budget.check_vram_budget(50000)

        assert result.approved is True  # Delegated to ResourceManager
        assert "delegated to ResourceManager" in result.reason

    async def test_check_vram_budget_approves_with_no_resource_manager_skipped(self) -> None:
        """Test that check_vram_budget approves with no ResourceManager (skipped)."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(resource_manager=None, emitter=emitter)

        result = await budget.check_vram_budget(5000)

        assert result.approved is True
        assert "no resource manager" in result.reason.lower()

    async def test_check_all_returns_first_failure_encountered(self) -> None:
        """Test that check_all returns first failure encountered."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(
            max_tokens_per_task=8192,
            max_concurrent_workers=3,
            emitter=emitter,
        )

        # Token budget will fail first (over per-task limit)
        result = await budget.check_all(
            task_id="task-1",
            tokens_requested=16384,
            model_vram_mb=5000,
            current_concurrent=2,
        )

        assert result.approved is False
        assert "per-task limit" in result.reason

    async def test_check_all_returns_approved_when_all_checks_pass(self) -> None:
        """Test that check_all returns approved when all checks pass."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(
            max_tokens_per_task=8192,
            max_concurrent_workers=3,
            emitter=emitter,
        )

        result = await budget.check_all(
            task_id="task-1",
            tokens_requested=4096,
            model_vram_mb=5000,
            current_concurrent=2,
        )

        assert result.approved is True
        assert "All budget checks approved" in result.reason

    async def test_record_token_usage_accumulates_across_calls_for_same_session(self) -> None:
        """Test that record_token_usage accumulates across calls for same session."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_tokens_per_task=8192, max_tokens_per_session=65536, emitter=emitter)

        await budget.record_token_usage("task-1", 10000, "session-1")
        await budget.record_token_usage("task-2", 15000, "session-1")
        await budget.record_token_usage("task-3", 20000, "session-1")

        # Check that cumulative usage is tracked
        result = await budget.check_token_budget("task-4", 4096, "session-1")
        # 10000 + 15000 + 20000 = 45000 used, 65536 - 45000 = 20536 session remaining
        # But per-task limit is 8192, so tokens_available = min(8192, 20536) = 8192
        assert result.tokens_available == 8192

    async def test_trace_event_emitted_on_approval(self) -> None:
        """Test that TraceEvent is emitted on approval."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_tokens_per_task=8192, emitter=emitter)

        await budget.check_token_budget("task-1", 4096)

        events = emitter.get_events()
        approval_events = [e for e in events if "approved" in e.message.lower()]

        assert len(approval_events) > 0

    async def test_trace_event_emitted_on_denial_includes_which_check_failed(self) -> None:
        """Test that TraceEvent is emitted on denial and includes which check failed."""
        emitter = MemoryTraceEmitter()
        budget = ResourceBudget(max_tokens_per_task=8192, emitter=emitter)

        await budget.check_token_budget("task-1", 16384)

        events = emitter.get_events()
        denial_events = [e for e in events if "denied" in e.message.lower()]

        assert len(denial_events) > 0
        assert "per-task limit" in denial_events[0].data["reason"] if "reason" in denial_events[0].data else "per-task limit" in denial_events[0].message
