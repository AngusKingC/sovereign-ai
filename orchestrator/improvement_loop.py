"""Improvement loop wire module - connects eval harness, trace store, and improvement logic.

This is a thin wire layer that connects existing components without adding new logic:
- EvalHarness (evals/) for evaluation
- PostgresTraceStore (memory/) for trace persistence
- OrchestratorImprovementLoop (core/) for improvement decisions
"""

from typing import TYPE_CHECKING, Any

from core.observability import MemoryTraceEmitter, TraceEmitter, TraceEvent, TraceEventType, TraceComponent, TraceLevel
from evals.harness import EvalHarness

if TYPE_CHECKING:
    from core.orchestrator_improvement import OrchestratorImprovementLoop
    from memory import PostgresTraceStore


class ImprovementLoopOrchestrator:
    """Orchestrates the improvement loop by wiring eval harness, trace store, and improvement logic.

    This is a thin wire layer -- all heavy logic lives in existing components:
    - EvalHarness (evals/) for evaluation
    - PostgresTraceStore (memory/) for trace persistence
    - OrchestratorImprovementLoop (core/) for improvement decisions
    """

    def __init__(
        self,
        eval_harness: EvalHarness,
        trace_store: "PostgresTraceStore | None",
        improvement_loop: "OrchestratorImprovementLoop",
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the improvement loop orchestrator.

        Args:
            eval_harness: EvalHarness for running evaluations
            trace_store: PostgresTraceStore for querying task traces (optional, can be None)
            improvement_loop: OrchestratorImprovementLoop for improvement decisions
            emitter: TraceEmitter for observability (defaults to MemoryTraceEmitter)
        """
        self.eval_harness = eval_harness
        self.trace_store = trace_store
        self.improvement_loop = improvement_loop
        self.emitter = emitter if emitter is not None else MemoryTraceEmitter()

    async def process_improvement_task(
        self,
        task_id: str | None = None,
        recent_count: int = 10,
    ) -> dict[str, Any]:
        """Process an improvement task.

        If task_id is provided, evaluate that specific task's traces.
        If task_id is None, evaluate the last `recent_count` tasks from trace store.

        Returns dict with:
        - "eval_results": list of EvalResult
        - "accuracy": float (routing accuracy from improvement loop)
        - "update_triggered": bool (whether instruction update was triggered)
        - "proposal": VersionUpdateProposal | None
        """
        results: dict[str, Any] = {
            "eval_results": [],
            "accuracy": 0.0,
            "update_triggered": False,
            "proposal": None,
        }

        try:
            # Step 1: Query trace store for recent traces
            traces = []
            if self.trace_store is not None:
                if task_id:
                    # Query specific task
                    traces = await self._query_task_traces(task_id)
                else:
                    # Query recent tasks
                    traces = await self._query_recent_traces(recent_count)

            # Step 2: Run eval harness on predicted vs gold outputs
            eval_results = []
            for trace in traces:
                try:
                    # Extract predicted and gold from trace data
                    trace_data = trace.get("data", {})
                    predicted = trace_data.get("predicted", "")
                    gold = trace_data.get("gold", "")
                    trace_task_id = trace_data.get("task_id") or trace.get("task_id")

                    if predicted and gold:
                        result = await self.eval_harness.evaluate(
                            predicted=predicted,
                            gold=gold,
                            task_id=trace_task_id,
                        )
                        eval_results.append(result)

                        # Feed eval results to improvement loop
                        from core.schemas import OrchestratorMetrics
                        metrics = OrchestratorMetrics(
                            task_id=trace_task_id or "unknown",
                            routed_to_worker_id=trace_data.get("worker_id", "unknown"),
                            routing_score=result.metrics.get("token_f1", 0.0),
                            task_completed=True,
                            user_rating=None,
                            timestamp=result.timestamp,
                        )
                        await self.improvement_loop.record_routing_decision(metrics)

                except Exception as e:
                    # Per AR18: log warning, don't crash
                    await self._emit_warning(
                        f"Failed to evaluate trace: {e}",
                        {"trace": trace}
                    )

            results["eval_results"] = eval_results

            # Step 3: Get routing accuracy from improvement loop
            accuracy = await self.improvement_loop.get_routing_accuracy(n=recent_count)
            results["accuracy"] = accuracy

            # Step 4: Check if update needed
            proposal = await self.improvement_loop.check_and_trigger_update()
            if proposal is not None:
                results["update_triggered"] = True
                results["proposal"] = proposal

            # Emit completion trace
            await self._emit_completion(results)

            return results

        except Exception as e:
            # Per AR18: log warning, return partial results
            await self._emit_warning(
                f"Improvement task processing failed: {e}",
                {"task_id": task_id, "recent_count": recent_count}
            )
            return results

    async def _query_task_traces(self, task_id: str) -> list[dict[str, Any]]:
        """Query traces for a specific task.

        Args:
            task_id: Task identifier to query

        Returns:
            List of trace dicts
        """
        if self.trace_store is None:
            return []

        try:
            # Query traces for this task
            # Filter by task_id and event_type EVAL_COMPLETE or OPERATION_COMPLETE
            traces = await self.trace_store.query_traces(
                filters={"task_id": task_id}
            )
            return traces

        except Exception as e:
            await self._emit_warning(
                f"Failed to query task traces: {e}",
                {"task_id": task_id}
            )
            return []

    async def _query_recent_traces(self, count: int) -> list[dict[str, Any]]:
        """Query recent traces from trace store.

        Args:
            count: Number of recent traces to query

        Returns:
            List of trace dicts
        """
        if self.trace_store is None:
            return []

        try:
            # Query recent traces
            # Filter by event_type EVAL_COMPLETE or OPERATION_COMPLETE
            traces = await self.trace_store.query_traces(
                filters={"event_type": ["EVAL_COMPLETE", "OPERATION_COMPLETE"]}
            )
            # Limit results in Python since query_traces doesn't support limit parameter
            return traces[:count] if traces else []

        except Exception as e:
            await self._emit_warning(
                f"Failed to query recent traces: {e}",
                {"count": count}
            )
            return []

    async def _emit_warning(self, message: str, data: dict[str, Any]) -> None:
        """Emit a warning trace event.

        Args:
            message: Warning message
            data: Additional data to include in trace
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                message=message,
                level=TraceLevel.WARNING,
                data=data,
            ))
        except Exception:
            # Per AR18: don't crash if trace emission fails
            pass

    async def _emit_completion(self, results: dict[str, Any]) -> None:
        """Emit a completion trace event.

        Args:
            results: Results dict to include in trace
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                message="Improvement task processing completed",
                level=TraceLevel.INFO,
                data={
                    "eval_count": len(results.get("eval_results", [])),
                    "accuracy": results.get("accuracy"),
                    "update_triggered": results.get("update_triggered"),
                },
            ))
        except Exception:
            # Per AR18: don't crash if trace emission fails
            pass
