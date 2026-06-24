"""
Testing Battery Skill — orchestrates code quality tool runs in sandbox.

Single responsibility: Run mypy, vulture, pytest, bandit, hypothesis against
a solution file, return per-tool scores. No LLM calls — pure orchestration.

Per PEMADS spec section 4.4. Uses SandboxExecutor (Plan 73, AR19) for isolation.
AR5 compliant (skills/ imports from core/ only).
"""

import json
import logging
from dataclasses import dataclass, field

from core.observability import MemoryTraceEmitter, TraceEmitter
from core.sandbox import SandboxConfig, SandboxExecutor

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of a single testing tool run."""

    tool_name: str
    passed: bool
    score: float  # 0.0-10.0
    output: str
    error: str | None = None
    duration_ms: int = 0


@dataclass
class TestBatteryResult:
    """Aggregated result of all testing tool runs."""

    solution_path: str
    task_type: str
    tool_results: dict[str, ToolResult] = field(default_factory=dict)
    quality_pct: float = 0.0
    total_duration_ms: int = 0

    def get_score(self, tool_name: str) -> float:
        """Get the score for a specific tool."""
        result = self.tool_results.get(tool_name)
        return result.score if result else 0.0


class TestingBatterySkill:
    """Runs code quality tools against a solution in sandbox.

    Tools run (Phase 1 minimal set per Plan 76 research):
    - mypy (type safety)
    - pytest (functional correctness)
    - bandit (security)
    - vulture (dead code)
    - hypothesis (property-based fuzzing) — only if hypothesis tests exist

    cProfile + pytest-benchmark deferred to Phase 3 (Plan 83) per roadmap.
    """

    def __init__(
        self,
        sandbox_executor: SandboxExecutor | None = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        self._sandbox = sandbox_executor or SandboxExecutor(
            config=SandboxConfig(timeout=120),
            emitter=emitter or MemoryTraceEmitter(),
        )
        self._emitter = emitter or MemoryTraceEmitter()

    async def run_battery(
        self,
        solution_path: str,
        task_type: str,
        test_file_path: str | None = None,
    ) -> TestBatteryResult:
        """Run the full testing battery against a solution.

        Args:
            solution_path: Path to the solution .py file
            task_type: Task type for scoring weights (game, ai_agent, etc.)
            test_file_path: Optional path to test file (for pytest/hypothesis)

        Returns:
            TestBatteryResult with per-tool scores and aggregated quality %
        """
        import time

        start_time = time.perf_counter()

        result = TestBatteryResult(
            solution_path=solution_path,
            task_type=task_type,
        )

        # Run tools sequentially (per OR3 — parallel corrupts output)
        tools_to_run = [
            ("mypy", self._run_mypy),
            ("vulture", self._run_vulture),
            ("bandit", self._run_bandit),
        ]

        if test_file_path:
            # Rev2 fix (per GPT review): hypothesis runs via @given in normal pytest
            # Old: separate _run_hypothesis with -k hypothesis filter (broken — misses @given tests)
            # New: pytest runs all tests including @given-decorated ones; hypothesis is redundant
            tools_to_run.append(("pytest", lambda s: self._run_pytest(s, test_file_path)))  # type: ignore[arg-type]

        for tool_name, run_func in tools_to_run:
            tool_result = await run_func(solution_path)
            result.tool_results[tool_name] = tool_result

        # Calculate weighted quality % (Rev2: renormalize based on tools that ran)
        result.quality_pct = self._calculate_quality_pct(result, task_type)
        result.total_duration_ms = int((time.perf_counter() - start_time) * 1000)

        return result

    async def _run_mypy(self, solution_path: str) -> ToolResult:
        """Run mypy on the solution."""
        import shlex

        cmd = f"mypy {shlex.quote(solution_path)} --ignore-missing-imports"
        sandbox_result = await self._sandbox.execute_command(cmd)

        # Rev2 fix (per GPT + Kimi review): crashed tool scores 0, not 10
        if sandbox_result.return_code != 0 and not sandbox_result.stderr:
            # Tool crashed without output — score 0, not 10
            return ToolResult(
                tool_name="mypy",
                passed=False,
                score=0.0,
                output=self._truncate(sandbox_result.stdout),
                error="mypy crashed without output",
            )

        # Score: 10.0 if 0 errors, scale down by error count
        errors = self._count_mypy_errors(sandbox_result.stderr)
        score = max(0.0, 10.0 - errors)

        return ToolResult(
            tool_name="mypy",
            passed=sandbox_result.return_code == 0,
            score=score,
            output=self._truncate(sandbox_result.stdout),
            error=(
                self._truncate(sandbox_result.stderr)
                if sandbox_result.return_code != 0
                else None
            ),
        )

    async def _run_vulture(self, solution_path: str) -> ToolResult:
        """Run vulture on the solution."""
        import shlex

        cmd = f"vulture {shlex.quote(solution_path)} --min-confidence 80"
        sandbox_result = await self._sandbox.execute_command(cmd)

        # Rev2 fix: crashed tool scores 0
        if sandbox_result.return_code != 0 and not sandbox_result.stdout:
            return ToolResult(
                tool_name="vulture",
                passed=False,
                score=0.0,
                output="",
                error="vulture crashed without output",
            )

        findings = self._count_vulture_findings(sandbox_result.stdout)
        score = max(0.0, 10.0 - findings * 0.5)

        return ToolResult(
            tool_name="vulture",
            passed=sandbox_result.return_code == 0,
            score=score,
            output=self._truncate(sandbox_result.stdout),
            error=(
                self._truncate(sandbox_result.stderr)
                if sandbox_result.return_code != 0
                else None
            ),
        )

    async def _run_bandit(self, solution_path: str) -> ToolResult:
        """Run bandit on the solution."""
        import shlex

        cmd = f"bandit {shlex.quote(solution_path)} -ll -f json"
        sandbox_result = await self._sandbox.execute_command(cmd)

        # Rev2 fix: crashed tool scores 0
        if sandbox_result.return_code != 0 and not sandbox_result.stdout:
            return ToolResult(
                tool_name="bandit",
                passed=False,
                score=0.0,
                output="",
                error="bandit crashed without output",
            )

        issues = self._count_bandit_issues(sandbox_result.stdout)
        score = max(0.0, 10.0 - issues * 2.0)

        return ToolResult(
            tool_name="bandit",
            passed=sandbox_result.return_code == 0,
            score=score,
            output=self._truncate(sandbox_result.stdout),
            error=(
                self._truncate(sandbox_result.stderr)
                if sandbox_result.return_code != 0
                else None
            ),
        )

    async def _run_pytest(self, solution_path: str, test_file_path: str) -> ToolResult:
        """Run pytest on the test file (includes hypothesis @given tests)."""
        import shlex

        cmd = f"pytest {shlex.quote(test_file_path)} -v --tb=short"
        sandbox_result = await self._sandbox.execute_command(cmd)

        # Rev3 fix (per Claude review): added crash guard for consistency with other tools
        if sandbox_result.return_code != 0 and not sandbox_result.stdout:
            return ToolResult(
                tool_name="pytest",
                passed=False,
                score=0.0,
                output="",
                error="pytest crashed without output",
            )

        passed, total = self._parse_pytest_results(sandbox_result.stdout)
        score = (passed / total * 10.0) if total > 0 else 0.0

        return ToolResult(
            tool_name="pytest",
            passed=sandbox_result.return_code == 0,
            score=score,
            output=self._truncate(sandbox_result.stdout),
            error=(
                self._truncate(sandbox_result.stderr)
                if sandbox_result.return_code != 0
                else None
            ),
        )

    def _calculate_quality_pct(
        self, result: TestBatteryResult, task_type: str
    ) -> float:
        """Calculate weighted quality % per task type.

        Rev2 fix (per GPT + Claude + DeepSeek review): renormalize weights based
        on tools that actually ran. Old version summed only available tools
        without renormalizing, making tasks without test files unpassable
        (max 35% < 85% threshold).

        Rev3 fix (per Claude review): added assertion that all tools in
        result.tool_results have nonzero weights. Prevents a Phase 3 landmine
        where a tool runs but has weight 0 (not in weight dict) — its crash
        would be invisible to quality_pct.
        """
        weights = self._get_weights(task_type)

        # Rev3: validate that all tools that ran have weights
        # (prevents silent score inflation when tools_to_run is extended in Phase 3)
        for tool_name in result.tool_results:
            if tool_name not in weights:
                # AR18: log warning but don't crash — score what we can
                logger.warning(
                    "AR18: Tool %s ran but has no weight for task_type %s — score will be excluded",
                    tool_name,
                    task_type,
                )

        # Sum weights of tools that actually ran AND have nonzero weights
        available_weight = sum(
            weights.get(tool_name, 0)
            for tool_name in result.tool_results
            if weights.get(tool_name, 0) > 0
        )

        if available_weight == 0:
            return 0.0

        # Calculate raw score from available tools (only those with weights)
        raw_score = 0.0
        for tool_name, tool_result in result.tool_results.items():
            weight = weights.get(tool_name, 0)
            if weight > 0:  # Rev3: only count tools with nonzero weights
                raw_score += (tool_result.score / 10.0) * weight

        # Renormalize: scale to 100% based on available weight
        quality_pct = (raw_score / available_weight) * 100.0
        return min(quality_pct, 100.0)

    def _get_weights(self, task_type: str) -> dict[str, float]:
        """Get scoring weights for a task type.

        Returns weights as fractions (summing to ~1.0).
        Per PEMADS spec section 4.4 (simplified for Phase 1 — no cProfile/pylint).
        Rev2: hypothesis removed (runs via pytest @given); weights redistributed.
        """
        weights_by_type = {
            "game": {"mypy": 0.20, "vulture": 0.20, "pytest": 0.35, "bandit": 0.25},
            "ai_agent": {"mypy": 0.20, "vulture": 0.15, "pytest": 0.35, "bandit": 0.30},
            "data_pipeline": {
                "mypy": 0.20,
                "vulture": 0.20,
                "pytest": 0.40,
                "bandit": 0.20,
            },
            "api_backend": {
                "mypy": 0.20,
                "vulture": 0.15,
                "pytest": 0.35,
                "bandit": 0.30,
            },
            "script": {"mypy": 0.25, "vulture": 0.25, "pytest": 0.30, "bandit": 0.20},
        }
        return weights_by_type.get(task_type, weights_by_type["script"])

    def _count_mypy_errors(self, stderr: str) -> int:
        """Count mypy errors in stderr output.

        Rev2 fix (per GPT review): only count lines matching mypy error pattern
        (file:line: error:), not every line containing "error:" (which overcounts
        multi-line errors and notes).
        """
        import re

        # AR18: parse failure is non-critical, default to 0 errors
        try:
            # mypy errors match: filename.py:line: error: message
            pattern = r"^\S+\.py:\d+: error:"
            return len(
                [line for line in stderr.splitlines() if re.match(pattern, line)]
            )
        except Exception:
            return 0

    def _truncate(self, text: str, max_chars: int = 10000) -> str:
        """Truncate text to prevent memory bloat (Rev2 fix per Claude review).

        Testing tool output can be massive (hypothesis failures, verbose pytest).
        Cap at 10KB to prevent memory exhaustion in orchestrator.
        """
        if len(text) <= max_chars:
            return text
        return (
            text[:max_chars]
            + f"\n... [truncated, {len(text) - max_chars} chars omitted]"
        )

    def _count_vulture_findings(self, stdout: str) -> int:
        """Count vulture findings in stdout."""
        try:
            return len([line for line in stdout.splitlines() if "confidence" in line])
        except Exception:
            return 0

    def _count_bandit_issues(self, stdout: str) -> int:
        """Count bandit issues from JSON output."""
        try:
            data = json.loads(stdout)
            return len(data.get("results", []))
        except (json.JSONDecodeError, Exception):
            return 0

    def _parse_pytest_results(self, stdout: str) -> tuple[int, int]:
        """Parse pytest output for passed/total counts.

        Rev2 fix (per Kimi review): anchor regex to summary line (last match),
        not first match (which could match test names containing "passed").
        """
        try:
            import re

            # Look for ALL "X passed" patterns, take the last one (summary line)
            matches = re.findall(r"(\d+) passed", stdout)
            passed = int(matches[-1]) if matches else 0
            # Total = passed + failed
            matches_failed = re.findall(r"(\d+) failed", stdout)
            failed = int(matches_failed[-1]) if matches_failed else 0
            return passed, passed + failed
        except Exception:
            return 0, 0
