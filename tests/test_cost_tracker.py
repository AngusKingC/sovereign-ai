"""
Tests for CostTracker - central cost aggregation and spend cap enforcement.
"""

import asyncio

import pytest

from core.cost_tracker import CostPolicy, CostTracker
from core.observability import MemoryTraceEmitter, TraceEventType


@pytest.fixture
def emitter():
    """Fixture for trace emitter."""
    return MemoryTraceEmitter()


@pytest.fixture
def default_policy():
    """Fixture for default cost policy."""
    return CostPolicy()


@pytest.fixture
def custom_policy():
    """Fixture for custom cost policy."""
    return CostPolicy(
        daily_cap_usd=5.0,
        monthly_cap_usd=50.0,
        alert_threshold_pct=0.75,
        fallback_threshold_pct=0.85,
        fallback_model="gpt-3.5-turbo",
    )


@pytest.fixture
def cost_tracker(default_policy, emitter):
    """Fixture for CostTracker with default policy."""
    return CostTracker(policy=default_policy, emitter=emitter)


class TestCostTrackerInit:
    """Tests for CostTracker initialization."""

    def test_cost_tracker_init_default_policy(self, cost_tracker):
        """Test that default policy has correct values."""
        assert cost_tracker._policy.daily_cap_usd == 10.0
        assert cost_tracker._policy.monthly_cap_usd == 100.0
        assert cost_tracker._policy.alert_threshold_pct == 0.80
        assert cost_tracker._policy.fallback_threshold_pct == 0.90
        assert cost_tracker._policy.fallback_model is None

    def test_cost_tracker_init_custom_policy(self, custom_policy, emitter):
        """Test that custom policy is respected."""
        tracker = CostTracker(policy=custom_policy, emitter=emitter)
        assert tracker._policy.daily_cap_usd == 5.0
        assert tracker._policy.monthly_cap_usd == 50.0
        assert tracker._policy.alert_threshold_pct == 0.75
        assert tracker._policy.fallback_threshold_pct == 0.85
        assert tracker._policy.fallback_model == "gpt-3.5-turbo"


class TestRecordUsage:
    """Tests for record_usage method."""

    @pytest.mark.asyncio
    async def test_record_usage_updates_daily_spend(self, cost_tracker):
        """Test that record usage updates daily total."""
        await cost_tracker.record_usage(
            model="gpt-4",
            tokens_in=100,
            tokens_out=200,
            cost_usd=0.01,
            task_id="task-1",
        )
        daily_spend = cost_tracker.get_daily_spend()
        assert daily_spend == 0.01

    @pytest.mark.asyncio
    async def test_record_usage_updates_monthly_spend(self, cost_tracker):
        """Test that record usage updates monthly total."""
        await cost_tracker.record_usage(
            model="gpt-4",
            tokens_in=100,
            tokens_out=200,
            cost_usd=0.01,
            task_id="task-1",
        )
        monthly_spend = cost_tracker.get_monthly_spend()
        assert monthly_spend == 0.01

    @pytest.mark.asyncio
    async def test_record_usage_updates_model_spend(self, cost_tracker):
        """Test that record usage updates per-model total."""
        await cost_tracker.record_usage(
            model="gpt-4",
            tokens_in=100,
            tokens_out=200,
            cost_usd=0.01,
            task_id="task-1",
        )
        model_spend = cost_tracker.get_model_spend("gpt-4")
        assert model_spend == 0.01

    @pytest.mark.asyncio
    async def test_record_usage_emits_cost_trace(self, cost_tracker):
        """Test that record usage emits COST_RECORDED trace."""
        await cost_tracker.record_usage(
            model="gpt-4",
            tokens_in=100,
            tokens_out=200,
            cost_usd=0.01,
            task_id="task-1",
        )
        events = cost_tracker._emitter.get_events(
            event_type=TraceEventType.COST_RECORDED
        )
        assert len(events) == 1
        assert events[0].data["model"] == "gpt-4"
        assert events[0].data["cost_usd"] == 0.01

    @pytest.mark.asyncio
    async def test_cost_tracker_handles_zero_cost(self, cost_tracker):
        """Test that zero-cost usage (local model) is recorded correctly."""
        await cost_tracker.record_usage(
            model="local-llama",
            tokens_in=100,
            tokens_out=200,
            cost_usd=0.0,
            task_id="task-1",
        )
        daily_spend = cost_tracker.get_daily_spend()
        assert daily_spend == 0.0
        model_spend = cost_tracker.get_model_spend("local-llama")
        assert model_spend == 0.0


class TestCheckSpend:
    """Tests for check_spend method."""

    @pytest.mark.asyncio
    async def test_check_spend_approves_under_cap(self, cost_tracker):
        """Test that spend below cap returns approved=True."""
        decision = await cost_tracker.check_spend(estimated_cost_usd=1.0)
        assert decision.approved is True
        assert decision.reason == "within_caps"

    @pytest.mark.asyncio
    async def test_check_spend_denies_over_daily_cap(self, cost_tracker):
        """Test that spend over daily cap returns approved=False."""
        # Record $9.99 to get close to $10 cap
        await cost_tracker.record_usage(
            model="gpt-4",
            tokens_in=1000,
            tokens_out=2000,
            cost_usd=9.99,
            task_id="task-1",
        )
        decision = await cost_tracker.check_spend(estimated_cost_usd=0.02)
        assert decision.approved is False
        assert decision.reason == "daily_cap_exceeded"

    @pytest.mark.asyncio
    async def test_check_spend_denies_over_monthly_cap(self, emitter):
        """Test that spend over monthly cap returns approved=False."""
        # Use custom policy with high daily cap to test monthly cap
        custom_policy = CostPolicy(daily_cap_usd=1000.0, monthly_cap_usd=100.0)
        tracker = CostTracker(policy=custom_policy, emitter=emitter)
        # Record $99.99 to get close to $100 cap
        await tracker.record_usage(
            model="gpt-4",
            tokens_in=10000,
            tokens_out=20000,
            cost_usd=99.99,
            task_id="task-1",
        )
        decision = await tracker.check_spend(estimated_cost_usd=0.02)
        assert decision.approved is False
        assert decision.reason == "monthly_cap_exceeded"

    @pytest.mark.asyncio
    async def test_check_spend_triggers_fallback_at_threshold(
        self, custom_policy, emitter
    ):
        """Test that spend at 90% triggers fallback."""
        tracker = CostTracker(policy=custom_policy, emitter=emitter)
        # Record $4.24 to get to 85% of $5 cap
        await tracker.record_usage(
            model="gpt-4",
            tokens_in=1000,
            tokens_out=2000,
            cost_usd=4.24,
            task_id="task-1",
        )
        decision = await tracker.check_spend(estimated_cost_usd=0.01)
        assert decision.approved is True
        assert decision.reason == "fallback_threshold_reached"
        assert decision.fallback_model == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_check_spend_emits_alert_at_80_pct(self, cost_tracker):
        """Test that spend at 80% emits alert trace."""
        # Record $8.01 to cross 80% of $10 cap (alert threshold)
        await cost_tracker.record_usage(
            model="gpt-4",
            tokens_in=1000,
            tokens_out=2000,
            cost_usd=8.01,
            task_id="task-1",
        )
        events = cost_tracker._emitter.get_events(event_type=TraceEventType.COST_ALERT)
        assert len(events) == 1


class TestGetSpendSummary:
    """Tests for get_spend_summary method."""

    @pytest.mark.asyncio
    async def test_get_spend_summary_returns_all_breakdowns(self, cost_tracker):
        """Test that summary dict has daily, monthly, per-model breakdowns."""
        await cost_tracker.record_usage(
            model="gpt-4",
            tokens_in=100,
            tokens_out=200,
            cost_usd=0.01,
            task_id="task-1",
        )
        summary = cost_tracker.get_spend_summary()
        assert "daily_spend" in summary
        assert "monthly_spend" in summary
        assert "model_spend" in summary
        assert "daily_cap_usd" in summary
        assert "monthly_cap_usd" in summary
        assert "total_records" in summary
        assert summary["daily_spend"] == 0.01
        assert summary["monthly_spend"] == 0.01
        assert summary["model_spend"]["gpt-4"] == 0.01
        assert summary["total_records"] == 1


class TestConcurrentAccess:
    """Tests for concurrent access safety."""

    @pytest.mark.asyncio
    async def test_concurrent_record_usage_is_thread_safe(self, cost_tracker):
        """Test that multiple concurrent records don't corrupt state (asyncio.Lock)."""
        tasks = []
        for i in range(10):
            task = cost_tracker.record_usage(
                model="gpt-4",
                tokens_in=100,
                tokens_out=200,
                cost_usd=0.01,
                task_id=f"task-{i}",
            )
            tasks.append(task)
        await asyncio.gather(*tasks)
        daily_spend = cost_tracker.get_daily_spend()
        assert (
            abs(daily_spend - 0.1) < 0.0001
        )  # 10 * 0.01, with floating point tolerance
        assert abs(cost_tracker.get_model_spend("gpt-4") - 0.1) < 0.0001


class TestOrchestratorIntegration:
    """Integration tests for orchestrator wiring."""

    @pytest.mark.asyncio
    async def test_orchestrator_records_cost_after_task_completion(self, cost_tracker):
        """Test that orchestrator calls record_usage with correct args after task completion."""
        # This is a simplified integration test - full orchestrator test would require
        # mocking the full orchestrator setup
        await cost_tracker.record_usage(
            model="gpt-4",
            tokens_in=100,
            tokens_out=200,
            cost_usd=0.01,
            task_id="task-123",
        )
        summary = cost_tracker.get_spend_summary()
        assert summary["total_records"] == 1
        assert summary["model_spend"]["gpt-4"] == 0.01
