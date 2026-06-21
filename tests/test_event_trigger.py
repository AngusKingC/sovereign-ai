"""
Tests for event trigger system.
"""

import pytest
from datetime import datetime, timedelta, timezone

from core.event_trigger import TriggerType, TriggerOperator, EventTrigger, TriggerEngine
from core.observability import MemoryTraceEmitter
from core.schemas import Task


class TestTriggerType:
    """Test TriggerType enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert TriggerType.THRESHOLD.value == "threshold"
        assert TriggerType.SCHEDULE.value == "schedule"
        assert TriggerType.CHANGE.value == "change"


class TestTriggerOperator:
    """Test TriggerOperator enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert TriggerOperator.GREATER_THAN.value == ">"
        assert TriggerOperator.LESS_THAN.value == "<"
        assert TriggerOperator.GREATER_THAN_OR_EQUAL.value == ">="
        assert TriggerOperator.LESS_THAN_OR_EQUAL.value == "<="
        assert TriggerOperator.EQUAL.value == "=="
        assert TriggerOperator.NOT_EQUAL.value == "!="


class TestEventTrigger:
    """Test EventTrigger model."""

    def test_trigger_creation(self):
        """Test creating a trigger."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        assert trigger.metric_name == "cpu_usage"
        assert trigger.operator == TriggerOperator.GREATER_THAN
        assert trigger.threshold == 80.0
        assert trigger.enabled is True
        assert trigger.trigger_count == 0

    def test_trigger_defaults(self):
        """Test trigger default values."""
        trigger = EventTrigger(
            trigger_type=TriggerType.SCHEDULE,
            metric_name="daily_report",
            schedule_interval_seconds=86400,
        )
        assert trigger.operator is None
        assert trigger.threshold is None
        assert trigger.enabled is True
        assert trigger.trigger_count == 0
        assert trigger.last_triggered_at is None

    def test_should_trigger_greater_than(self):
        """Test threshold trigger with greater than operator."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        assert trigger.should_trigger(85.0) is True
        assert trigger.should_trigger(80.0) is False
        assert trigger.should_trigger(75.0) is False

    def test_should_trigger_less_than(self):
        """Test threshold trigger with less than operator."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="memory_usage",
            operator=TriggerOperator.LESS_THAN,
            threshold=20.0,
        )
        assert trigger.should_trigger(15.0) is True
        assert trigger.should_trigger(20.0) is False
        assert trigger.should_trigger(25.0) is False

    def test_should_trigger_greater_than_or_equal(self):
        """Test threshold trigger with greater than or equal operator."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="disk_usage",
            operator=TriggerOperator.GREATER_THAN_OR_EQUAL,
            threshold=90.0,
        )
        assert trigger.should_trigger(95.0) is True
        assert trigger.should_trigger(90.0) is True
        assert trigger.should_trigger(85.0) is False

    def test_should_trigger_less_than_or_equal(self):
        """Test threshold trigger with less than or equal operator."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="battery",
            operator=TriggerOperator.LESS_THAN_OR_EQUAL,
            threshold=10.0,
        )
        assert trigger.should_trigger(5.0) is True
        assert trigger.should_trigger(10.0) is True
        assert trigger.should_trigger(15.0) is False

    def test_should_trigger_equal(self):
        """Test threshold trigger with equal operator."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="temperature",
            operator=TriggerOperator.EQUAL,
            threshold=100.0,
        )
        assert trigger.should_trigger(100.0) is True
        assert trigger.should_trigger(99.0) is False
        assert trigger.should_trigger(101.0) is False

    def test_should_trigger_not_equal(self):
        """Test threshold trigger with not equal operator."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="status",
            operator=TriggerOperator.NOT_EQUAL,
            threshold=0.0,
        )
        assert trigger.should_trigger(1.0) is True
        assert trigger.should_trigger(0.0) is False
        assert trigger.should_trigger(-1.0) is True

    def test_should_trigger_disabled(self):
        """Test disabled trigger does not fire."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
            enabled=False,
        )
        assert trigger.should_trigger(100.0) is False

    def test_should_trigger_missing_operator(self):
        """Test trigger without operator does not fire."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            threshold=80.0,
        )
        assert trigger.should_trigger(100.0) is False

    def test_should_schedule_first_time(self):
        """Test schedule trigger fires on first check."""
        trigger = EventTrigger(
            trigger_type=TriggerType.SCHEDULE,
            metric_name="daily_report",
            schedule_interval_seconds=3600,
        )
        now = datetime.now(timezone.utc)
        assert trigger.should_schedule(now) is True

    def test_should_schedule_after_interval(self):
        """Test schedule trigger fires after interval."""
        trigger = EventTrigger(
            trigger_type=TriggerType.SCHEDULE,
            metric_name="daily_report",
            schedule_interval_seconds=3600,
        )
        trigger.last_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=3700)
        now = datetime.now(timezone.utc)
        assert trigger.should_schedule(now) is True

    def test_should_schedule_before_interval(self):
        """Test schedule trigger does not fire before interval."""
        trigger = EventTrigger(
            trigger_type=TriggerType.SCHEDULE,
            metric_name="daily_report",
            schedule_interval_seconds=3600,
        )
        trigger.last_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=1800)
        now = datetime.now(timezone.utc)
        assert trigger.should_schedule(now) is False

    def test_should_schedule_disabled(self):
        """Test disabled schedule trigger does not fire."""
        trigger = EventTrigger(
            trigger_type=TriggerType.SCHEDULE,
            metric_name="daily_report",
            schedule_interval_seconds=3600,
            enabled=False,
        )
        now = datetime.now(timezone.utc)
        assert trigger.should_schedule(now) is False


class TestTriggerEngine:
    """Test TriggerEngine class."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock orchestrator."""
        class MockOrchestrator:
            async def process_task(self, task: Task) -> None:
                pass
        return MockOrchestrator()

    @pytest.fixture
    def trace_emitter(self):
        """Create a memory trace emitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def trigger_engine(self, mock_orchestrator, trace_emitter):
        """Create a trigger engine."""
        return TriggerEngine(orchestrator=mock_orchestrator, emitter=trace_emitter)

    @pytest.mark.asyncio
    async def test_register_trigger(self, trigger_engine):
        """Test registering a trigger."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        await trigger_engine.register(trigger)
        assert trigger.trigger_id in trigger_engine._triggers
        assert trigger_engine._triggers[trigger.trigger_id] == trigger

    @pytest.mark.asyncio
    async def test_unregister_trigger(self, trigger_engine):
        """Test unregistering a trigger."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        await trigger_engine.register(trigger)
        await trigger_engine.unregister(trigger.trigger_id)
        assert trigger.trigger_id not in trigger_engine._triggers

    @pytest.mark.asyncio
    async def test_ingest_metric_fires_trigger(self, trigger_engine, trace_emitter):
        """Test ingesting metric fires threshold trigger."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        await trigger_engine.register(trigger)
        await trigger_engine.ingest_metric("cpu_usage", 85.0)
        assert trigger.trigger_count == 1
        assert trigger.last_triggered_at is not None

    @pytest.mark.asyncio
    async def test_ingest_metric_does_not_fire_below_threshold(self, trigger_engine):
        """Test ingesting metric does not fire when below threshold."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        await trigger_engine.register(trigger)
        await trigger_engine.ingest_metric("cpu_usage", 75.0)
        assert trigger.trigger_count == 0
        assert trigger.last_triggered_at is None

    @pytest.mark.asyncio
    async def test_ingest_metric_stores_history(self, trigger_engine):
        """Test ingesting metric stores history."""
        await trigger_engine.ingest_metric("cpu_usage", 50.0)
        await trigger_engine.ingest_metric("cpu_usage", 60.0)
        await trigger_engine.ingest_metric("cpu_usage", 70.0)
        assert "cpu_usage" in trigger_engine._metric_history
        assert len(trigger_engine._metric_history["cpu_usage"]) == 3
        assert trigger_engine._metric_history["cpu_usage"] == [50.0, 60.0, 70.0]

    @pytest.mark.asyncio
    async def test_ingest_metric_limits_history_size(self, trigger_engine):
        """Test metric history is limited to 100 values."""
        for i in range(150):
            await trigger_engine.ingest_metric("cpu_usage", float(i))
        assert len(trigger_engine._metric_history["cpu_usage"]) == 100
        assert trigger_engine._metric_history["cpu_usage"][-1] == 149.0

    @pytest.mark.asyncio
    async def test_evaluate_schedule_triggers(self, trigger_engine):
        """Test evaluating schedule triggers."""
        trigger = EventTrigger(
            trigger_type=TriggerType.SCHEDULE,
            metric_name="daily_report",
            schedule_interval_seconds=1,
        )
        await trigger_engine.register(trigger)
        await trigger_engine.evaluate_schedule_triggers()
        assert trigger.trigger_count == 1
        assert trigger.last_triggered_at is not None

    @pytest.mark.asyncio
    async def test_build_task_for_threshold_trigger(self, trigger_engine):
        """Test building task from threshold trigger."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        context = {"metric_value": 85.0}
        task = trigger_engine.build_task(trigger, context)
        assert isinstance(task, Task)
        assert "cpu_usage" in task.intent
        assert "80.0" in task.intent
        assert "85.0" in task.intent

    @pytest.mark.asyncio
    async def test_build_task_for_schedule_trigger(self, trigger_engine):
        """Test building task from schedule trigger."""
        trigger = EventTrigger(
            trigger_type=TriggerType.SCHEDULE,
            metric_name="daily_report",
            schedule_interval_seconds=3600,
        )
        context = {"scheduled_time": datetime.now(timezone.utc).isoformat()}
        task = trigger_engine.build_task(trigger, context)
        assert isinstance(task, Task)
        assert "daily_report" in task.intent
        assert "scheduled time" in task.intent

    @pytest.mark.asyncio
    async def test_register_emits_trace_event(self, trigger_engine, trace_emitter):
        """Test registering trigger emits trace event."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        trace_emitter.clear()
        await trigger_engine.register(trigger)
        events = trace_emitter.get_events()
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_unregister_emits_trace_event(self, trigger_engine, trace_emitter):
        """Test unregistering trigger emits trace event."""
        trigger = EventTrigger(
            trigger_type=TriggerType.THRESHOLD,
            metric_name="cpu_usage",
            operator=TriggerOperator.GREATER_THAN,
            threshold=80.0,
        )
        await trigger_engine.register(trigger)
        trace_emitter.clear()
        await trigger_engine.unregister(trigger.trigger_id)
        events = trace_emitter.get_events()
        assert len(events) > 0
