"""
PEMADS Phase 2: Expert Panel Manager

Manages a pool of expert workers for multi-round debates. Each expert proposes
a solution, critiques others' solutions, and iterates. Debates are persisted
via DebatePool. VRAM is managed via VRAMManager (which wraps ResourceManager — hot-swap models in/out).

Integration:
- TaskClassifier: determines if a task is debate-worthy (COMPLEX complexity)
- ModelTierRouter: selects expert models based on task type
- VRAMManager: ensures models loaded before debate, releases after (wraps ResourceManager)
- DebatePool: persists solutions, critiques, scores
- WorkerCircuitBreaker: tracks expert failures, opens circuit if an expert repeatedly fails
- CostTracker: records debate costs (multiple experts × multiple rounds)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from core.cost_tracker import CostTracker
from core.model_tier_router import ModelTierRouter, TaskComplexity
from core.schemas import Task
from core.task_classifier import TaskClassifier, TaskType
from core.vram_manager import VRAMManager
from core.worker_base import LLMAdapter, WorkerBase
from core.worker_circuit_breaker import WorkerCircuitBreaker
from memory.debate_pool import DebatePool, DebateTask, ExpertCritique, ExpertSolution

logger = logging.getLogger(__name__)


class ExpertPanelManager:
    """Manages expert panel debates for PEMADS Phase 2.

    Expert pool is configured at init time. Each expert has:
    - worker_id: unique identifier
    - adapter: LLMAdapter instance (e.g., PrismLlamaAdapter, OpenAIAdapter)
    - worker: WorkerBase instance wrapping the adapter
    - specialty: task type this expert excels at (for routing)
    """

    def __init__(
        self,
        debate_pool: DebatePool,
        task_classifier: TaskClassifier,
        model_tier_router: ModelTierRouter,
        vram_manager: VRAMManager,
        circuit_breaker: WorkerCircuitBreaker,
        cost_tracker: CostTracker,
        emitter: Optional[Any] = None,
        max_rounds: int = 3,
        max_experts: int = 3,
    ) -> None:
        self._debate_pool = debate_pool
        self._classifier = task_classifier
        self._router = model_tier_router
        self._vram_manager = vram_manager
        self._circuit_breaker = circuit_breaker
        self._cost_tracker = cost_tracker
        self._emitter = emitter
        self._max_rounds = max_rounds
        self._max_experts = max_experts
        self._experts: dict[str, ExpertConfig] = {}  # worker_id -> config

    def register_expert(
        self,
        worker_id: str,
        adapter: LLMAdapter,
        worker: WorkerBase,
        specialty: str = TaskType.SCRIPT,
    ) -> None:
        """Register an expert worker in the panel pool."""
        self._experts[worker_id] = ExpertConfig(
            worker_id=worker_id,
            adapter=adapter,
            worker=worker,
            specialty=specialty,
        )
        self._circuit_breaker.register_worker(worker_id)
        logger.info(f"Registered expert '{worker_id}' (specialty: {specialty})")

    async def should_debate(self, task: Task) -> bool:
        """Determine if a task warrants a debate (COMPLEX complexity)."""
        complexity = self._router.classify(task)
        return complexity == TaskComplexity.COMPLEX

    async def run_debate(self, task: Task) -> str:
        """Run a multi-round debate. Returns the debate task_id.

        Steps:
        1. Classify task type
        2. Select N experts (diverse specialties, circuit-breaker available)
        3. Ensure models loaded (VRAM)
        4. For each round:
           a. Each expert proposes a solution
           b. Each expert critiques others' solutions
           c. Persist solutions + critiques to DebatePool
        5. Release models (VRAM)
        6. Return debate task_id for Judge to evaluate (Plan 88)
        """
        classification = self._classifier.classify(task.intent)

        # Create debate pool
        debate_task = DebateTask(
            task_id=f"debate-{task.task_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            prompt=task.intent,
            task_type=classification.task_type,
            created_at=datetime.now(timezone.utc),
        )
        self._debate_pool.create_pool(debate_task)

        # Select experts (diverse, available)
        selected = self._select_experts(classification.task_type, self._max_experts)
        if len(selected) < 2:
            logger.warning(
                f"Debate requires 2+ experts, only {len(selected)} available"
            )
            return debate_task.task_id  # No debate possible

        # Ensure models loaded (VRAM hot-swap via VRAMManager)
        # Rev2 H11 fix — load ALL experts ONCE before debate, not once per expert in a loop.
        # The original code called ensure_expert_models inside a for loop, which
        # would load all experts N times (once per loop iteration).
        try:
            await self._vram_manager.ensure_expert_models([e.adapter for e in selected])
            for expert in selected:
                self._circuit_breaker.record_success(expert.worker_id)
        except Exception as e:
            logger.warning(f"Failed to load expert models: {e}")
            for expert in selected:
                self._circuit_breaker.record_failure(expert.worker_id)

        try:
            # Run debate rounds
            for round_num in range(1, self._max_rounds + 1):
                # Round phase 1: solutions
                solutions = await self._collect_solutions(
                    debate_task.task_id, round_num, selected, task
                )

                # Round phase 2: critiques
                await self._collect_critiques(
                    debate_task.task_id, round_num, selected, solutions
                )

                logger.info(f"Debate {debate_task.task_id} round {round_num} complete")
        finally:
            # Release models (VRAM via VRAMManager)
            try:
                await self._vram_manager.release_expert_models(
                    [expert.adapter for expert in selected]
                )
            except Exception as e:
                logger.warning(f"Failed to release expert models: {e}")

        return debate_task.task_id

    def _select_experts(self, task_type: str, count: int) -> list[ExpertConfig]:
        """Select N diverse experts. Prefer matching specialty, fall back to general."""
        available = [
            e
            for e in self._experts.values()
            if self._circuit_breaker.is_available(e.worker_id)
        ]
        # Sort: matching specialty first, then by worker_id for determinism
        matching = [e for e in available if e.specialty == task_type]
        general = [e for e in available if e.specialty == TaskType.SCRIPT]
        others = [e for e in available if e not in matching and e not in general]

        selected = (matching + general + others)[:count]
        return selected

    async def _collect_solutions(
        self, debate_id: str, round_num: int, experts: list, task: Task
    ) -> list[ExpertSolution]:
        """Each expert proposes a solution."""
        solutions = []
        for expert in experts:
            try:
                # Build prompt with debate history for rounds > 1
                history = ""
                if round_num > 1:
                    history = self._debate_pool.get_debate_history(debate_id)

                # Rev2 H4 fix — use worker.run() not worker.execute().
                # WorkerBase.run(task) is the canonical entry point that enforces
                # the tracing pipeline (MEMORY_QUERY → PROMPT_BUILT → LLM_CALLED → OUTPUT_FINAL).
                # execute() is a legacy compat method that may not exist on all workers.
                # run() accepts a Task object; we construct a minimal Task from the intent.
                from uuid import uuid4

                from core.schemas import Task as TaskSchema
                from core.schemas import TaskPriority

                debate_task = TaskSchema(
                    task_id=uuid4(),
                    intent=(
                        f"{task.intent}\n\nPrevious debate context:\n{history}"
                        if history
                        else task.intent
                    ),
                    complexity_score=0.5,
                    priority=TaskPriority.NORMAL,
                    created_at=datetime.now(timezone.utc),
                )
                solution_code = await expert.worker.run(debate_task)

                sol = ExpertSolution(
                    expert_id=expert.worker_id,
                    expert_name=expert.worker_id,
                    round_number=round_num,
                    solution_code=str(solution_code),
                    generated_at=datetime.now(timezone.utc),
                )
                self._debate_pool.save_solution(debate_id, sol)
                solutions.append(sol)
                self._circuit_breaker.record_success(expert.worker_id)

            except Exception as e:
                logger.warning(
                    f"Expert {expert.worker_id} failed in round {round_num}: {e}"
                )
                self._circuit_breaker.record_failure(expert.worker_id)

        return solutions

    async def _collect_critiques(
        self, debate_id: str, round_num: int, experts: list, solutions: list
    ) -> None:
        """Each expert critiques others' solutions."""
        for critic in experts:
            for sol in solutions:
                if sol.expert_id == critic.worker_id:
                    continue  # Don't critique own solution

                try:
                    # Rev2 H4 fix — use worker.run() not worker.execute()
                    from uuid import uuid4

                    from core.schemas import Task as TaskSchema
                    from core.schemas import TaskPriority

                    critique_task = TaskSchema(
                        task_id=uuid4(),
                        intent=(
                            f"Critique this solution by {sol.expert_id}:\n\n{sol.solution_code}\n\n"
                            f"Identify flaws, suggest improvements."
                        ),
                        complexity_score=0.5,
                        priority=TaskPriority.NORMAL,
                        created_at=datetime.now(timezone.utc),
                    )
                    critique_text = await critic.worker.run(critique_task)

                    critique = ExpertCritique(
                        expert_id=critic.worker_id,
                        expert_name=critic.worker_id,
                        round_number=round_num,
                        target_expert_id=sol.expert_id,
                        critique_text=str(critique_text),
                        generated_at=datetime.now(timezone.utc),
                    )
                    self._debate_pool.save_critique(debate_id, critique)
                    self._circuit_breaker.record_success(critic.worker_id)

                except Exception as e:
                    logger.warning(f"Critique by {critic.worker_id} failed: {e}")
                    self._circuit_breaker.record_failure(critic.worker_id)


@dataclass
class ExpertConfig:
    worker_id: str
    adapter: LLMAdapter
    worker: WorkerBase
    specialty: str
