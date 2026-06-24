"""
Debate Pool — persistent storage for PEMADS debate history.

Single responsibility: Store and retrieve debate artifacts (solutions,
critiques, scores, feedback) across rounds. No LLM calls — pure data.

Per PEMADS spec section 4.2. AR3 compliant (memory/ imports from core/ only).
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.observability import MemoryTraceEmitter, TraceEmitter

logger = logging.getLogger(__name__)


@dataclass
class DebateTask:
    """Original task metadata."""

    task_id: str
    prompt: str
    task_type: str  # "game", "ai_agent", "data_pipeline", "api_backend", "script"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExpertSolution:
    """A single expert's solution for a round."""

    expert_id: str
    expert_name: str
    round_number: int
    solution_code: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExpertCritique:
    """A single expert's critique of other solutions."""

    expert_id: str
    expert_name: str
    round_number: int
    target_expert_id: str
    critique_text: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class JudgeScore:
    """Judge's score for a single solution in a round."""

    round_number: int
    expert_id: str
    scores: dict[str, float]  # {"mypy": 10.0, "pytest": 8.5, ...}
    quality_pct: float
    feedback: str
    scored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DebateRound:
    """A complete debate round (solutions + critiques + scores)."""

    round_number: int
    solutions: list[ExpertSolution] = field(default_factory=list)
    critiques: list[ExpertCritique] = field(default_factory=list)
    scores: list[JudgeScore] = field(default_factory=list)


class DebatePool:
    """Persistent storage for debate history.

    Filesystem layout (per task):
    pool/
    ├── task.json                 # DebateTask metadata
    ├── round_1/
    │   ├── expert_A_solution.py
    │   ├── expert_B_solution.py
    │   └── ...
    ├── round_2/
    │   ├── expert_A_critique.md
    │   └── ...
    ├── judge/
    │   ├── round_1_scores.json
    │   └── final_verdict.json
    └── context/
        └── debate_history.md     # Concatenated summary for expert prompts
    """

    def __init__(
        self,
        pool_root: str = "debate_pools",
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the debate pool.

        Args:
            pool_root: Root directory for all debate pools (default: "debate_pools")
            emitter: Trace emitter for observability. Reserved for Phase 5 orchestrator
                wiring — current Phase 1 methods use logger.info() (sync) instead of
                async trace emission. The param is kept for API stability so Phase 5
                doesn't need to change the constructor signature.
        """
        self._pool_root = Path(pool_root)
        self._emitter = emitter or MemoryTraceEmitter()  # reserved for Phase 5
        self._pool_root.mkdir(parents=True, exist_ok=True)

    def create_pool(self, task: DebateTask) -> Path:
        """Create a new debate pool for a task. Returns the pool directory path."""
        pool_dir = self._pool_root / task.task_id
        pool_dir.mkdir(parents=True, exist_ok=True)

        # Write task metadata
        task_file = pool_dir / "task.json"
        task_file.write_text(
            json.dumps(asdict(task), default=str, indent=2), encoding="utf-8"
        )

        # Create subdirectories
        (pool_dir / "context").mkdir(exist_ok=True)

        # Rev3 fix (per Claude review): replaced async trace emission with sync logger
        # Old: asyncio.get_event_loop().create_task(self._emitter.emit(...)) — silently
        #      failed in Python 3.10+ (no event loop in sync context)
        # New: logger.info() — DebatePool is sync; async traces from sync code is an anti-pattern
        # Trace emission deferred to async callers (orchestrator in Phase 5)
        logger.info(
            "Debate pool created: task_id=%s task_type=%s", task.task_id, task.task_type
        )

        return pool_dir

    def save_solution(self, task_id: str, solution: ExpertSolution) -> Path:
        """Save an expert's solution to the pool."""
        round_dir = self._pool_root / task_id / f"round_{solution.round_number}"
        round_dir.mkdir(parents=True, exist_ok=True)

        solution_file = round_dir / f"{solution.expert_id}_solution.py"
        solution_file.write_text(solution.solution_code, encoding="utf-8")
        return solution_file

    def save_critique(self, task_id: str, critique: ExpertCritique) -> Path:
        """Save an expert's critique to the pool."""
        round_dir = self._pool_root / task_id / f"round_{critique.round_number}"
        round_dir.mkdir(parents=True, exist_ok=True)

        critique_file = (
            round_dir / f"{critique.expert_id}_critique_{critique.target_expert_id}.md"
        )
        critique_file.write_text(critique.critique_text, encoding="utf-8")
        return critique_file

    def save_scores(self, task_id: str, scores: list[JudgeScore]) -> Path:
        """Save judge scores for a round."""
        judge_dir = self._pool_root / task_id / "judge"
        judge_dir.mkdir(parents=True, exist_ok=True)

        if not scores:
            raise ValueError("Cannot save empty scores list")

        round_number = scores[0].round_number
        scores_file = judge_dir / f"round_{round_number}_scores.json"
        scores_file.write_text(
            json.dumps([asdict(s) for s in scores], default=str, indent=2),
            encoding="utf-8",
        )
        return scores_file

    def get_solutions(self, task_id: str, round_number: int) -> list[ExpertSolution]:
        """Retrieve all solutions for a round."""
        round_dir = self._pool_root / task_id / f"round_{round_number}"
        if not round_dir.exists():
            return []

        solutions = []
        for solution_file in round_dir.glob("*_solution.py"):
            # Rev2 fix (per GPT review): use rsplit to handle expert IDs with underscores
            # Old: expert_id = solution_file.stem.replace("_solution", "")  # corrupts IDs with "solution" in name
            # New: rsplit from the right, max 1 split
            expert_id = solution_file.stem.rsplit("_solution", 1)[0]
            solutions.append(
                ExpertSolution(
                    expert_id=expert_id,
                    expert_name=expert_id,  # simplified
                    round_number=round_number,
                    solution_code=solution_file.read_text(encoding="utf-8"),
                )
            )
        return solutions

    def get_critiques(self, task_id: str, round_number: int) -> list[ExpertCritique]:
        """Retrieve all critiques for a round."""
        round_dir = self._pool_root / task_id / f"round_{round_number}"
        if not round_dir.exists():
            return []

        critiques = []
        for critique_file in round_dir.glob("*_critique_*.md"):
            # Rev2 fix (per Claude + GPT review): use rsplit to handle expert IDs with underscores
            # Old: parts = critique_file.stem.split("_critique_") — fails on IDs with multiple underscores
            # New: rsplit from the right, max 1 split
            parts = critique_file.stem.rsplit("_critique_", 1)
            if len(parts) == 2:
                expert_id, target_part = parts
                # target_part is "target_id" (strip .md already done by .stem)
                critiques.append(
                    ExpertCritique(
                        expert_id=expert_id,
                        expert_name=expert_id,
                        round_number=round_number,
                        target_expert_id=target_part,
                        critique_text=critique_file.read_text(encoding="utf-8"),
                    )
                )
        return critiques

    def get_debate_history(self, task_id: str) -> str:
        """Get concatenated debate history for expert prompts."""
        pool_dir = self._pool_root / task_id
        if not pool_dir.exists():
            return ""

        history_parts = []
        for round_dir in sorted(pool_dir.glob("round_*")):
            round_num = int(round_dir.name.split("_")[1])
            history_parts.append(f"## Round {round_num}\n")

            for solution_file in sorted(round_dir.glob("*_solution.py")):
                # Rev3 fix (per Claude review): rsplit fix was missed here in Rev2
                # Old: expert_id = solution_file.stem.replace("_solution", "")  # corrupts IDs with "solution" in name
                # New: rsplit from the right, max 1 split (matches get_solutions fix)
                expert_id = solution_file.stem.rsplit("_solution", 1)[0]
                history_parts.append(f"### {expert_id} solution:\n")
                history_parts.append(
                    f"```python\n{solution_file.read_text(encoding='utf-8')}\n```\n"
                )

            for critique_file in sorted(round_dir.glob("*_critique_*.md")):
                history_parts.append("### Critique:\n")
                history_parts.append(critique_file.read_text(encoding="utf-8") + "\n")

        return "\n".join(history_parts)

    def cleanup_pool(self, task_id: str) -> None:
        """Remove a debate pool after implementation or max rounds."""
        import shutil

        pool_dir = self._pool_root / task_id
        if pool_dir.exists():
            shutil.rmtree(pool_dir)
