"""
PEMADS Phase 3: Judge

Evaluates debate quality using TestingBatterySkill. Scores each expert's
solution against the task's quality threshold (per TaskType). Selects the
best solution. Produces a JudgeVerdict for the ImplementationGate.

Integration:
- DebatePool: reads solutions + critiques from debate rounds
- TestingBatterySkill: runs mypy/vulture/bandit/pytest on each solution
- TaskClassifier: provides quality threshold per task type
- CostTracker: records judging costs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from core.task_classifier import TaskClassifier
from memory.debate_pool import DebatePool, JudgeScore
from skills.testing_battery.skill import TestBatteryResult, TestingBatterySkill

logger = logging.getLogger(__name__)


@dataclass
class JudgeVerdict:
    """Result of judging a debate."""

    debate_id: str
    winning_expert_id: str
    winning_quality_pct: float
    threshold: float
    passed: bool  # True if winning_quality_pct >= threshold
    all_scores: dict[str, float]  # expert_id -> quality_pct
    feedback: str
    judged_at: datetime
    winning_solution_code: str = (
        ""  # Rev2 H8 fix — winning solution code for orchestrator routing
    )


class PEMADSJudge:
    """Evaluates PEMADS debate solutions and selects the best."""

    def __init__(
        self,
        debate_pool: DebatePool,
        testing_battery: TestingBatterySkill,
        classifier: TaskClassifier,
        emitter: Optional[Any] = None,
    ) -> None:
        self._debate_pool = debate_pool
        self._battery = testing_battery
        self._classifier = classifier
        self._emitter = emitter

    async def judge_debate(self, debate_id: str, task_type: str) -> JudgeVerdict:
        """Judge the final round of a debate. Returns JudgeVerdict.

        Steps:
        1. Get all solutions from the final round
        2. Run TestingBattery on each solution (Rev2 H7 fix — write solution_code to tempfile)
        3. Score each solution (quality_pct)
        4. Select winner (highest quality_pct)
        5. Compare winner's quality_pct against task threshold
        6. Persist scores to DebatePool
        7. Return JudgeVerdict

        Rev2 H7 fix — the original code assumed DebatePool saves solutions as .py files
        on disk (pool_root/debate_id/round_N/<expert>_solution.py) and constructed paths
        via self._debate_pool.pool_root. This assumption is unverified — DebatePool may
        be DB-backed or store solutions as metadata only. The fix writes solution_code
        to a tempfile.NamedTemporaryFile before passing to TestingBatterySkill.
        """
        import os
        import tempfile

        # Determine final round number
        final_round = self._get_final_round_number(debate_id)

        solutions = self._debate_pool.get_solutions(debate_id, final_round)
        if not solutions:
            raise ValueError(
                f"No solutions found for debate {debate_id} round {final_round}"
            )

        threshold = self._classifier.get_threshold(task_type)
        all_scores: dict[str, float] = {}
        all_judge_scores: list[JudgeScore] = []

        for sol in solutions:
            temp_path = None
            try:
                # Rev2 H7 fix — write solution_code to a tempfile instead of assuming
                # DebatePool materializes .py files on disk.
                temp_fd, temp_path = tempfile.mkstemp(
                    suffix=".py", prefix=f"{sol.expert_id}_solution_"
                )
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    f.write(sol.solution_code)

                result = await self._battery.run_battery(
                    solution_path=temp_path,
                    task_type=task_type,
                )

                all_scores[sol.expert_id] = result.quality_pct

                judge_score = JudgeScore(
                    round_number=final_round,
                    expert_id=sol.expert_id,
                    scores={tool: tr.score for tool, tr in result.tool_results.items()},
                    quality_pct=result.quality_pct,
                    feedback=self._generate_feedback(result),
                    scored_at=datetime.now(timezone.utc),
                )
                all_judge_scores.append(judge_score)

            except Exception as e:
                logger.warning(f"Failed to judge solution by {sol.expert_id}: {e}")
                all_scores[sol.expert_id] = 0.0
            finally:
                # Clean up tempfile
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

        # Persist scores to DebatePool
        if all_judge_scores:
            self._debate_pool.save_scores(debate_id, all_judge_scores)

        # Select winner
        winning_expert_id = (
            max(all_scores, key=lambda k: all_scores[k]) if all_scores else ""
        )
        winning_quality = all_scores.get(winning_expert_id, 0.0)
        passed = winning_quality >= threshold

        # Rev2 H8 fix — include winning solution code in verdict so orchestrator
        # can route it to implementation instead of re-executing the original task.
        winning_solution = next(
            (s for s in solutions if s.expert_id == winning_expert_id), None
        )

        return JudgeVerdict(
            debate_id=debate_id,
            winning_expert_id=winning_expert_id,
            winning_quality_pct=winning_quality,
            threshold=threshold,
            passed=passed,
            all_scores=all_scores,
            feedback=self._summarize_verdict(all_scores, winning_expert_id, threshold),
            judged_at=datetime.now(timezone.utc),
            winning_solution_code=(
                winning_solution.solution_code if winning_solution else ""
            ),
        )

    def _get_final_round_number(self, debate_id: str) -> int:
        """Find the highest round number in the debate pool.

        Rev2 H7 fix — this method previously used os + iterdir() on debate_pool.pool_root,
        assuming a filesystem layout. Now it tries the filesystem approach first, but
        falls back to querying DebatePool.get_solutions() for round 1, 2, 3... until
        it finds an empty result, returning the last non-empty round number.
        """
        # Try filesystem approach first (if DebatePool uses filesystem storage)
        try:
            import os

            debate_path = getattr(self._debate_pool, "pool_root", None)
            if debate_path:
                debate_path = (
                    debate_path / debate_id
                    if hasattr(debate_path, "__truediv__")
                    else os.path.join(str(debate_path), debate_id)
                )
                if os.path.exists(str(debate_path)):
                    rounds = []
                    for d in os.listdir(str(debate_path)):
                        if d.startswith("round_"):
                            try:
                                rounds.append(int(d.split("_")[1]))
                            except (IndexError, ValueError):
                                pass
                    if rounds:
                        return max(rounds)
        except Exception:
            pass  # Fall through to query-based approach

        # Fallback: query DebatePool for rounds until empty result
        for round_num in range(10, 0, -1):  # Check 10 down to 1
            solutions = self._debate_pool.get_solutions(debate_id, round_num)
            if solutions:
                return round_num

        return 1  # Default if no rounds found

    def _generate_feedback(self, result: TestBatteryResult) -> str:
        """Generate human-readable feedback from battery results."""
        lines = [f"Quality: {result.quality_pct:.1f}%"]
        for tool_name, tool_result in result.tool_results.items():
            status = "PASS" if tool_result.passed else "FAIL"
            lines.append(f"  {tool_name}: {status} (score: {tool_result.score:.1f}/10)")
        return "\n".join(lines)

    def _summarize_verdict(
        self, scores: dict[str, float], winner: str, threshold: float
    ) -> str:
        """Summarize the verdict for the ImplementationGate."""
        lines = [f"Winner: {winner} ({scores[winner]:.1f}%)"]
        lines.append(f"Threshold: {threshold:.1f}%")
        lines.append(f"Result: {'PASSED' if scores[winner] >= threshold else 'FAILED'}")
        lines.append("All scores:")
        for eid, score in sorted(scores.items(), key=lambda x: -x[1]):
            lines.append(f"  {eid}: {score:.1f}%")
        return "\n".join(lines)
