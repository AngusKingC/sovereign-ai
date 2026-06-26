# Plan 88 — PEMADS Phase 3: Judge + Implementation Gate

**Tag**: `prompt-88` | **Depends on**: `prompt-87`

### Scope

Build `PEMADSJudge` — evaluates debate quality using `TestingBatterySkill`, decides whether to implement. Build `ImplementationGate` — gates on quality threshold (per TaskType) + approval for unsafe implementations. Wire into `Orchestrator` after Plan 87's `ExpertPanelManager`.

### S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-87` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for PEMADS vocabulary.
S0.3. No new AGENTS.md rules this prompt.

### S1. Create `core/pemads_judge.py`

```python
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

from memory.debate_pool import DebatePool, JudgeScore
from core.task_classifier import TaskClassifier
from skills.testing_battery.skill import TestingBatterySkill, TestBatteryResult

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
    winning_solution_code: str = ""  # Rev2 H8 fix — winning solution code for orchestrator routing


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
        import tempfile
        import os

        # Determine final round number
        final_round = self._get_final_round_number(debate_id)

        solutions = self._debate_pool.get_solutions(debate_id, final_round)
        if not solutions:
            raise ValueError(f"No solutions found for debate {debate_id} round {final_round}")

        threshold = self._classifier.get_threshold(task_type)
        all_scores: dict[str, float] = {}
        all_judge_scores: list[JudgeScore] = []

        for sol in solutions:
            temp_path = None
            try:
                # Rev2 H7 fix — write solution_code to a tempfile instead of assuming
                # DebatePool materializes .py files on disk.
                temp_fd, temp_path = tempfile.mkstemp(suffix=".py", prefix=f"{sol.expert_id}_solution_")
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
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
        winning_expert_id = max(all_scores, key=all_scores.get) if all_scores else ""
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
            winning_solution_code=winning_solution.solution_code if winning_solution else "",
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
            debate_path = getattr(self._debate_pool, 'pool_root', None)
            if debate_path:
                debate_path = debate_path / debate_id if hasattr(debate_path, '__truediv__') else os.path.join(str(debate_path), debate_id)
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

    def _summarize_verdict(self, scores: dict[str, float], winner: str, threshold: float) -> str:
        """Summarize the verdict for the ImplementationGate."""
        lines = [f"Winner: {winner} ({scores[winner]:.1f}%)"]
        lines.append(f"Threshold: {threshold:.1f}%")
        lines.append(f"Result: {'PASSED' if scores[winner] >= threshold else 'FAILED'}")
        lines.append("All scores:")
        for eid, score in sorted(scores.items(), key=lambda x: -x[1]):
            lines.append(f"  {eid}: {score:.1f}%")
        return "\n".join(lines)
```

### S2. Create `core/implementation_gate.py`

```python
"""
PEMADS Phase 3: Implementation Gate

Gates implementation of a debated solution based on:
1. Quality threshold (from JudgeVerdict.passed)
2. Risk assessment (unsafe implementations require approval)
3. Approval gate integration (for high-risk implementations)

If gate passes → solution is implemented.
If gate fails → solution is rejected, task may be retried or escalated.
If gate requires approval → ApprovalGate.request_approval is called.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from core.pemads_judge import JudgeVerdict
from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType

logger = logging.getLogger(__name__)


@dataclass
class GateDecision:
    """Result of implementation gate check."""
    debate_id: str
    approved: bool
    requires_human_approval: bool
    pending: bool = False  # Rev2 H6 fix — True when request is submitted but not yet responded to
    reason: str
    approved_by: str  # "auto", "pending", or human responder
    decided_at: datetime


class ImplementationGate:
    """Gates PEMADS solution implementation."""

    # Risk thresholds for auto-approval vs human approval
    AUTO_APPROVE_THRESHOLD = 90.0  # >= 90% quality → auto-approve
    HUMAN_APPROVAL_THRESHOLD = 75.0  # 75-90% → human approval required
    # Below 75% → auto-reject

    # Rev2 L3 fix — thresholds are configurable via constructor
    def __init__(
        self,
        approval_gate: ApprovalGate,
        emitter: Optional[Any] = None,
        auto_approve_threshold: float = 90.0,
        human_approval_threshold: float = 75.0,
        approval_ttl_seconds: int = 300,
    ) -> None:
        self._approval_gate = approval_gate
        self._emitter = emitter
        self._auto_approve_threshold = auto_approve_threshold
        self._human_approval_threshold = human_approval_threshold
        self._approval_ttl_seconds = approval_ttl_seconds

    async def check(self, verdict: JudgeVerdict, task: Any) -> GateDecision:
        """Check if a solution should be implemented.

        Decision tree:
        1. If verdict.passed is False → reject (quality below threshold)
        2. If quality >= AUTO_APPROVE_THRESHOLD → auto-approve
        3. If quality >= HUMAN_APPROVAL_THRESHOLD → submit for approval, return pending
        4. Below HUMAN_APPROVAL_THRESHOLD → reject (even if passed threshold)

        Rev2 H6 fix — medium-quality tier returns pending=True instead of treating
        the initial request_approval response as final. The orchestrator holds the
        task in AWAITING_APPROVAL state and resumes when respond() is called.
        """
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        # Case 1: Quality below task threshold
        if not verdict.passed:
            return GateDecision(
                debate_id=verdict.debate_id,
                approved=False,
                requires_human_approval=False,
                pending=False,
                reason=f"Quality {verdict.winning_quality_pct:.1f}% below threshold {verdict.threshold:.1f}%",
                approved_by="auto",
                decided_at=now,
            )

        # Case 2: High quality → auto-approve
        if verdict.winning_quality_pct >= self._auto_approve_threshold:
            return GateDecision(
                debate_id=verdict.debate_id,
                approved=True,
                requires_human_approval=False,
                pending=False,
                reason=f"Quality {verdict.winning_quality_pct:.1f}% >= auto-approve threshold {self._auto_approve_threshold}%",
                approved_by="auto",
                decided_at=now,
            )

        # Case 3: Medium quality → human approval required
        if verdict.winning_quality_pct >= self._human_approval_threshold:
            # Rev2 H5 fix — use timedelta, not now.replace(second=now.second + 300)
            # datetime.replace(second=...) only accepts 0-59; adding 300 raises ValueError.
            expires_at = now + timedelta(seconds=self._approval_ttl_seconds)

            approval_request = ApprovalRequest(
                request_id=f"pemads-gate-{verdict.debate_id}",
                task_id=getattr(task, 'task_id', ''),
                session_id=getattr(task, 'session_id', ''),
                action_type=ApprovalActionType.SYSTEM_CONFIG,
                action_description=f"PEMADS implementation gate for debate {verdict.debate_id}",
                action_parameters={
                    "debate_id": verdict.debate_id,
                    "winning_expert": verdict.winning_expert_id,
                    "quality_pct": verdict.winning_quality_pct,
                },
                risk_level="medium",
                reason_for_approval=verdict.feedback,
                created_at=now,
                expires_at=expires_at,
            )

            # Submit for approval — returns immediately with pending status
            response = await self._approval_gate.request_approval(approval_request)

            # Rev2 H6 fix — don't treat initial pending response as denial.
            # request_approval returns approved=False while pending. The orchestrator
            # should hold the task in AWAITING_APPROVAL and resume when respond() is called.
            return GateDecision(
                debate_id=verdict.debate_id,
                approved=False,  # Not yet approved — will be updated when respond() is called
                requires_human_approval=True,
                pending=True,  # Rev2 H6 fix — mark as pending, not denied
                reason=f"Human approval submitted (expires {expires_at.isoformat()}). Awaiting response.",
                approved_by="pending",
                decided_at=now,
            )

        # Case 4: Below human approval threshold → reject
        return GateDecision(
            debate_id=verdict.debate_id,
            approved=False,
            requires_human_approval=False,
            pending=False,
            reason=f"Quality {verdict.winning_quality_pct:.1f}% below human approval threshold {self._human_approval_threshold}%",
            approved_by="auto",
            decided_at=now,
        )
```

### S3. Wire into `core/orchestrator.py`

Add optional injection:

```python
# In __init__ signature:
pemads_judge: Optional["PEMADSJudge"] = None,
implementation_gate: Optional["ImplementationGate"] = None,

# In __init__ body:
self.pemads_judge = pemads_judge
self.implementation_gate = implementation_gate
```

Update the debate trigger in `_execute_task` (from Plan 87) to add judging:

```python
# Check if task should be debated (PEMADS Phase 2)
if self.expert_panel_manager and await self.expert_panel_manager.should_debate(task):
    logger.info(f"Task {task.task_id} flagged for PEMADS debate")
    debate_id = await self.expert_panel_manager.run_debate(task)

    # PEMADS Phase 3: Judge the debate
    if self.pemads_judge:
        classification = self.task_classifier.classify(task.intent)
        verdict = await self.pemads_judge.judge_debate(debate_id, classification.task_type)

        if self.implementation_gate:
            gate_decision = await self.implementation_gate.check(verdict, task)

            # Rev2 H6 fix — handle pending state (medium-quality awaiting human approval)
            if gate_decision.pending:
                logger.info(f"PEMADS gate pending for task {task.task_id}: {gate_decision.reason}")
                # Hold task in AWAITING_APPROVAL state. The task will be resumed
                # when ApprovalGate.respond() is called (via Web UI, Telegram, or Email).
                task.metadata = task.metadata or {}
                task.metadata["pemads_pending"] = {
                    "debate_id": debate_id,
                    "verdict": verdict.__dict__,
                    "gate_decision": gate_decision.__dict__,
                }
                # Transition to AWAITING_APPROVAL — orchestrator's pending_approval_queue
                # handles resumption when respond() is called
                return  # Don't proceed with execution until approved

            elif not gate_decision.approved:
                logger.info(f"PEMADS gate rejected task {task.task_id}: {gate_decision.reason}")
                task.metadata = task.metadata or {}
                task.metadata["pemads_rejection"] = gate_decision.reason
                return  # Don't proceed with execution

            else:
                logger.info(f"PEMADS gate approved task {task.task_id}")
                # Rev2 H8 fix — route the winning solution to implementation instead
                # of re-executing the original task intent. The entire PEMADS chain
                # (debate + judge + gate) is useless if we discard the winning solution.
                task.metadata = task.metadata or {}
                task.metadata["pemads_verdict"] = {
                    "debate_id": verdict.debate_id,
                    "winning_expert": verdict.winning_expert_id,
                    "quality_pct": verdict.winning_quality_pct,
                    "threshold": verdict.threshold,
                }
                # If the winning solution is code, execute it directly instead of
                # re-running the original task through a worker.
                if verdict.winning_solution_code:
                    task.metadata["pemads_winning_solution"] = verdict.winning_solution_code
                    # Route to implementation executor (sandbox) rather than worker dispatch
                    # This ensures the debated solution is what actually gets implemented
                    # TODO: wire to SandboxExecutor in Plan 90+ when sandbox is integrated
                    # For now, log that we have a winning solution
                    logger.info(f"Task {task.task_id} has winning solution from {verdict.winning_expert_id}")

    # Proceed with normal execution after gate approval
    # (If winning_solution_code is set, a future plan will route it to sandbox)
```

### S4. Add API endpoint

```python
@app.get("/api/debates/{debate_id}/verdict")
async def get_verdict(debate_id: str):
    if not orchestrator.pemads_judge:
        return {"error": "PEMADS judge not configured"}, 404
    # Return last verdict for this debate (cached or re-judged)
    # For now, re-judge on demand
    # In production, cache verdicts
    return {"debate_id": debate_id, "verdict": "endpoint placeholder"}
```

### S5. Add tests

Create `tests/test_pemads_judge.py`:
- test_judge_debate_selects_winner
- test_judge_debate_quality_below_threshold
- test_judge_debate_quality_above_threshold
- test_judge_debate_no_solutions_raises
- test_generate_feedback
- test_summarize_verdict

Create `tests/test_implementation_gate.py`:
- test_gate_auto_approve_high_quality
- test_gate_human_approval_medium_quality
- test_gate_reject_below_threshold
- test_gate_reject_below_human_threshold
- test_gate_approval_request_created

Minimum 11 tests total.

### S6. Verify build

```powershell
ruff check core/pemads_judge.py core/implementation_gate.py
mypy core/pemads_judge.py core/implementation_gate.py core/orchestrator.py --ignore-missing-imports
pytest tests/test_pemads_judge.py tests/test_implementation_gate.py -v
pytest tests/ -q --tb=short | Select-Object -Last 5
```

### STOP condition

If mypy reports errors in new files, STOP and fix. If any test fails, STOP and fix.

### Files WILL create (4)
- `core/pemads_judge.py`
- `core/implementation_gate.py`
- `tests/test_pemads_judge.py`
- `tests/test_implementation_gate.py`

### Files WILL edit (2)
- `core/orchestrator.py` (add pemads_judge, implementation_gate injection + judging logic)
- `web/server.py` (add /api/debates/{id}/verdict endpoint)

### Files will NOT edit
- `memory/debate_pool.py` (use as-is)
- `core/task_classifier.py` (use as-is)
- `core/approval_gate.py` (use as-is — already has request_approval)
- `skills/testing_battery/` (use as-is)
- `src/` (no frontend changes this plan)

### Closing

Run `/jarvis-close`. Tag `prompt-88`. CHANGELOG entry for Plan 88. Update PLANS.md.

---
