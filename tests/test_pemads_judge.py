"""
Tests for PEMADSJudge (Plan 88).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.pemads_judge import PEMADSJudge
from core.task_classifier import TaskClassifier
from memory.debate_pool import DebatePool, ExpertSolution
from skills.testing_battery.skill import (
    TestBatteryResult,
    TestingBatterySkill,
    ToolResult,
)


@pytest.fixture
def mock_debate_pool():
    """Mock DebatePool."""
    pool = MagicMock(spec=DebatePool)
    return pool


@pytest.fixture
def mock_testing_battery():
    """Mock TestingBatterySkill."""
    battery = AsyncMock(spec=TestingBatterySkill)
    return battery


@pytest.fixture
def mock_classifier():
    """Mock TaskClassifier."""
    classifier = MagicMock(spec=TaskClassifier)
    classifier.get_threshold.return_value = 85.0
    return classifier


@pytest.fixture
def judge(mock_debate_pool, mock_testing_battery, mock_classifier):
    """PEMADSJudge fixture."""
    return PEMADSJudge(
        debate_pool=mock_debate_pool,
        testing_battery=mock_testing_battery,
        classifier=mock_classifier,
        emitter=None,
    )


@pytest.mark.asyncio
async def test_judge_debate_selects_winner(
    judge, mock_debate_pool, mock_testing_battery
):
    """Test that judge selects the winner with highest quality."""
    debate_id = "debate-123"
    task_type = "script"

    # Mock solutions
    solutions = [
        ExpertSolution(
            expert_id="expert_a",
            expert_name="Expert A",
            solution_code="def foo(): return 1",
            round_number=1,
        ),
        ExpertSolution(
            expert_id="expert_b",
            expert_name="Expert B",
            solution_code="def bar(): return 2",
            round_number=1,
        ),
    ]
    mock_debate_pool.get_solutions.return_value = solutions
    mock_debate_pool.get_solutions.return_value = solutions

    # Mock battery results
    result_a = TestBatteryResult(
        solution_path="",
        task_type="script",
        tool_results={
            "mypy": ToolResult(tool_name="mypy", passed=True, score=9.0, output=""),
            "pytest": ToolResult(tool_name="pytest", passed=True, score=8.0, output=""),
        },
        quality_pct=85.0,
    )
    result_b = TestBatteryResult(
        solution_path="",
        task_type="script",
        tool_results={
            "mypy": ToolResult(tool_name="mypy", passed=True, score=10.0, output=""),
            "pytest": ToolResult(tool_name="pytest", passed=True, score=9.0, output=""),
        },
        quality_pct=95.0,
    )
    mock_testing_battery.run_battery.side_effect = [result_a, result_b]

    verdict = await judge.judge_debate(debate_id, task_type)

    assert verdict.winning_expert_id == "expert_b"
    assert verdict.winning_quality_pct == 95.0
    assert verdict.passed is True
    assert verdict.all_scores["expert_a"] == 85.0
    assert verdict.all_scores["expert_b"] == 95.0


@pytest.mark.asyncio
async def test_judge_debate_quality_below_threshold(
    judge, mock_debate_pool, mock_testing_battery, mock_classifier
):
    """Test that quality below threshold results in failed verdict."""
    debate_id = "debate-123"
    task_type = "script"
    mock_classifier.get_threshold.return_value = 90.0

    solutions = [
        ExpertSolution(
            expert_id="expert_a",
            expert_name="Expert A",
            solution_code="def foo(): return 1",
            round_number=1,
        ),
    ]
    mock_debate_pool.get_solutions.return_value = solutions

    result = TestBatteryResult(
        solution_path="",
        task_type="script",
        tool_results={
            "mypy": ToolResult(tool_name="mypy", passed=True, score=7.0, output=""),
            "pytest": ToolResult(tool_name="pytest", passed=True, score=7.0, output=""),
        },
        quality_pct=70.0,
    )
    mock_testing_battery.run_battery.return_value = result

    verdict = await judge.judge_debate(debate_id, task_type)

    assert verdict.winning_quality_pct == 70.0
    assert verdict.passed is False
    assert verdict.threshold == 90.0


@pytest.mark.asyncio
async def test_judge_debate_quality_above_threshold(
    judge, mock_debate_pool, mock_testing_battery
):
    """Test that quality above threshold results in passed verdict."""
    debate_id = "debate-123"
    task_type = "script"

    solutions = [
        ExpertSolution(
            expert_id="expert_a",
            expert_name="Expert A",
            solution_code="def foo(): return 1",
            round_number=1,
        ),
    ]
    mock_debate_pool.get_solutions.return_value = solutions

    result = TestBatteryResult(
        solution_path="",
        task_type="script",
        tool_results={
            "mypy": ToolResult(tool_name="mypy", passed=True, score=9.0, output=""),
            "pytest": ToolResult(tool_name="pytest", passed=True, score=9.0, output=""),
        },
        quality_pct=90.0,
    )
    mock_testing_battery.run_battery.return_value = result

    verdict = await judge.judge_debate(debate_id, task_type)

    assert verdict.winning_quality_pct == 90.0
    assert verdict.passed is True


@pytest.mark.asyncio
async def test_judge_debate_no_solutions_raises(judge, mock_debate_pool):
    """Test that ValueError is raised when no solutions found."""
    debate_id = "debate-123"
    task_type = "script"
    mock_debate_pool.get_solutions.return_value = []

    with pytest.raises(ValueError, match="No solutions found"):
        await judge.judge_debate(debate_id, task_type)


def test_generate_feedback(judge):
    """Test feedback generation from battery results."""
    result = TestBatteryResult(
        solution_path="",
        task_type="script",
        tool_results={
            "mypy": ToolResult(tool_name="mypy", passed=True, score=9.0, output=""),
            "pytest": ToolResult(
                tool_name="pytest", passed=False, score=5.0, output=""
            ),
        },
        quality_pct=70.0,
    )

    feedback = judge._generate_feedback(result)

    assert "Quality: 70.0%" in feedback
    assert "mypy: PASS (score: 9.0/10)" in feedback
    assert "pytest: FAIL (score: 5.0/10)" in feedback


def test_summarize_verdict(judge):
    """Test verdict summarization."""
    scores = {"expert_a": 85.0, "expert_b": 95.0}
    winner = "expert_b"
    threshold = 85.0

    summary = judge._summarize_verdict(scores, winner, threshold)

    assert "Winner: expert_b (95.0%)" in summary
    assert "Threshold: 85.0%" in summary
    assert "Result: PASSED" in summary
    assert "expert_a: 85.0%" in summary
    assert "expert_b: 95.0%" in summary
