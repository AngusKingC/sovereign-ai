"""
Event Trigger System

Single responsibility: Manage event-based task triggers for the MonitorDaemon.
Supports threshold, schedule, and change triggers to automatically create tasks.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from core.observability import (
    TraceComponent,
    TraceEmitter,
    MemoryTraceEmitter,
    TraceEventType,
    TraceLevel,
    TraceEvent,
)
from core.schemas import Task, TaskPriority

if TYPE_CHECKING:
    from core.orchestrator import Orchestrator


class TriggerType(str, Enum):
    """Types of event triggers."""
    THRESHOLD = "threshold"  # Trigger when metric crosses threshold
    SCHEDULE = "schedule"  # Trigger at specific time or interval
    CHANGE = "change"  # Trigger when metric changes significantly


class TriggerOperator(str, Enum):
    """Comparison operators for threshold triggers."""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN_OR_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="


class EventTrigger(BaseModel):
    """An event trigger that can create tasks when conditions are met."""

    trigger_id: UUID = Field(default_factory=uuid4, description="Unique trigger identifier")
    trigger_type: TriggerType = Field(description="Type of trigger")
    metric_name: str = Field(description="Name of the metric to monitor")
    operator: TriggerOperator | None = Field(default=None, description="Comparison operator for threshold triggers")
    threshold: float | None = Field(default=None, description="Threshold value for threshold triggers")
    schedule_interval_seconds: int | None = Field(default=None, description="Interval in seconds for schedule triggers")
    enabled: bool = Field(default=True, description="Whether the trigger is enabled")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional trigger metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the trigger was created")
    last_triggered_at: datetime | None = Field(default=None, description="When the trigger last fired")
    trigger_count: int = Field(default=0, description="Number of times the trigger has fired")

    def should_trigger(self, metric_value: float) -> bool:
        """Check if the trigger should fire based on the metric value."""
        if not self.enabled:
            return False

        if self.trigger_type == TriggerType.THRESHOLD:
            if self.operator is None or self.threshold is None:
                return False

            if self.operator == TriggerOperator.GREATER_THAN:
                return metric_value > self.threshold
            elif self.operator == TriggerOperator.LESS_THAN:
                return metric_value < self.threshold
            elif self.operator == TriggerOperator.GREATER_THAN_OR_EQUAL:
                return metric_value >= self.threshold
            elif self.operator == TriggerOperator.LESS_THAN_OR_EQUAL:
                return metric_value <= self.threshold
            elif self.operator == TriggerOperator.EQUAL:
                return metric_value == self.threshold
            elif self.operator == TriggerOperator.NOT_EQUAL:
                return metric_value != self.threshold

        return False

    def should_schedule(self, last_check_time: datetime) -> bool:
        """Check if a schedule trigger should fire based on time."""
        if not self.enabled or self.trigger_type != TriggerType.SCHEDULE:
            return False

        if self.schedule_interval_seconds is None:
            return False

        if self.last_triggered_at is None:
            return True

        time_since_last_trigger = datetime.now(timezone.utc) - self.last_triggered_at
        return time_since_last_trigger.total_seconds() >= self.schedule_interval_seconds


class TriggerEngine:
    """Manages event triggers and evaluates them to create tasks."""

    def __init__(
        self,
        orchestrator: "Orchestrator",
        emitter: "TraceEmitter | None" = None,
    ) -> None:
        """Initialize the trigger engine with an orchestrator.

        Args:
            orchestrator: The orchestrator to use for creating tasks
            emitter: Trace emitter for events
        """
        self.orchestrator = orchestrator
        self._emitter = emitter or MemoryTraceEmitter()
        self._triggers: dict[UUID, EventTrigger] = {}
        self._metric_history: dict[str, list[float]] = {}

    async def register(self, trigger: EventTrigger) -> None:
        """Register a new event trigger.

        Args:
            trigger: The trigger to register
        """
        self._triggers[trigger.trigger_id] = trigger

        try:
            event = TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message=f"Trigger registered: {trigger.trigger_id} ({trigger.trigger_type.value})",
                data={
                    "trigger_id": str(trigger.trigger_id),
                    "trigger_type": trigger.trigger_type.value,
                    "metric_name": trigger.metric_name,
                },
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

    async def unregister(self, trigger_id: UUID) -> None:
        """Unregister an event trigger.

        Args:
            trigger_id: The ID of the trigger to unregister
        """
        if trigger_id in self._triggers:
            del self._triggers[trigger_id]

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.INFO,
                    message=f"Trigger unregistered: {trigger_id}",
                    data={
                        "trigger_id": str(trigger_id),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

    async def ingest_metric(self, metric_name: str, value: float) -> None:
        """Ingest a metric value and evaluate triggers.

        Args:
            metric_name: Name of the metric
            value: Value of the metric
        """
        # Store metric history for change detection
        if metric_name not in self._metric_history:
            self._metric_history[metric_name] = []
        self._metric_history[metric_name].append(value)

        # Keep only last 100 values
        if len(self._metric_history[metric_name]) > 100:
            self._metric_history[metric_name] = self._metric_history[metric_name][-100:]

        # Evaluate threshold triggers
        for trigger in self._triggers.values():
            if trigger.metric_name == metric_name and trigger.trigger_type == TriggerType.THRESHOLD:
                if trigger.should_trigger(value):
                    await self._handle_trigger_firing(trigger, {"metric_value": value})

    async def evaluate_schedule_triggers(self) -> None:
        """Evaluate all schedule triggers and fire if needed."""
        now = datetime.now(timezone.utc)

        for trigger in self._triggers.values():
            if trigger.trigger_type == TriggerType.SCHEDULE:
                if trigger.should_schedule(now):
                    await self._handle_trigger_firing(trigger, {"scheduled_time": now.isoformat()})

    async def _handle_trigger_firing(self, trigger: EventTrigger, context: dict[str, Any]) -> None:
        """Handle a trigger firing by creating a task.

        Args:
            trigger: The trigger that fired
            context: Additional context about the trigger firing
        """
        # Update trigger state
        trigger.last_triggered_at = datetime.now(timezone.utc)
        trigger.trigger_count += 1

        # Build and submit task
        task = self.build_task(trigger, context)

        try:
            await self.orchestrator.process_task(task)

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.INFO,
                    message=f"Trigger fired and task created: {trigger.trigger_id}",
                    data={
                        "trigger_id": str(trigger.trigger_id),
                        "task_id": str(task.task_id),
                        "trigger_count": trigger.trigger_count,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.ERROR,
                    message=f"Failed to create task from trigger: {trigger.trigger_id}",
                    data={
                        "trigger_id": str(trigger.trigger_id),
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass

    def build_task(self, trigger: EventTrigger, context: dict[str, Any]) -> Task:
        """Build a task from a trigger firing.

        Args:
            trigger: The trigger that fired
            context: Additional context about the trigger firing

        Returns:
            A task to be processed by the orchestrator
        """
        intent = f"Trigger fired: {trigger.metric_name}"

        if trigger.trigger_type == TriggerType.THRESHOLD:
            metric_value = context.get("metric_value", 0)
            intent += f" crossed threshold {trigger.threshold} (current: {metric_value})"
        elif trigger.trigger_type == TriggerType.SCHEDULE:
            scheduled_time = context.get("scheduled_time", datetime.now(timezone.utc).isoformat())
            intent += f" at scheduled time {scheduled_time}"

        return Task(
            task_id=uuid4(),
            intent=intent,
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            current_state="received",
            created_at=datetime.now(timezone.utc),
        )
