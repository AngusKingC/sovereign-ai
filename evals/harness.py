"""Evaluation harness for offline LLM output evaluation.

This module provides the EvalHarness class for orchestrating evaluation
of LLM outputs against gold-standard responses using configurable metrics.
"""

from datetime import datetime, timezone
from typing import Callable, Optional
from dataclasses import dataclass

from core.observability import TraceEmitter, TraceEvent, TraceEventType, TraceLevel, TraceComponent
from .metrics import (
    compute_exact_match,
    compute_token_f1,
    compute_bleu,
    compute_cosine_similarity,
)


@dataclass
class EvalResult:
    """Single evaluation result.
    
    Attributes:
        predicted: The model's output
        gold: The gold-standard (expected) output
        task_id: Optional identifier for the task
        metrics: Dict mapping metric names to scores (e.g., {"exact_match": 0.0, "token_f1": 0.6, ...})
        timestamp: When the evaluation was performed (UTC)
    """
    predicted: str
    gold: str
    task_id: Optional[str]
    metrics: dict[str, float]
    timestamp: datetime


class EvalHarness:
    """Harness for offline evaluation of LLM outputs.
    
    The harness manages eval state, runs evals against gold-standard responses,
    and accumulates results for summary statistics.
    """

    def __init__(
        self,
        metrics: Optional[dict[str, Callable[[str, str], float]]] = None,
        trace_emitter: Optional[TraceEmitter] = None,
    ) -> None:
        """Initialize the eval harness.
        
        Args:
            metrics: Dict mapping metric names to callables. Defaults to standard metrics.
            trace_emitter: Optional trace emitter for recording eval events.
        """
        self.trace_emitter = trace_emitter
        self.metrics = metrics or {
            "exact_match": compute_exact_match,
            "token_f1": compute_token_f1,
            "bleu": compute_bleu,
            "cosine_similarity": compute_cosine_similarity,
        }
        self.results: list[EvalResult] = []

    async def evaluate(
        self,
        predicted: str,
        gold: str,
        task_id: Optional[str] = None,
    ) -> EvalResult:
        """Evaluate a single prediction against gold standard.
        
        Args:
            predicted: The model's output
            gold: The gold-standard (expected) output
            task_id: Optional identifier for the task
            
        Returns:
            EvalResult with computed metrics
        """
        metrics_scores = {}
        for metric_name, metric_fn in self.metrics.items():
            try:
                score = metric_fn(predicted, gold)
                metrics_scores[metric_name] = score
            except Exception as e:
                # Per AR18: broad except requires inline comment + WARNING trace
                # If a metric fails, record it as 0.0 and log warning
                metrics_scores[metric_name] = 0.0
                if self.trace_emitter:
                    await self._emit_eval_warning(
                        f"Metric {metric_name} failed: {e}",
                        task_id,
                    )

        result = EvalResult(
            predicted=predicted,
            gold=gold,
            task_id=task_id,
            metrics=metrics_scores,
            timestamp=datetime.now(timezone.utc),  # Per OR20
        )
        
        self.results.append(result)
        
        if self.trace_emitter:
            await self._emit_eval_result(result)
        
        return result

    async def evaluate_batch(
        self,
        predictions: list[tuple[str, str]],
        task_ids: Optional[list[str]] = None,
    ) -> list[EvalResult]:
        """Evaluate multiple predictions.
        
        Args:
            predictions: List of (predicted, gold) pairs
            task_ids: Optional list of task identifiers (must match predictions length)
            
        Returns:
            List of EvalResult objects
            
        Raises:
            ValueError: If task_ids length != predictions length
        """
        if task_ids and len(task_ids) != len(predictions):
            raise ValueError("task_ids must match predictions length")
        
        results = []
        for idx, (predicted, gold) in enumerate(predictions):
            task_id = task_ids[idx] if task_ids else None
            result = await self.evaluate(predicted, gold, task_id)
            results.append(result)
        
        return results

    def summary(self) -> dict[str, dict[str, float]]:
        """Compute summary statistics across all eval results.
        
        Returns:
            Dict mapping metric names to stats (mean, min, max, count)
        """
        if not self.results:
            return {}
        
        summary = {}
        metric_names: set[str] = set()
        for result in self.results:
            metric_names.update(result.metrics.keys())
        
        for metric_name in metric_names:
            scores = [r.metrics[metric_name] for r in self.results if metric_name in r.metrics]
            if scores:
                summary[metric_name] = {
                    "mean": sum(scores) / len(scores),
                    "min": min(scores),
                    "max": max(scores),
                    "count": len(scores),
                }
        
        return summary

    async def _emit_eval_result(self, result: EvalResult) -> None:
        """Emit trace event for eval result."""
        if not self.trace_emitter:
            return
        
        event = TraceEvent(
            event_type=TraceEventType.EVAL_COMPLETE,
            level=TraceLevel.INFO,
            component=TraceComponent.SYSTEM,
            message=f"Eval complete: {result.task_id or 'unknown'}",
            data={
                "task_id": result.task_id,
                "metrics": result.metrics,
            },
        )
        await self.trace_emitter.emit(event)

    async def _emit_eval_warning(
        self,
        message: str,
        task_id: Optional[str],
    ) -> None:
        """Emit warning trace event."""
        if not self.trace_emitter:
            return
        
        event = TraceEvent(
            event_type=TraceEventType.EVAL_WARNING,
            level=TraceLevel.WARNING,
            component=TraceComponent.SYSTEM,
            message=message,
            data={"task_id": task_id},
        )
        await self.trace_emitter.emit(event)
