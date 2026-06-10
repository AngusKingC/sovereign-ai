"""
LLM-as-Judge automated output evaluator.

Evaluates worker outputs using an LLM to assess task completion, accuracy,
format compliance, and conciseness. Combines with manual ratings to produce
final evaluation records.
"""

import json
from datetime import datetime

from core.worker_base import LLMAdapter
from core.memory_router import MemoryRouter
from core.observability import MemoryTraceEmitter, TraceEmitter, TraceEvent, TraceEventType, TraceComponent, TraceLevel
from core.schemas import EvaluatorScore, EvaluationRecord


class OutputEvaluator:
    """Evaluates worker outputs using LLM-as-Judge approach."""
    
    def __init__(
        self,
        llm_adapter: LLMAdapter,
        memory_router: MemoryRouter,
        evaluator_model: str = "default",
        emitter: TraceEmitter | None = None
    ):
        """Initialize output evaluator.
        
        Args:
            llm_adapter: LLMAdapter for evaluation calls
            memory_router: MemoryRouter for persisting evaluation records
            evaluator_model: Model identifier for the evaluator
            emitter: TraceEmitter for observability (defaults to MemoryTraceEmitter)
        """
        self.llm_adapter = llm_adapter
        self.memory_router = memory_router
        self.evaluator_model = evaluator_model
        self.emitter = emitter if emitter is not None else MemoryTraceEmitter()
    
    async def evaluate_output(
        self,
        task_id: str,
        worker_id: str,
        task_description: str,
        worker_output: str
    ) -> EvaluatorScore:
        """Evaluate worker output using LLM-as-Judge.
        
        Args:
            task_id: Task identifier
            worker_id: Worker identifier
            task_description: Description of the task
            worker_output: Worker's output to evaluate
            
        Returns:
            EvaluatorScore with component scores and composite score
            
        Raises:
            ValueError: If LLM response cannot be parsed as JSON
        """
        # Build evaluation prompt
        prompt = f"""Evaluate the following worker output for the given task.

Task: {task_description}

Worker Output:
{worker_output}

Respond with JSON only (no preamble, no fences) in this exact format:
{{"task_completion": 0.0-1.0, "accuracy": 0.0-1.0, "format_compliance": 0.0-1.0, "conciseness": 0.0-1.0}}

Where:
- task_completion: Did the output address the task? (0.0 = not at all, 1.0 = completely)
- accuracy: Factual/logical correctness (0.0 = incorrect, 1.0 = correct)
- format_compliance: Followed output format instructions (0.0 = not at all, 1.0 = perfectly)
- conciseness: Appropriately brief (0.0 = too verbose, 1.0 = appropriately concise)"""
        
        # Call LLM
        response = await self.llm_adapter.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse JSON response
        content = response.content.strip()
        
        # Strip ```json fences if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            scores = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}")
        
        # Validate required fields
        required_fields = ["task_completion", "accuracy", "format_compliance", "conciseness"]
        for field in required_fields:
            if field not in scores:
                raise ValueError(f"Missing required field in LLM response: {field}")
        
        # Compute composite score
        composite_score = (
            scores["task_completion"] * 0.4 +
            scores["accuracy"] * 0.3 +
            scores["format_compliance"] * 0.2 +
            scores["conciseness"] * 0.1
        )
        
        # Create EvaluatorScore
        evaluator_score = EvaluatorScore(
            task_id=task_id,
            worker_id=worker_id,
            task_completion=scores["task_completion"],
            accuracy=scores["accuracy"],
            format_compliance=scores["format_compliance"],
            conciseness=scores["conciseness"],
            composite_score=composite_score,
            evaluator_model=self.evaluator_model,
            timestamp=datetime.utcnow()
        )
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.EVALUATOR,
                message=f"Output evaluated for task {task_id}",
                level=TraceLevel.INFO,
                data={
                    "task_id": task_id,
                    "worker_id": worker_id,
                    "composite": composite_score
                }
            ))
        except Exception:
            pass
        
        return evaluator_score
    
    async def record_evaluation(
        self,
        evaluator_score: EvaluatorScore | None,
        manual_rating: float | None,
        task_id: str,
        worker_id: str
    ) -> EvaluationRecord:
        """Record an evaluation, combining auto-eval and manual rating.
        
        Args:
            evaluator_score: Auto-eval score if performed
            manual_rating: Manual rating 1-10 if provided
            task_id: Task identifier
            worker_id: Worker identifier
            
        Returns:
            EvaluationRecord with resolved final score
            
        Raises:
            ValueError: If both evaluator_score and manual_rating are None
        """
        # Compute final score
        if manual_rating is not None:
            final_score = manual_rating / 10.0
        elif evaluator_score is not None:
            final_score = evaluator_score.composite_score
        else:
            raise ValueError("Both evaluator_score and manual_rating cannot be None")
        
        # Create EvaluationRecord
        record = EvaluationRecord(
            task_id=task_id,
            worker_id=worker_id,
            evaluator_score=evaluator_score,
            manual_rating=manual_rating,
            final_score=final_score,
            timestamp=datetime.utcnow()
        )
        
        # Persist to memory router
        await self.memory_router.write(
            {
                "type": "evaluation_record",
                "record_id": record.record_id,
                "task_id": record.task_id,
                "worker_id": record.worker_id,
                "evaluator_score": record.evaluator_score.model_dump() if record.evaluator_score else None,
                "manual_rating": record.manual_rating,
                "final_score": record.final_score,
                "timestamp": record.timestamp.isoformat()
            },
            document_id=f"evaluation:{task_id}:{worker_id}"
        )
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.EVALUATOR,
                message=f"Evaluation recorded for task {task_id}",
                level=TraceLevel.INFO,
                data={
                    "task_id": task_id,
                    "final_score": final_score
                }
            ))
        except Exception:
            pass
        
        return record
    
    async def get_worker_evaluations(self, worker_id: str, n: int = 20) -> list[EvaluationRecord]:
        """Get evaluation records for a worker.
        
        Args:
            worker_id: Worker identifier
            n: Number of recent records to retrieve
            
        Returns:
            List of EvaluationRecord objects, empty if none exist
        """
        results = await self.memory_router.fetch(
            {"worker_id": worker_id},
            collection="evaluation_records",
            limit=n
        )
        
        records = []
        for result in results:
            content_data = result.get("content", {})
            try:
                # Reconstruct evaluator_score if present
                evaluator_score = None
                if content_data.get("evaluator_score"):
                    evaluator_score = EvaluatorScore(**content_data["evaluator_score"])
                
                record = EvaluationRecord(
                    record_id=content_data.get("record_id", ""),
                    task_id=content_data.get("task_id", ""),
                    worker_id=content_data.get("worker_id", ""),
                    evaluator_score=evaluator_score,
                    manual_rating=content_data.get("manual_rating"),
                    final_score=content_data.get("final_score", 0.0),
                    timestamp=datetime.fromisoformat(content_data.get("timestamp", datetime.utcnow().isoformat()))
                )
                records.append(record)
            except Exception:
                continue
        
        return records
