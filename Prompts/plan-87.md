# Plan 87 — PEMADS Phase 2: Expert Panel Manager + VRAM Hot-Swap

**Tag**: `prompt-87` | **Depends on**: `prompt-86`

### Scope

Build `ExpertPanelManager` — manages a pool of expert workers for PEMADS debates. Build `VRAMManager` — tracks VRAM usage and hot-swaps models in/out (standalone wrapper around `system.resource_manager.ResourceManager`). Integrate with existing `WorkerCircuitBreaker`, `ModelTierRouter`, `VRAMManager`, `DebatePool`, and `TaskClassifier`. Wire into `Orchestrator` via Optional injection (following the established pattern).

### S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-86` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for PEMADS vocabulary.
S0.3. No new AGENTS.md rules this prompt.

### S1. Create `core/expert_panel_manager.py`

`ExpertPanelManager` orchestrates multi-round debates using a pool of expert workers. Each expert is a `WorkerBase` instance backed by a different LLM adapter (diversity of architectures).

```python
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
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from core.schemas import Task
from core.task_classifier import TaskClassifier, TaskType
from core.model_tier_router import ModelTierRouter, TaskComplexity
from core.worker_circuit_breaker import WorkerCircuitBreaker
from core.cost_tracker import CostTracker
from core.worker_base import WorkerBase, LLMAdapter
from core.vram_manager import VRAMManager
from memory.debate_pool import DebatePool, DebateTask, ExpertSolution, ExpertCritique

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
            logger.warning(f"Debate requires 2+ experts, only {len(selected)} available")
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
                await self._vram_manager.release_expert_models([expert.adapter for expert in selected])
            except Exception as e:
                logger.warning(f"Failed to release expert models: {e}")

        return debate_task.task_id

    def _select_experts(self, task_type: str, count: int) -> list[ExpertConfig]:
        """Select N diverse experts. Prefer matching specialty, fall back to general."""
        available = [
            e for e in self._experts.values()
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
                from core.schemas import Task as TaskSchema
                debate_task = TaskSchema(
                    task_id=f"{debate_id}-r{round_num}-{expert.worker_id}",
                    intent=f"{task.intent}\n\nPrevious debate context:\n{history}" if history else task.intent,
                    session_id=getattr(task, 'session_id', 'debate'),
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
                logger.warning(f"Expert {expert.worker_id} failed in round {round_num}: {e}")
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
                    from core.schemas import Task as TaskSchema
                    critique_task = TaskSchema(
                        task_id=f"{debate_id}-r{round_num}-critique-{critic.worker_id}",
                        intent=(
                            f"Critique this solution by {sol.expert_id}:\n\n{sol.solution_code}\n\n"
                            f"Identify flaws, suggest improvements."
                        ),
                        session_id="debate",
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


from dataclasses import dataclass

@dataclass
class ExpertConfig:
    worker_id: str
    adapter: LLMAdapter
    worker: WorkerBase
    specialty: str
```

### S2. Create `core/vram_manager.py` (standalone — NOT a wrapper around MultiWorkerDispatcher)

**Post-scan note**: Plan 85 removed `resource_manager` from `MultiWorkerDispatcher` (was unused, caused test failures). `VRAMManager` is now a **standalone component** that `ExpertPanelManager` calls directly. It wraps `system.resource_manager.ResourceManager` (which still exists and is fully built — 1229 lines).

Thin wrapper that adds PEMADS-specific VRAM tracking:

```python
"""
VRAM Manager — PEMADS Phase 2 wrapper around ResourceManager.

Tracks VRAM usage across expert panel debates. Provides:
- ensure_expert_models(experts): load all expert models before debate
- release_expert_models(experts): release after debate
- get_vram_status(): current VRAM usage for UI consumption
"""

from __future__ import annotations
import logging
from typing import Any, Optional

from system.resource_manager import ResourceManager
from core.worker_base import LLMAdapter

logger = logging.getLogger(__name__)


class VRAMManager:
    def __init__(self, resource_manager: ResourceManager, emitter: Optional[Any] = None) -> None:
        self._rm = resource_manager
        self._emitter = emitter
        self._debate_loaded: set[str] = set()  # model_names currently loaded for debate

    async def ensure_expert_models(self, adapters: list[LLMAdapter]) -> None:
        """Load all expert models. Best-effort — failures are logged, not raised."""
        for adapter in adapters:
            try:
                await self._rm.ensure_model(adapter)
                self._debate_loaded.add(adapter.model_name)
            except Exception as e:
                logger.warning(f"Failed to load {adapter.model_name}: {e}")

    async def release_expert_models(self, adapters: list[LLMAdapter]) -> None:
        """Release all expert models after debate."""
        for adapter in adapters:
            try:
                await self._rm.release_model(adapter)
                self._debate_loaded.discard(adapter.model_name)
            except Exception as e:
                logger.warning(f"Failed to release {adapter.model_name}: {e}")

    async def get_vram_status(self) -> dict[str, Any]:
        """Return VRAM status for UI consumption."""
        loaded = await self._rm.get_loaded_models()
        return {
            "loaded_models": [
                {"model_id": m.model_id, "size_mb": m.size_mb, "is_pinned": m.is_pinned}
                for m in loaded
            ],
            "debate_loaded": list(self._debate_loaded),
            "loaded_count": len(loaded),
        }
```

### S3. Add API endpoints to `web/server.py`

```python
@app.get("/api/vram/status")
async def vram_status():
    if not orchestrator.vram_manager:
        return {"loaded_models": [], "debate_loaded": [], "loaded_count": 0}
    return await orchestrator.vram_manager.get_vram_status()

@app.get("/api/debates/{debate_id}")
async def get_debate(debate_id: str):
    if not orchestrator.expert_panel_manager:
        return {"error": "PEMADS not configured"}, 404
    # Return debate history from DebatePool
    history = orchestrator.debate_pool.get_debate_history(debate_id)
    return {"debate_id": debate_id, "history": history}
```

### S4. Wire into `core/orchestrator.py`

**Post-scan note**: Plan 85 removed `resource_manager` from `MultiWorkerDispatcher`. The `ExpertPanelManager` now calls `VRAMManager` directly (which wraps `system.resource_manager.ResourceManager`). The orchestrator injects `VRAMManager` into `ExpertPanelManager` at construction.

Add optional injection (following established pattern at lines 48-64):

```python
# In __init__ signature:
expert_panel_manager: Optional["ExpertPanelManager"] = None,
vram_manager: Optional["VRAMManager"] = None,
debate_pool: Optional["DebatePool"] = None,

# In __init__ body:
self.expert_panel_manager = expert_panel_manager
self.vram_manager = vram_manager
self.debate_pool = debate_pool
```

Add debate trigger in `_execute_task` (after model routing, before execution):

```python
# Check if task should be debated (PEMADS Phase 2)
if self.expert_panel_manager and await self.expert_panel_manager.should_debate(task):
    logger.info(f"Task {task.task_id} flagged for PEMADS debate")
    debate_id = await self.expert_panel_manager.run_debate(task)
    # Store debate_id for Plan 88 Judge to pick up
    task.metadata = task.metadata or {}
    task.metadata["debate_id"] = debate_id
    # For now, proceed with normal execution after debate
    # Plan 88 will add Judge + ImplementationGate to evaluate debate results
```

### S5. Add tests

Create `tests/test_expert_panel_manager.py`:
- test_register_expert
- test_should_debate_complex_task
- test_should_not_debate_simple_task
- test_run_debate_single_round
- test_run_debate_multi_round
- test_expert_failure_triggers_circuit_breaker
- test_vram_ensure_and_release (verify VRAMManager.ensure_expert_models/release_expert_models called — NOT MultiWorkerDispatcher.resource_manager which was removed in Plan 85)
- test_select_experts_prefers_matching_specialty
- test_select_experts_falls_back_to_general
- test_debate_pool_persists_solutions_and_critiques

Minimum 10 tests.

### S6. Verify build

```powershell
ruff check core/expert_panel_manager.py core/vram_manager.py
mypy core/expert_panel_manager.py core/vram_manager.py core/orchestrator.py --ignore-missing-imports
pytest tests/test_expert_panel_manager.py -v
pytest tests/ -q --tb=short | Select-Object -Last 5
```

### STOP condition

If mypy reports errors in new files, STOP and fix. If any test fails, STOP and fix.

### Files WILL create (3)
- `core/expert_panel_manager.py`
- `core/vram_manager.py`
- `tests/test_expert_panel_manager.py`

### Files WILL edit (2)
- `core/orchestrator.py` (add expert_panel_manager, vram_manager, debate_pool injection + debate trigger)
- `web/server.py` (add /api/vram/status and /api/debates/{id} endpoints)

### Files will NOT edit
- `memory/debate_pool.py` (use as-is — Phase 1 complete)
- `core/task_classifier.py` (use as-is)
- `core/model_tier_router.py` (use as-is)
- `core/worker_circuit_breaker.py` (use as-is)
- `system/resource_manager.py` (use as-is — VRAMManager wraps it)
- `adapters/` (use as-is)
- `src/` (no frontend changes this plan)

### Closing

Run `/jarvis-close`. Tag `prompt-87`. CHANGELOG entry for Plan 87. Update PLANS.md.

---
