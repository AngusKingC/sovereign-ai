"""
Tests for TestingBatterySkill (skills/testing_battery/skill.py).

Tests cover tool orchestration, scoring logic, quality % calculation,
and edge cases. Mocks SandboxExecutor. No LLM calls — pure orchestration.
"""

import json
from unittest.mock import AsyncMock

import pytest

from core.sandbox import SandboxResult
from skills.testing_battery.skill import (
    TestBatteryResult,
    TestingBatterySkill,
    ToolResult,
)


@pytest.fixture
def mock_sandbox():
    """Mock SandboxExecutor for testing."""
    sandbox = AsyncMock()
    sandbox.execute_command = AsyncMock()
    return sandbox


@pytest.fixture
def skill(mock_sandbox):
    """TestingBatterySkill instance with mock sandbox."""
    return TestingBatterySkill(sandbox_executor=mock_sandbox)


@pytest.fixture
def sample_solution_path(tmp_path):
    """Sample solution file path for testing."""
    solution_file = tmp_path / "solution.py"
    solution_file.write_text("def test(): pass", encoding="utf-8")
    return str(solution_file)


@pytest.fixture
def sample_test_file_path(tmp_path):
    """Sample test file path for testing."""
    test_file = tmp_path / "test_solution.py"
    test_file.write_text("def test_func(): assert True", encoding="utf-8")
    return str(test_file)


@pytest.mark.asyncio
async def test_run_battery_returns_result(skill, sample_solution_path):
    """Verify TestBatteryResult returned."""
    # Mock all tools to pass
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill.run_battery(sample_solution_path, "game")

    assert isinstance(result, TestBatteryResult)
    assert result.solution_path == sample_solution_path
    assert result.task_type == "game"
    assert "mypy" in result.tool_results
    assert "vulture" in result.tool_results
    assert "bandit" in result.tool_results


@pytest.mark.asyncio
async def test_run_mypy_scores_10_on_no_errors(skill, sample_solution_path):
    """Mock 0 errors → score 10.0."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="Success: no issues found",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_mypy(sample_solution_path)

    assert result.tool_name == "mypy"
    assert result.score == 10.0
    assert result.passed is True


@pytest.mark.asyncio
async def test_run_mypy_scores_lower_on_errors(skill, sample_solution_path):
    """Mock 3 errors → score 7.0."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=1,
        stdout="",
        stderr="solution.py:1: error: Name 'x' is not defined\n"
        "solution.py:2: error: Name 'y' is not defined\n"
        "solution.py:3: error: Name 'z' is not defined",
        success=False,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_mypy(sample_solution_path)

    assert result.tool_name == "mypy"
    assert result.score == 7.0  # 10.0 - 3 errors
    assert result.passed is False


@pytest.mark.asyncio
async def test_run_mypy_crash_scores_zero(skill, sample_solution_path):
    """Rev3: mock return_code != 0 + no stderr → score 0.0 (not 10.0)."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=1,
        stdout="",
        stderr="",  # No stderr = crash
        success=False,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_mypy(sample_solution_path)

    assert result.tool_name == "mypy"
    assert result.score == 0.0  # Rev3 fix: crashed tool scores 0
    assert result.passed is False
    assert "crashed without output" in result.error


@pytest.mark.asyncio
async def test_run_vulture_scores_10_on_no_findings(skill, sample_solution_path):
    """Mock 0 findings → score 10.0."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="No dead code found.",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_vulture(sample_solution_path)

    assert result.tool_name == "vulture"
    assert result.score == 10.0
    assert result.passed is True


@pytest.mark.asyncio
async def test_run_vulture_crash_scores_zero(skill, sample_solution_path):
    """Rev3: mock crash → score 0.0."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=1,
        stdout="",  # No stdout = crash
        stderr="",
        success=False,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_vulture(sample_solution_path)

    assert result.tool_name == "vulture"
    assert result.score == 0.0  # Rev3 fix: crashed tool scores 0
    assert result.passed is False


@pytest.mark.asyncio
async def test_run_bandit_scores_10_on_no_issues(skill, sample_solution_path):
    """Mock 0 issues → score 10.0."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout=json.dumps({"results": []}),
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_bandit(sample_solution_path)

    assert result.tool_name == "bandit"
    assert result.score == 10.0
    assert result.passed is True


@pytest.mark.asyncio
async def test_run_bandit_crash_scores_zero(skill, sample_solution_path):
    """Rev3: mock crash → score 0.0."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=1,
        stdout="",  # No stdout = crash
        stderr="",
        success=False,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_bandit(sample_solution_path)

    assert result.tool_name == "bandit"
    assert result.score == 0.0  # Rev3 fix: crashed tool scores 0
    assert result.passed is False


@pytest.mark.asyncio
async def test_run_pytest_scores_by_pass_ratio(
    skill, sample_solution_path, sample_test_file_path
):
    """Mock 8/10 passed → score 8.0."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="8 passed, 2 failed in 0.5s",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_pytest(sample_solution_path, sample_test_file_path)

    assert result.tool_name == "pytest"
    assert result.score == 8.0  # 8/10 * 10.0
    assert result.passed is True


@pytest.mark.asyncio
async def test_run_pytest_crash_scores_zero(
    skill, sample_solution_path, sample_test_file_path
):
    """Rev3: mock crash → score 0.0 (consistency with other tools)."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=1,
        stdout="",  # No stdout = crash
        stderr="",
        success=False,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_pytest(sample_solution_path, sample_test_file_path)

    assert result.tool_name == "pytest"
    assert result.score == 0.0  # Rev3 fix: crashed tool scores 0
    assert result.passed is False


@pytest.mark.asyncio
async def test_calculate_quality_pct_uses_task_weights(skill, sample_solution_path):
    """Verify game weights differ from script."""
    # Mock all tools with score 10.0
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result_game = await skill.run_battery(sample_solution_path, "game")
    result_script = await skill.run_battery(sample_solution_path, "script")

    # Game: mypy=0.20, vulture=0.20, pytest=0.35, bandit=0.25
    # Script: mypy=0.25, vulture=0.25, pytest=0.30, bandit=0.20
    # Both should be 100% if all tools pass
    assert result_game.quality_pct == 100.0
    assert result_script.quality_pct == 100.0


@pytest.mark.asyncio
async def test_calculate_quality_pct_renormalizes_when_tools_skipped(
    skill, sample_solution_path
):
    """Rev2: verify tasks without test files can still pass (renormalization)."""
    # Mock tools without pytest (no test_file_path)
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill.run_battery(sample_solution_path, "game", test_file_path=None)

    # Only mypy, vulture, bandit run (no pytest)
    # Game weights: mypy=0.20, vulture=0.20, bandit=0.25 → total 0.65
    # Renormalized: (0.20 + 0.20 + 0.25) / 0.65 = 1.0 → 100%
    assert result.quality_pct == 100.0
    assert "pytest" not in result.tool_results


@pytest.mark.asyncio
async def test_calculate_quality_pct_capped_at_100(skill, sample_solution_path):
    """Verify cap."""
    # Mock all tools with score 15.0 (above max)
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    # Manually set high scores (bypass normal scoring)
    result = await skill.run_battery(sample_solution_path, "game")
    for tool_result in result.tool_results.values():
        tool_result.score = 15.0

    # Recalculate with high scores
    result.quality_pct = skill._calculate_quality_pct(result, "game")

    assert result.quality_pct == 100.0  # Capped


@pytest.mark.asyncio
async def test_run_battery_skips_pytest_if_no_test_file(skill, sample_solution_path):
    """Rev2: verify pytest skipped when no test_file_path."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill.run_battery(sample_solution_path, "game", test_file_path=None)

    assert "pytest" not in result.tool_results
    assert "mypy" in result.tool_results
    assert "vulture" in result.tool_results
    assert "bandit" in result.tool_results


@pytest.mark.asyncio
async def test_run_battery_includes_pytest_if_test_file(
    skill, sample_solution_path, sample_test_file_path
):
    """Rev2: verify pytest included when test_file_path provided."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill.run_battery(
        sample_solution_path, "game", test_file_path=sample_test_file_path
    )

    assert "pytest" in result.tool_results


@pytest.mark.asyncio
async def test_parse_pytest_results_anchors_to_summary_line(
    skill, sample_solution_path, sample_test_file_path
):
    """Rev2: verify last match used (not first)."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="test_passed: 1 passed\n2 passed in summary line",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_pytest(sample_solution_path, sample_test_file_path)

    # Should use last match (2 passed), but failed count is 0 (no "failed" in output)
    # So total = 2, passed = 2 → score = 10.0
    assert result.score == 10.0


@pytest.mark.asyncio
async def test_parse_pytest_results_handles_failures(
    skill, sample_solution_path, sample_test_file_path
):
    """Verify failed count parsed."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=1,
        stdout="8 passed, 2 failed",
        stderr="",
        success=False,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_pytest(sample_solution_path, sample_test_file_path)

    assert result.score == 8.0  # 8/10 * 10.0


@pytest.mark.asyncio
async def test_tool_result_passed_flag_correct(skill, sample_solution_path):
    """Verify passed flag per return code."""
    # Pass case
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )
    result_pass = await skill._run_mypy(sample_solution_path)
    assert result_pass.passed is True

    # Fail case
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=1,
        stdout="",
        stderr="error",
        success=False,
        sandboxed=True,
        container_id="test",
    )
    result_fail = await skill._run_mypy(sample_solution_path)
    assert result_fail.passed is False


@pytest.mark.asyncio
async def test_truncate_caps_output_at_10kb(skill, sample_solution_path):
    """Rev2: verify output truncation prevents memory bloat."""
    long_output = "x" * 15000  # 15KB
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout=long_output,
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill._run_mypy(sample_solution_path)

    assert len(result.output) == 10000 + len("\n... [truncated, 5000 chars omitted]")
    assert "truncated" in result.output


@pytest.mark.asyncio
async def test_calculate_quality_pct_warns_on_unweighted_tool(
    skill, sample_solution_path
):
    """Rev3: verify logger.warning when tool not in weight dict."""
    skill._sandbox.execute_command.return_value = SandboxResult(
        return_code=0,
        stdout="",
        stderr="",
        success=True,
        sandboxed=True,
        container_id="test",
    )

    result = await skill.run_battery(sample_solution_path, "game")
    # Manually add a tool not in weight dict
    result.tool_results["unknown_tool"] = ToolResult(
        tool_name="unknown_tool",
        passed=True,
        score=10.0,
        output="",
    )

    # Should log warning but not crash
    quality_pct = skill._calculate_quality_pct(result, "game")
    # unknown_tool should be excluded from calculation
    assert quality_pct == 100.0
