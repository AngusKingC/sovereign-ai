"""Tests for ModelTierRouter.

Tests cover classification heuristics, routing logic, cost fallback integration,
and edge cases. All 19 tests specified in Plan 79 S1.3.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from core.cost_tracker import CostDecision
from core.model_tier_router import ModelTierRouter, TaskComplexity
from core.schemas import Task, TaskPriority


@pytest.fixture
def router():
    """Create a ModelTierRouter instance for testing."""
    return ModelTierRouter(
        emitter=None,
        simple_model="llama3.2:1b",
        medium_model="llama3.2:8b",
        complex_model="gpt-4o",
    )


@pytest.fixture
def sample_task():
    """Create a sample Task for testing."""
    return Task(
        task_id=uuid4(),
        intent="test task",
        complexity_score=0.5,
        priority=TaskPriority.NORMAL,
        created_at=datetime.now(timezone.utc),
    )


def test_classify_returns_simple_for_arithmetic_keywords(router, sample_task):
    """Test that arithmetic keywords return SIMPLE complexity."""
    sample_task.intent = "calculate 2+2"
    assert router.classify(sample_task) == TaskComplexity.SIMPLE


def test_classify_returns_simple_for_lookup_keywords(router, sample_task):
    """Test that lookup keywords return SIMPLE complexity."""
    sample_task.intent = "define photosynthesis"
    assert router.classify(sample_task) == TaskComplexity.SIMPLE


def test_classify_returns_medium_for_summarize(router, sample_task):
    """Test that summarize keyword returns MEDIUM complexity."""
    sample_task.intent = "summarize this article"
    assert router.classify(sample_task) == TaskComplexity.MEDIUM


def test_classify_returns_medium_for_single_file_edit(router, sample_task):
    """Test that single-file edit returns MEDIUM complexity."""
    sample_task.intent = "edit main.py"
    assert router.classify(sample_task) == TaskComplexity.MEDIUM


def test_classify_returns_complex_for_debate(router, sample_task):
    """Test that debate keyword returns COMPLEX complexity."""
    sample_task.intent = "debate the best approach"
    assert router.classify(sample_task) == TaskComplexity.COMPLEX


def test_classify_returns_complex_for_multi_file_refactor(router, sample_task):
    """Test that multi-file refactor returns COMPLEX complexity."""
    sample_task.intent = "refactor across core/ and adapters/"
    assert router.classify(sample_task) == TaskComplexity.COMPLEX


def test_classify_returns_medium_for_unknown_tasks(router, sample_task):
    """Test that unknown tasks default to MEDIUM complexity."""
    sample_task.intent = "do something random"
    assert router.classify(sample_task) == TaskComplexity.MEDIUM


def test_route_returns_simple_model_for_simple_task(router, sample_task):
    """Test that SIMPLE tasks route to simple_model."""
    sample_task.intent = "calculate 2+2"
    choice = router.route(sample_task)
    assert choice.model_name == "llama3.2:1b"
    assert choice.complexity == TaskComplexity.SIMPLE
    assert not choice.downgraded


def test_route_returns_medium_model_for_medium_task(router, sample_task):
    """Test that MEDIUM tasks route to medium_model."""
    sample_task.intent = "summarize this article"
    choice = router.route(sample_task)
    assert choice.model_name == "llama3.2:8b"
    assert choice.complexity == TaskComplexity.MEDIUM
    assert not choice.downgraded


def test_route_returns_complex_model_for_complex_task(router, sample_task):
    """Test that COMPLEX tasks route to complex_model."""
    sample_task.intent = "debate the best approach"
    choice = router.route(sample_task)
    assert choice.model_name == "gpt-4o"
    assert choice.complexity == TaskComplexity.COMPLEX
    assert not choice.downgraded


def test_route_downgrades_complex_to_medium_on_cost_fallback(router, sample_task):
    """Test that cost fallback downgrades COMPLEX → MEDIUM."""
    sample_task.intent = "debate the best approach"
    cost_decision = CostDecision(
        approved=True,
        reason="spend cap approaching",
        fallback_model="llama3.2:8b",
    )
    choice = router.route(sample_task, cost_decision=cost_decision)
    assert choice.model_name == "llama3.2:8b"
    assert choice.complexity == TaskComplexity.MEDIUM
    assert choice.downgraded
    assert "cost cap downgrade" in choice.reason


def test_route_downgrades_medium_to_simple_on_cost_fallback(router, sample_task):
    """Test that cost fallback downgrades MEDIUM → SIMPLE."""
    sample_task.intent = "summarize this article"
    cost_decision = CostDecision(
        approved=True,
        reason="spend cap approaching",
        fallback_model="llama3.2:1b",
    )
    choice = router.route(sample_task, cost_decision=cost_decision)
    assert choice.model_name == "llama3.2:1b"
    assert choice.complexity == TaskComplexity.SIMPLE
    assert choice.downgraded
    assert "cost cap downgrade" in choice.reason


def test_route_does_not_downgrade_simple_below_simple(router, sample_task):
    """Test that SIMPLE tasks cannot be downgraded further."""
    sample_task.intent = "calculate 2+2"
    cost_decision = CostDecision(
        approved=True,
        reason="spend cap approaching",
        fallback_model="llama3.2:1b",
    )
    choice = router.route(sample_task, cost_decision=cost_decision)
    assert choice.model_name == "llama3.2:1b"
    assert choice.complexity == TaskComplexity.SIMPLE
    assert not choice.downgraded


def test_route_returns_correct_reason_string(router, sample_task):
    """Test that reason field is descriptive."""
    sample_task.intent = "calculate 2+2"
    choice = router.route(sample_task)
    assert "complexity" in choice.reason.lower()
    assert "simple" in choice.reason.lower()


def test_get_tier_for_model_returns_correct_tier(router):
    """Test that reverse lookup returns correct tier."""
    assert router.get_tier_for_model("llama3.2:1b") == TaskComplexity.SIMPLE
    assert router.get_tier_for_model("llama3.2:8b") == TaskComplexity.MEDIUM
    assert router.get_tier_for_model("gpt-4o") == TaskComplexity.COMPLEX


def test_classify_handles_empty_task(router, sample_task):
    """Test that empty task defaults to MEDIUM."""
    sample_task.intent = ""
    assert router.classify(sample_task) == TaskComplexity.MEDIUM


def test_classify_handles_none_metadata(router, sample_task):
    """Test that task with no metadata defaults to MEDIUM."""
    sample_task.intent = "do something"
    assert router.classify(sample_task) == TaskComplexity.MEDIUM


def test_classify_returns_medium_for_single_file_refactor(router, sample_task):
    """Test that single-file refactor returns MEDIUM (Rev2 Issue #3 fix)."""
    sample_task.intent = "refactor main.py to use dataclasses"
    assert router.classify(sample_task) == TaskComplexity.MEDIUM


def test_classify_returns_complex_for_refactor_with_no_file_paths(router, sample_task):
    """Test that refactor with no file paths defaults to COMPLEX (Rev2 Issue #3 fix)."""
    sample_task.intent = "refactor the authentication logic"
    assert router.classify(sample_task) == TaskComplexity.COMPLEX
