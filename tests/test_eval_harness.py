"""Unit tests for evaluation harness and metrics."""

import pytest
from datetime import datetime, timezone
from evals.harness import EvalHarness, EvalResult
from evals.metrics import (
    compute_exact_match,
    compute_token_f1,
    compute_bleu,
    compute_cosine_similarity,
)
from core.observability import MemoryTraceEmitter


class TestMetrics:
    """Test metric functions."""

    def test_exact_match_identical(self):
        """Test that exact match returns 1.0 for identical strings."""
        assert compute_exact_match("hello", "hello") == 1.0
        assert compute_exact_match("hello world", "hello world") == 1.0

    def test_exact_match_different(self):
        """Test that exact match returns 0.0 for different strings."""
        assert compute_exact_match("hello", "world") == 0.0
        assert compute_exact_match("hello world", "hello") == 0.0

    def test_exact_match_whitespace(self):
        """Test that exact match ignores leading/trailing whitespace."""
        assert compute_exact_match("  hello  ", "hello") == 1.0
        assert compute_exact_match("hello", "  hello  ") == 1.0

    def test_token_f1_perfect(self):
        """Test that token F1 returns 1.0 for identical tokens."""
        assert compute_token_f1("hello world", "hello world") == 1.0
        assert compute_token_f1("Hello World", "hello world") == 1.0  # case-insensitive

    def test_token_f1_partial(self):
        """Test that token F1 returns partial score for overlap."""
        score = compute_token_f1("hello world", "hello there")
        assert 0.0 < score < 1.0

    def test_token_f1_empty(self):
        """Test that token F1 handles empty strings."""
        assert compute_token_f1("", "") == 1.0
        assert compute_token_f1("hello", "") == 0.0
        assert compute_token_f1("", "hello") == 0.0

    def test_bleu_score(self):
        """Test that BLEU score computes n-gram overlap."""
        score = compute_bleu("hello world", "hello world")
        assert score > 0.5  # Should be high for identical strings

    def test_bleu_different(self):
        """Test that BLEU score is low for different strings."""
        score = compute_bleu("hello world", "foo bar")
        assert score < 0.5

    def test_cosine_similarity(self):
        """Test that cosine similarity computes bag-of-words similarity."""
        score = compute_cosine_similarity("hello world", "hello world")
        assert score > 0.999  # Identical vectors (floating point tolerance)

    def test_cosine_similarity_partial(self):
        """Test that cosine similarity handles partial overlap."""
        score = compute_cosine_similarity("hello world", "hello there")
        assert 0.0 < score < 1.0

    def test_cosine_similarity_empty(self):
        """Test that cosine similarity handles empty strings."""
        assert compute_cosine_similarity("", "") == 1.0
        assert compute_cosine_similarity("hello", "") == 0.0


class TestEvalHarness:
    """Test EvalHarness functionality."""

    @pytest.fixture
    def harness(self):
        """Create a default EvalHarness instance."""
        return EvalHarness()

    @pytest.fixture
    def harness_with_emitter(self):
        """Create an EvalHarness with a trace emitter."""
        return EvalHarness(trace_emitter=MemoryTraceEmitter())

    @pytest.mark.asyncio
    async def test_harness_initialization(self, harness):
        """Test that harness initializes with default metrics."""
        assert "exact_match" in harness.metrics
        assert "token_f1" in harness.metrics
        assert "bleu" in harness.metrics
        assert "cosine_similarity" in harness.metrics
        assert len(harness.results) == 0

    @pytest.mark.asyncio
    async def test_evaluate_single(self, harness):
        """Test that single eval returns EvalResult with metrics."""
        result = await harness.evaluate("hello world", "hello world")
        assert isinstance(result, EvalResult)
        assert result.predicted == "hello world"
        assert result.gold == "hello world"
        assert result.metrics["exact_match"] == 1.0
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_evaluate_batch(self, harness):
        """Test that batch eval processes multiple pairs."""
        predictions = [("hello", "hello"), ("foo", "bar")]
        results = await harness.evaluate_batch(predictions)
        assert len(results) == 2
        assert all(isinstance(r, EvalResult) for r in results)

    @pytest.mark.asyncio
    async def test_evaluate_with_trace_emitter(self, harness_with_emitter):
        """Test that harness emits trace events when emitter provided."""
        result = await harness_with_emitter.evaluate("hello", "hello")
        assert result.metrics["exact_match"] == 1.0
        # Trace emitter should have recorded the event
        assert harness_with_emitter.trace_emitter.count() > 0

    @pytest.mark.asyncio
    async def test_summary_stats(self, harness):
        """Test that summary computes mean/min/max correctly."""
        await harness.evaluate("hello", "hello")
        await harness.evaluate("foo", "bar")
        summary = harness.summary()
        assert "exact_match" in summary
        assert "mean" in summary["exact_match"]
        assert "min" in summary["exact_match"]
        assert "max" in summary["exact_match"]
        assert "count" in summary["exact_match"]

    @pytest.mark.asyncio
    async def test_evaluate_empty_predictions(self, harness):
        """Test that harness handles empty strings gracefully."""
        result = await harness.evaluate("", "")
        assert result.metrics["exact_match"] == 1.0

    @pytest.mark.asyncio
    async def test_metric_failure_handling(self, harness_with_emitter):
        """Test that metric exception doesn't crash harness (AR18)."""
        # Add a failing metric
        def failing_metric(predicted: str, gold: str) -> float:
            raise ValueError("Test failure")
        
        harness_with_emitter.metrics["failing"] = failing_metric
        result = await harness_with_emitter.evaluate("hello", "hello")
        # Failing metric should default to 0.0
        assert result.metrics["failing"] == 0.0
        # Other metrics should still work
        assert result.metrics["exact_match"] == 1.0

    @pytest.mark.asyncio
    async def test_batch_length_mismatch(self, harness):
        """Test that batch raises ValueError if task_ids length != predictions."""
        predictions = [("hello", "hello"), ("foo", "bar")]
        task_ids = ["task1"]  # Only 1 task_id for 2 predictions
        with pytest.raises(ValueError, match="task_ids must match predictions length"):
            await harness.evaluate_batch(predictions, task_ids)

    @pytest.mark.asyncio
    async def test_results_accumulation(self, harness):
        """Test that multiple evals accumulate in results list."""
        await harness.evaluate("hello", "hello")
        await harness.evaluate("foo", "bar")
        assert len(harness.results) == 2

    @pytest.mark.asyncio
    async def test_evaluate_with_task_id(self, harness):
        """Test that task_id is preserved in result."""
        result = await harness.evaluate("hello", "hello", task_id="test-task-123")
        assert result.task_id == "test-task-123"

    @pytest.mark.asyncio
    async def test_summary_empty(self, harness):
        """Test that summary returns empty dict when no results."""
        summary = harness.summary()
        assert summary == {}

    @pytest.mark.asyncio
    async def test_custom_metrics(self):
        """Test that harness accepts custom metrics."""
        custom_metrics = {"custom": lambda p, g: 0.5}
        harness = EvalHarness(metrics=custom_metrics)
        result = await harness.evaluate("hello", "hello")
        assert "custom" in result.metrics
        assert result.metrics["custom"] == 0.5
        assert "exact_match" not in result.metrics  # Default metrics not used

    @pytest.mark.asyncio
    async def test_timestamp_utc(self, harness):
        """Test that timestamps use UTC timezone (OR20)."""
        result = await harness.evaluate("hello", "hello")
        assert result.timestamp.tzinfo == timezone.utc
