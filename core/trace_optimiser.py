"""
Trace-based skill optimiser for instruction updates.

Analyzes trace events to compute worker performance scores and triggers
instruction updates when scores fall below threshold. Complements the
rating-trend trigger from Prompt 20 with a continuous trace-scoring path.
"""

import logging

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
from core.schemas import VersionUpdateProposal

logger = logging.getLogger(__name__)


class TraceOptimiser:
    """Analyses trace events to trigger instruction updates based on performance scores."""

    def __init__(
        self,
        memory_router: MemoryRouter,
        instruction_version_manager: InstructionVersionManager,
        emitter: TraceEmitter | None = None,
        trace_threshold: float = 0.65,
        min_traces: int = 10,
    ):
        """Initialize trace optimiser.

        Args:
            memory_router: MemoryRouter for reading trace events
            instruction_version_manager: InstructionVersionManager for triggering updates
            emitter: TraceEmitter for observability (defaults to MemoryTraceEmitter)
            trace_threshold: Trigger update if score is below this value
            min_traces: Minimum traces required before scoring
        """
        self.memory_router = memory_router
        self.instruction_version_manager = instruction_version_manager
        self.emitter = emitter if emitter is not None else MemoryTraceEmitter()
        self.trace_threshold = trace_threshold
        self.min_traces = min_traces

    async def score_recent_traces(self, worker_id: str, n: int = 50) -> float:
        """Reads the last n trace events for worker_id and computes a composite trace score.

        Args:
            worker_id: Worker identifier
            n: Number of recent traces to analyse (default 50)

        Returns:
            Composite trace score between 0.0 and 1.0. Returns 1.0 if fewer than
            min_traces traces exist (fail safe — do not trigger spurious updates).
        """
        try:
            # Fetch recent traces for this worker
            traces = await self.memory_router.fetch_by_filter(
                filter={"worker_id": worker_id}, collection="traces", limit=n
            )

            # If fewer than min_traces traces exist, return 1.0 (not enough data)
            if len(traces) < self.min_traces:
                return 1.0

            # Extract trace events from memory router format
            trace_events = []
            for trace in traces:
                content = trace.get("content", {})
                if isinstance(content, dict):
                    trace_events.append(content)

            if len(trace_events) == 0:
                return 1.0

            # Compute tool call success rate
            tool_call_events = [
                e
                for e in trace_events
                if isinstance(e, dict)
                and isinstance(e.get("event_type"), str)
                and (
                    "tool_call" in e["event_type"]
                    or "skill_call" in e["event_type"]
                    or "mcp_tool_call" in e["event_type"]
                )
            ]

            if len(tool_call_events) == 0:
                # No tool call events — use neutral score
                success_rate = 0.5
            else:
                successful = sum(
                    1
                    for e in tool_call_events
                    if isinstance(e.get("level"), str) and e["level"].lower() == "info"
                )
                success_rate = successful / len(tool_call_events)

            # Compute error penalty
            error_events = [
                e
                for e in trace_events
                if isinstance(e, dict)
                and isinstance(e.get("level"), str)
                and e["level"].lower() == "error"
            ]
            error_penalty = min(len(error_events) / len(trace_events), 1.0)

            # Composite score: 70% success rate, 30% (1 - error penalty)
            score = (success_rate * 0.7) + ((1.0 - error_penalty) * 0.3)

            # Clamp to [0.0, 1.0]
            score = max(0.0, min(1.0, score))

            # Emit trace event
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.TRACE_SCORE_COMPUTED,
                        component=TraceComponent.TRACE_OPTIMISER,
                        level=TraceLevel.INFO,
                        message=f"Trace score for worker {worker_id}: {score:.2f}",
                        data={"worker_id": worker_id, "score": score, "n_traces": n},
                        duration_ms=0,
                    )
                )
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)

            return score

        except Exception:
            # Fail safe — return 1.0 on read failures to avoid spurious updates
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.TRACE_OPTIMISER,
                        level=TraceLevel.ERROR,
                        message=f"Failed to compute trace score for worker {worker_id}",
                        data={"worker_id": worker_id},
                        duration_ms=0,
                    )
                )
            except Exception as e2:
                logger.warning("Trace emission failed: %s", e2)
            return 1.0

    async def check_and_trigger_update(
        self, worker_id: str
    ) -> VersionUpdateProposal | None:
        """Checks trace score and triggers instruction update if below threshold.

        Args:
            worker_id: Worker identifier

        Returns:
            VersionUpdateProposal if update triggered, None otherwise
        """
        try:
            # Compute trace score
            score = await self.score_recent_traces(worker_id)

            # If score is at or above threshold, no update needed
            if score >= self.trace_threshold:
                return None

            # Score is below threshold — trigger update
            try:
                # Create a mock profile for the instruction version manager
                from core.worker_factory import DynamicWorkerProfile

                profile = DynamicWorkerProfile(
                    worker_id=worker_id,
                    worker_type="specialist",
                    name=f"Worker {worker_id}",
                    description="Auto-generated profile for trace-based update",
                    purpose="Instruction update triggered by trace optimiser",
                    capabilities=[],
                    preferred_models=[],
                    performance_score=0.0,
                )

                # Call instruction version manager
                proposal = (
                    await self.instruction_version_manager.check_and_trigger_update(
                        profile
                    )
                )

                # Emit trace event
                try:
                    await self.emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.TRACE_UPDATE_TRIGGERED,
                            component=TraceComponent.TRACE_OPTIMISER,
                            level=TraceLevel.INFO,
                            message=f"Trace score below threshold for worker {worker_id} — update triggered",
                            data={
                                "worker_id": worker_id,
                                "score": score,
                                "threshold": self.trace_threshold,
                            },
                            duration_ms=0,
                        )
                    )
                except Exception as e:
                    logger.warning("Trace emission failed: %s", e)

                return proposal

            except Exception:
                # Fail silently on trigger failures
                try:
                    await self.emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.TRACE_OPTIMISER,
                            level=TraceLevel.ERROR,
                            message=f"Failed to trigger update for worker {worker_id}",
                            data={"worker_id": worker_id, "score": score},
                            duration_ms=0,
                        )
                    )
                except Exception as e2:
                    logger.warning("Trace emission failed: %s", e2)
                return None

        except Exception:
            # Fail silently on score computation failures
            return None
