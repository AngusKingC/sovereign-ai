"""
Orchestrator improvement loop - self-improvement for the orchestrator.

Wires the orchestrator into the same self-improvement loop that workers now have.
The orchestrator tracks its own performance, proposes instruction updates when routing
quality degrades, and improves via the same InstructionVersionManager mechanism.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from core.instruction_versioning import InstructionVersionManager
from core.memory_router import MemoryRouter
from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)
from core.orchestrator import Orchestrator
from core.schemas import OrchestratorMetrics, VersionUpdateProposal

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class OrchestratorImprovementLoop:
    """Manages orchestrator self-improvement via instruction file updates."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        instruction_version_manager: InstructionVersionManager,
        memory_router: MemoryRouter,
        emitter: TraceEmitter | None = None,
        accuracy_threshold: float = 0.6,
        trend_threshold: float = -0.5,
        min_samples: int = 5,
        min_ratings: int = 3,
    ):
        """Initialize orchestrator improvement loop.

        Args:
            orchestrator: Orchestrator instance to monitor
            instruction_version_manager: InstructionVersionManager for generating updates
            memory_router: MemoryRouter for persisting metrics
            emitter: TraceEmitter for observability (defaults to MemoryTraceEmitter)
            accuracy_threshold: Trigger update if routing accuracy below this
            trend_threshold: Trigger update if rating trend below this
            min_samples: Minimum samples before computing routing accuracy
            min_ratings: Minimum ratings before computing rating trend
        """
        self.orchestrator = orchestrator
        self.instruction_version_manager = instruction_version_manager
        self.memory_router = memory_router
        self.emitter = emitter if emitter is not None else MemoryTraceEmitter()
        self.accuracy_threshold = accuracy_threshold
        self.trend_threshold = trend_threshold
        self.min_samples = min_samples
        self.min_ratings = min_ratings

    async def record_routing_decision(self, metrics: OrchestratorMetrics) -> None:
        """Record a routing decision metric.

        Args:
            metrics: OrchestratorMetrics to persist
        """
        # Persist metrics via MemoryRouter
        await self.memory_router.write_to_collection(
            data={
                "type": "orchestrator_metrics",
                "task_id": metrics.task_id,
                "routed_to_worker_id": metrics.routed_to_worker_id,
                "routing_score": metrics.routing_score,
                "task_completed": metrics.task_completed,
                "user_rating": metrics.user_rating,
                "timestamp": metrics.timestamp.isoformat(),
            },
            collection="orchestrator_metrics",
            document_id=f"orchestrator_metrics:{metrics.task_id}",
        )

        # Emit trace event
        try:
            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    message=f"Orchestrator routing metric recorded for task {metrics.task_id}",
                    level=TraceLevel.INFO,
                    data={
                        "task_id": metrics.task_id,
                        "routed_to": metrics.routed_to_worker_id,
                        "score": metrics.routing_score,
                    },
                )
            )
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)

    async def get_routing_accuracy(self, n: int = 20) -> float:
        """Get routing accuracy over last N routing decisions.

        Args:
            n: Number of recent routing decisions to consider

        Returns:
            Routing accuracy as float 0.0-1.0, or 0.0 if fewer than min_samples records exist
        """
        # Retrieve last N orchestrator metrics
        results = await self.memory_router.fetch_by_filter(
            filter={"type": "orchestrator_metrics"},
            collection="orchestrator_metrics",
            limit=n,
        )

        # Check if we have enough samples
        if len(results) < self.min_samples:
            return 0.0

        # Compute accuracy: proportion of tasks where task_completed == True
        completed_count = 0
        for result in results:
            content = result.get("content", {})
            if content.get("task_completed", False):
                completed_count += 1

        accuracy = completed_count / len(results)
        return accuracy

    async def get_rating_trend(self, n: int = 10) -> float:
        """Get rating trend over last N rated routing decisions.

        Args:
            n: Number of recent rated routing decisions to consider

        Returns:
            Linear trend slope of user_rating values (negative = declining, positive = improving),
            or 0.0 if fewer than min_ratings rated records exist
        """
        # Retrieve last N orchestrator metrics
        results = await self.memory_router.fetch_by_filter(
            filter={"type": "orchestrator_metrics"},
            collection="orchestrator_metrics",
            limit=n * 2,  # Get more to filter for rated ones
        )

        # Filter for records with user_rating
        rated_records = []
        for result in results:
            content = result.get("content", {})
            user_rating = content.get("user_rating")
            if user_rating is not None:
                rated_records.append(user_rating)

        # Check if we have enough rated records
        if len(rated_records) < self.min_ratings:
            return 0.0

        # Take last N rated records
        rated_records = rated_records[-n:]

        # Compute linear trend slope
        # Simple linear regression: y = mx + b
        # m = (N*sum(xy) - sum(x)*sum(y)) / (N*sum(x^2) - (sum(x))^2)
        N = len(rated_records)
        x_values = list(range(N))
        y_values = rated_records

        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)

        denominator = N * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0

        slope = (N * sum_xy - sum_x * sum_y) / denominator
        return slope

    async def check_and_trigger_update(self) -> VersionUpdateProposal | None:
        """Check if orchestrator instruction update is needed and trigger if so.

        Returns:
            VersionUpdateProposal if update triggered, None otherwise
        """
        # Get routing accuracy and rating trend
        accuracy = await self.get_routing_accuracy()
        trend = await self.get_rating_trend()

        # Check if update is needed
        trigger_reason = None
        if accuracy < self.accuracy_threshold:
            trigger_reason = f"routing accuracy {accuracy:.2f} below threshold {self.accuracy_threshold}"
        elif trend < self.trend_threshold:
            trigger_reason = (
                f"rating trend {trend:.2f} below threshold {self.trend_threshold}"
            )

        if not trigger_reason:
            return None

        # Create synthetic orchestrator profile for instruction generation
        from core.worker_factory import DynamicWorkerProfile

        orchestrator_profile = DynamicWorkerProfile(
            worker_id="orchestrator",
            worker_type="orchestrator",
            name="Orchestrator",
            description="Central coordination system",
            purpose="Coordinate workers and manage task routing",
            capabilities=["routing", "coordination", "planning"],
            preferred_models=["qwen2.5-coder:7b"],
            performance_score=accuracy,
        )

        # Trigger update via InstructionVersionManager
        proposal = await self.instruction_version_manager.check_and_trigger_update(
            profile=orchestrator_profile
        )

        # Emit trace event
        try:
            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    message=f"Orchestrator instruction update triggered: {trigger_reason}",
                    level=TraceLevel.INFO,
                    data={
                        "accuracy": accuracy,
                        "trend": trend,
                        "reason": trigger_reason,
                    },
                )
            )
        except Exception as e:
            logger.warning(
                "Trace emission failed: %s", e
            )  # Trace failure should not crash main path

        return proposal

    async def mark_task_completed(self, task_id: str) -> None:
        """Mark a task as completed in orchestrator metrics.

        Args:
            task_id: Task identifier to mark as completed
        """
        # Retrieve the OrchestratorMetrics record for task_id
        document_id = f"orchestrator_metrics:{task_id}"
        result = await self.memory_router.fetch_by_filter(
            filter={"task_id": task_id, "_document_id": document_id}, limit=1
        )

        if not result:
            # No record found, emit warning trace and return silently
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.ORCHESTRATOR,
                        message=f"No orchestrator metrics found for task {task_id}",
                        level=TraceLevel.WARNING,
                        data={"task_id": task_id},
                    )
                )
            except Exception as e:
                logger.warning(
                    "Trace emission failed: %s", e
                )  # Trace failure should not crash main path
            return

        # Update task_completed to True
        metrics_data = result[0].get("content", {})
        metrics_data["task_completed"] = True
        metrics_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Persist the updated record
        await self.memory_router.write_to_collection(
            data=metrics_data,
            collection="orchestrator_metrics",
            document_id=document_id,
        )

        # Emit trace event
        try:
            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    message=f"Task {task_id} marked as completed",
                    level=TraceLevel.INFO,
                    data={"task_id": task_id},
                )
            )
        except Exception as e:
            logger.warning(
                "Trace emission failed: %s", e
            )  # Trace failure should not crash main path
