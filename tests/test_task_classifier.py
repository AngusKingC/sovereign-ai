"""
Tests for TaskClassifier (core/task_classifier.py).

Tests cover keyword-based classification, confidence scaling,
threshold retrieval, and edge cases. No LLM calls — pure heuristics.
"""

import pytest

from core.task_classifier import TaskClassifier, TaskType


@pytest.fixture
def classifier():
    """TaskClassifier instance for testing."""
    return TaskClassifier()


def test_classify_game_keywords(classifier):
    """'write a game with 60fps' → game."""
    result = classifier.classify("write a game with 60fps rendering and physics")
    assert result.task_type == TaskType.GAME
    assert result.confidence > 0.5
    assert "game" in result.matched_keywords


def test_classify_ai_agent_keywords(classifier):
    """'build an agent that uses tools' → ai_agent."""
    result = classifier.classify("build an agent that uses tools and reasoning")
    assert result.task_type == TaskType.AI_AGENT
    assert result.confidence > 0.5
    assert "agent" in result.matched_keywords


def test_classify_data_pipeline_keywords(classifier):
    """'ETL pipeline for batch processing' → data_pipeline."""
    result = classifier.classify("ETL pipeline for batch processing and stream data")
    assert result.task_type == TaskType.DATA_PIPELINE
    assert result.confidence > 0.5
    assert "pipeline" in result.matched_keywords


def test_classify_api_backend_keywords(classifier):
    """'REST API endpoint for requests' → api_backend."""
    result = classifier.classify(
        "REST API endpoint for server requests and backend routes"
    )
    assert result.task_type == TaskType.API_BACKEND
    assert result.confidence > 0.5
    assert "api" in result.matched_keywords


def test_classify_defaults_to_script(classifier):
    """'print hello world' → script."""
    result = classifier.classify("print hello world")
    assert result.task_type == TaskType.SCRIPT
    assert result.confidence == 0.3  # Low confidence on default
    assert len(result.matched_keywords) == 0


def test_classify_confidence_increases_with_matches(classifier):
    """More keywords → higher confidence."""
    result1 = classifier.classify("game")  # 1 match
    result2 = classifier.classify("game with physics and rendering")  # 3 matches

    assert result2.confidence > result1.confidence
    assert result1.confidence < 0.6  # Single match should be <60%
    assert result2.confidence > 0.6  # Multiple matches should be >60%


def test_get_threshold_returns_correct_value(classifier):
    """Verify per-type thresholds."""
    assert classifier.get_threshold(TaskType.GAME) == 85.0
    assert classifier.get_threshold(TaskType.AI_AGENT) == 90.0
    assert classifier.get_threshold(TaskType.DATA_PIPELINE) == 80.0
    assert classifier.get_threshold(TaskType.API_BACKEND) == 88.0
    assert classifier.get_threshold(TaskType.SCRIPT) == 75.0


def test_classify_case_insensitive(classifier):
    """'GAME' and 'game' match same."""
    result_upper = classifier.classify("GAME with physics")
    result_lower = classifier.classify("game with physics")

    assert result_upper.task_type == result_lower.task_type
    assert result_upper.confidence == result_lower.confidence


def test_classify_all_scores_populated(classifier):
    """Verify all_scores dict populated for all types."""
    result = classifier.classify("game with rendering")
    assert TaskType.GAME in result.all_scores
    assert TaskType.AI_AGENT in result.all_scores
    assert TaskType.DATA_PIPELINE in result.all_scores
    assert TaskType.API_BACKEND in result.all_scores


def test_classify_rev2_confidence_fix(classifier):
    """Rev2 fix: single keyword ≠ 100% confidence."""
    result = classifier.classify("game")
    # Old bug: confidence = 1.0 (100%) on single keyword
    # New: confidence < 0.6 (logarithmic scaling)
    assert result.confidence < 0.6
    assert result.confidence > 0.4


def test_classify_multiple_keywords_higher_confidence(classifier):
    """Rev2 fix: multiple keywords scale logarithmically."""
    result = classifier.classify("game with physics and rendering and sprites")
    # 4 matches gives ~0.74 with logarithmic scaling (not >0.8)
    assert result.confidence > 0.7
