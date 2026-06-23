# Plan 62 — Eval Harness Implementation

**Priority**: 3 (measurement layer foundation, post-trace-store)  
**Scope**: Implement offline evaluation harness for improvement loop. Evals compare LLM outputs against gold-standard responses using metrics (BLEU, cosine similarity, semantic similarity).

---

## S0 — Opening Sequence

### S0.1: Run `/jarvis-open`

Per AI_HANDOFF.md's Devin Plan Template, run the workflow — do not hand-roll the equivalent commands. The workflow verifies the previous prompt's tag on origin and confirms the working copy is clean and on `master`. If the workflow is missing or fails, STOP and report.

### S0.2: AGENTS.md Rules Check

Read `AGENTS.md` in full. No new AGENTS.md rules for this plan.

All file edits in this plan MUST comply with:
- **AR1-AR4**: Architecture rules (core/memory separation)
- **AR5-AR8**: Serialization and type safety
- **AR9**: No raw LLM calls outside adapters/
- **AR10**: Memory access via MemoryRouter only
- **AR11**: `TraceEmitter` via constructor injection only
- **AR12**: All I/O async
- **AR14**: Return type annotations
- **AR18**: No broad `except Exception: pass` without inline comment + WARNING trace
- **OR5**: Edit each file occurrence individually (never replace_all)
- **OR6**: Syntax check after every edit
- **OR7**: Structured markdown edits use Edit tool only
- **OR15-OR17**: Scope discipline (no unplanned changes)
- **OR20**: Never mix naive/aware datetime (use `datetime.now(timezone.utc)`)
- **OR22**: Re-read AGENTS.md before file edits

**If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for the trigger and diagnostic context.**

### S0.3: Scope Declaration (OR15)

**Will edit** (5 files):
- `evals/harness.py` (new)
- `evals/metrics.py` (new)
- `evals/__init__.py` (new)
- `tests/test_eval_harness.py` (new)
- `core/observability.py` (add eval result recording support)

**Will NOT edit**: anything in `memory/`, `cli/`, `web/`, `system/`, `skills/`, `adapters/`, or any other file. If wiring the eval harness requires touching a file outside this list, STOP and report per OR16 — do not fix it unilaterally.

---

## S1 — Implement Evaluation Metrics Module

### S1.1: Create `evals/metrics.py`

**Purpose**: Core metrics for evaluating LLM output quality.

**Scope**: New file. ~180 lines.

**Metrics to implement**:
1. **BLEU Score** — sequence n-gram overlap (use `nltk` library if available, or implement basic version)
2. **Cosine Similarity** — embedding-based similarity (use `sklearn.metrics.pairwise.cosine_similarity`)
3. **Exact Match** — binary 1/0 for identical strings
4. **Token F1** — precision/recall for token-level comparison

**Design**:
- Module-level functions, not classes (keep it simple)
- Each function: `compute_{metric}(predicted: str, gold: str) -> float`
- Return normalized scores in range [0.0, 1.0]
- All functions synchronous (metrics are lightweight CPU-bound operations)
- Return type annotations on all public functions (AR14)

**File structure**:
```python
from typing import List, Tuple
from collections import Counter
import math

def compute_exact_match(predicted: str, gold: str) -> float:
    """Return 1.0 if strings match exactly, 0.0 otherwise."""
    return 1.0 if predicted.strip() == gold.strip() else 0.0

def compute_token_f1(predicted: str, gold: str) -> float:
    """Compute F1 score at token level."""
    pred_tokens = set(predicted.lower().split())
    gold_tokens = set(gold.lower().split())
    
    if not gold_tokens:
        return 1.0 if not pred_tokens else 0.0
    
    common = len(pred_tokens & gold_tokens)
    if common == 0:
        return 0.0
    
    precision = common / len(pred_tokens) if pred_tokens else 0.0
    recall = common / len(gold_tokens) if gold_tokens else 0.0
    
    if precision + recall == 0:
        return 0.0
    
    return 2 * (precision * recall) / (precision + recall)

def compute_bleu(predicted: str, gold: str, max_n: int = 2) -> float:
    """Compute BLEU score (simplified version, n-grams up to max_n)."""
    pred_tokens = predicted.lower().split()
    gold_tokens = gold.lower().split()
    
    if not gold_tokens:
        return 1.0 if not pred_tokens else 0.0
    
    # For simplicity, compute unigram + bigram overlap
    score = 0.0
    for n in range(1, min(max_n + 1, len(gold_tokens) + 1)):
        pred_ngrams = [tuple(pred_tokens[i:i+n]) for i in range(len(pred_tokens) - n + 1)]
        gold_ngrams = [tuple(gold_tokens[i:i+n]) for i in range(len(gold_tokens) - n + 1)]
        
        if not gold_ngrams:
            continue
        
        pred_count = Counter(pred_ngrams)
        gold_count = Counter(gold_ngrams)
        
        matches = sum((pred_count & gold_count).values())
        score += matches / len(gold_ngrams)
    
    return score / min(max_n, len(gold_tokens))

def compute_cosine_similarity(predicted: str, gold: str) -> float:
    """
    Compute cosine similarity of word vectors (bag-of-words implementation).
    
    Self-contained, no external dependencies. Uses word frequency vectors
    and standard cosine similarity formula: dot product / (||pred|| * ||gold||)
    
    Returns normalized score in [0.0, 1.0].
    """
    pred_tokens = predicted.lower().split()
    gold_tokens = gold.lower().split()
    
    if not pred_tokens or not gold_tokens:
        return 1.0 if (not pred_tokens and not gold_tokens) else 0.0
    
    pred_count = Counter(pred_tokens)
    gold_count = Counter(gold_tokens)
    
    # Cosine similarity = dot product / (||pred|| * ||gold||)
    common_words = set(pred_count.keys()) & set(gold_count.keys())
    dot_product = sum(pred_count[w] * gold_count[w] for w in common_words)
    
    pred_norm = math.sqrt(sum(c ** 2 for c in pred_count.values()))
    gold_norm = math.sqrt(sum(c ** 2 for c in gold_count.values()))
    
    if pred_norm == 0 or gold_norm == 0:
        return 0.0
    
    return dot_product / (pred_norm * gold_norm)
```

**After creating, run:**
```powershell
python -c "import ast; ast.parse(open('evals/metrics.py').read())"
git diff --stat evals/metrics.py
```

Verify: syntax clean, file is new, ~180 lines.

---

### S1.2: Create `evals/__init__.py`

**Purpose**: Make eval module importable.

**Steps**:
1. Add imports: `from .metrics import compute_exact_match, compute_token_f1, compute_bleu, compute_cosine_similarity`
2. Add `__all__` list with all metric functions

**After edit**:
```powershell
python -c "import ast; ast.parse(open('evals/__init__.py').read())"
git diff evals/__init__.py
```

Verify: syntax clean, 3-5 lines.

---

## S2 — Implement Eval Harness

### S2.1: Create `evals/harness.py`

**Purpose**: Main evaluation harness — orchestrates evaluation of LLM outputs against gold-standard responses.

**Scope**: New file. ~250 lines.

**Design**:
- Class: `EvalHarness` (manages eval state, runs evals)
- Constructor: `__init__(metrics: dict[str, Callable] | None = None, trace_emitter: TraceEmitter | None = None)`
- Methods:
  - `evaluate(predicted: str, gold: str, task_id: str | None = None) -> EvalResult` — runs all metrics, returns structured result
  - `evaluate_batch(predictions: list[tuple[str, str]], task_ids: list[str] | None = None) -> list[EvalResult]` — eval multiple pairs (raises ValueError if task_ids length != predictions length)
  - `summary() -> dict` — aggregate stats (mean, std, min, max per metric)

**Key requirements**:
- ✅ All methods async (AR12)
- ✅ Return type annotations (AR14)
- ✅ TraceEmitter injection optional (AR11)
- ✅ Metrics are configurable (default: exact_match, token_f1, bleu, cosine_similarity)
- ✅ Each eval result includes timestamp (use `datetime.now(timezone.utc)`, OR20)

**EvalResult schema**:
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class EvalResult:
    predicted: str
    gold: str
    task_id: str | None
    metrics: dict[str, float]  # e.g., {"exact_match": 0.0, "token_f1": 0.6, ...}
    timestamp: datetime
```

**File structure**:
```python
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from dataclasses import dataclass, asdict
import asyncio

from core.observability import TraceEmitter, TraceEvent, TraceEventType, TraceLevel
from .metrics import (
    compute_exact_match,
    compute_token_f1,
    compute_bleu,
    compute_cosine_similarity,
)

@dataclass
class EvalResult:
    """Single evaluation result."""
    predicted: str
    gold: str
    task_id: Optional[str]
    metrics: dict[str, float]
    timestamp: datetime

class EvalHarness:
    """Harness for offline evaluation of LLM outputs."""

    def __init__(
        self,
        metrics: Optional[dict[str, Callable[[str, str], float]]] = None,
        trace_emitter: Optional[TraceEmitter] = None,
    ) -> None:
        """Initialize the eval harness.
        
        Args:
            metrics: Dict mapping metric names to callables. Defaults to standard metrics.
            trace_emitter: Optional trace emitter for recording eval events.
        """
        self.trace_emitter = trace_emitter
        self.metrics = metrics or {
            "exact_match": compute_exact_match,
            "token_f1": compute_token_f1,
            "bleu": compute_bleu,
            "cosine_similarity": compute_cosine_similarity,
        }
        self.results: list[EvalResult] = []

    async def evaluate(
        self,
        predicted: str,
        gold: str,
        task_id: Optional[str] = None,
    ) -> EvalResult:
        """Evaluate a single prediction against gold standard.
        
        Args:
            predicted: The model's output
            gold: The gold-standard (expected) output
            task_id: Optional identifier for the task
            
        Returns:
            EvalResult with computed metrics
        """
        metrics_scores = {}
        for metric_name, metric_fn in self.metrics.items():
            try:
                score = metric_fn(predicted, gold)
                metrics_scores[metric_name] = score
            except Exception as e:
                # If a metric fails, record it as 0.0 and log warning
                metrics_scores[metric_name] = 0.0
                if self.trace_emitter:
                    await self._emit_eval_warning(
                        f"Metric {metric_name} failed: {e}",
                        task_id,
                    )

        result = EvalResult(
            predicted=predicted,
            gold=gold,
            task_id=task_id,
            metrics=metrics_scores,
            timestamp=datetime.now(timezone.utc),
        )
        
        self.results.append(result)
        
        if self.trace_emitter:
            await self._emit_eval_result(result)
        
        return result

    async def evaluate_batch(
        self,
        predictions: list[tuple[str, str]],
        task_ids: Optional[list[str]] = None,
    ) -> list[EvalResult]:
        """Evaluate multiple predictions.
        
        Args:
            predictions: List of (predicted, gold) pairs
            task_ids: Optional list of task identifiers (must match predictions length)
            
        Returns:
            List of EvalResult objects
        """
        if task_ids and len(task_ids) != len(predictions):
            raise ValueError("task_ids must match predictions length")
        
        results = []
        for idx, (predicted, gold) in enumerate(predictions):
            task_id = task_ids[idx] if task_ids else None
            result = await self.evaluate(predicted, gold, task_id)
            results.append(result)
        
        return results

    def summary(self) -> dict[str, dict[str, float]]:
        """Compute summary statistics across all eval results.
        
        Returns:
            Dict mapping metric names to stats (mean, std, min, max)
        """
        if not self.results:
            return {}
        
        summary = {}
        metric_names = set()
        for result in self.results:
            metric_names.update(result.metrics.keys())
        
        for metric_name in metric_names:
            scores = [r.metrics[metric_name] for r in self.results if metric_name in r.metrics]
            if scores:
                summary[metric_name] = {
                    "mean": sum(scores) / len(scores),
                    "min": min(scores),
                    "max": max(scores),
                    "count": len(scores),
                }
        
        return summary

    async def _emit_eval_result(self, result: EvalResult) -> None:
        """Emit trace event for eval result."""
        if not self.trace_emitter:
            return
        
        event = TraceEvent(
            event_type=TraceEventType.EVAL_COMPLETE,
            level=TraceLevel.INFO,
            component="eval",
            message=f"Eval complete: {result.task_id or 'unknown'}",
            metadata={
                "task_id": result.task_id,
                "metrics": result.metrics,
            },
        )
        await self.trace_emitter.emit(event)

    async def _emit_eval_warning(
        self,
        message: str,
        task_id: Optional[str],
    ) -> None:
        """Emit warning trace event."""
        if not self.trace_emitter:
            return
        
        event = TraceEvent(
            event_type=TraceEventType.EVAL_WARNING,
            level=TraceLevel.WARNING,
            component="eval",
            message=message,
            metadata={"task_id": task_id},
        )
        await self.trace_emitter.emit(event)
```

**After creating, run:**
```powershell
python -c "import ast; ast.parse(open('evals/harness.py').read())"
git diff --stat evals/harness.py
```

Verify: syntax clean, file is new, ~250 lines.

---

## S3 — Update Core Observability (Trace Event Types)

### S3.1: Add Eval Event Types to `core/observability.py`

**Purpose**: Extend TraceEventType enum to support eval events.

**Steps**:
1. Read the TraceEventType enum definition (find the current values)
2. Add two new event types: `EVAL_COMPLETE`, `EVAL_WARNING`
3. Do NOT change existing values

**After edit**:
```powershell
python -c "import ast; ast.parse(open('core/observability.py').read())"
git diff core/observability.py
```

Verify: syntax clean, only 2-3 lines added (2 new enum values).

---

## S4 — Create Unit Tests for Eval Harness

### S4.1: Create `tests/test_eval_harness.py`

**Purpose**: Test metrics and harness functionality.

**Scope**: ~200 lines, 12-15 test cases.

**Tests to implement**:

**Metrics tests** (4-6 tests):
- `test_exact_match_identical()` — exact match returns 1.0
- `test_exact_match_different()` — different strings return 0.0
- `test_token_f1_perfect()` — identical tokens return 1.0
- `test_token_f1_partial()` — overlap returns 0.0 < score < 1.0
- `test_bleu_score()` — n-gram overlap computed
- `test_cosine_similarity()` — bag-of-words similarity computed

**Harness tests** (8-10 tests):
- `test_harness_initialization()` — harness initializes with default metrics
- `test_evaluate_single()` — single eval returns EvalResult with metrics
- `test_evaluate_batch()` — batch eval processes multiple pairs
- `test_evaluate_with_trace_emitter()` — emits trace events when emitter provided
- `test_summary_stats()` — summary computes mean/min/max correctly
- `test_evaluate_empty_predictions()` — handles empty strings gracefully
- `test_metric_failure_handling()` — metric exception doesn't crash harness (AR18)
- `test_batch_length_mismatch()` — raises ValueError if task_ids length != predictions
- `test_results_accumulation()` — multiple evals accumulate in results list

**File structure** (sketch):
```python
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
        assert compute_exact_match("hello", "hello") == 1.0

    def test_exact_match_different(self):
        assert compute_exact_match("hello", "world") == 0.0

    # ... more metric tests


class TestEvalHarness:
    """Test EvalHarness functionality."""

    @pytest.fixture
    def harness(self):
        return EvalHarness()

    @pytest.mark.asyncio
    async def test_evaluate_single(self, harness):
        result = await harness.evaluate("hello world", "hello world")
        assert result.metrics["exact_match"] == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_batch(self, harness):
        predictions = [("hello", "hello"), ("foo", "bar")]
        results = await harness.evaluate_batch(predictions)
        assert len(results) == 2

    # ... more harness tests
```

**After creating, run:**
```powershell
python -m pytest tests/test_eval_harness.py -v
```

Expected: 12-15 passed (all tests should pass without external dependencies).

---

## S5 — File-Scoped Verification

### S5.1: Syntax Check

```powershell
python -c "import ast; ast.parse(open('evals/harness.py').read())"
python -c "import ast; ast.parse(open('evals/metrics.py').read())"
python -c "import ast; ast.parse(open('evals/__init__.py').read())"
python -c "import ast; ast.parse(open('core/observability.py').read())"
```

Expected: All clean.

---

### S5.2: File-Scoped Mypy

```powershell
mypy evals/harness.py evals/metrics.py core/observability.py --ignore-missing-imports 2>&1 | Select-Object -Last 5
```

Expected: error count ≤ baseline (+5-10 acceptable for new code).

If errors: fix type annotations, re-run.

---

### S5.3: Ruff on Touched Files

```powershell
ruff check evals/harness.py evals/metrics.py evals/__init__.py core/observability.py tests/test_eval_harness.py 2>&1 | Select-Object -Last 3
```

Expected: 0 errors (file-scoped cleanup as you go).

If errors: fix before moving to closing.

---

## S6 — Baseline Reconciliation

### S6.1: Run Full Test Suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Expected**: ~1285 passed, 67 skipped (baseline 1170 + 15 new eval tests = 1185; actual may vary ±5).

**Baseline check**: PLANS.md expects 1170 baseline + ~15 new = ~1185 total. If count differs:
- ✅ Within ±5: acceptable, note delta in CHANGELOG
- ❌ Outside ±5: investigate (check if new tests are actually running), STOP if unclear

---

## Closing — Run `/jarvis-close`

Per AI_HANDOFF.md's Devin Plan Template, run the workflow — it handles the test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md (if a new pattern was captured), rule proposal (C9), docs commit, push, and post-push verification. Do not hand-roll the equivalent git/test/push sequence inline — `.windsurf/workflows/jarvis-close.md` is the single source of truth for this sequence. If the workflow is missing or fails, STOP and report.

Files expected to be staged by the workflow: `evals/harness.py`, `evals/metrics.py`, `evals/__init__.py`, `core/observability.py`, `tests/test_eval_harness.py`.

---

## Expected Outcomes

### Code Changes
- **New**: `evals/harness.py` (~250 lines)
- **New**: `evals/metrics.py` (~180 lines)
- **New**: `evals/__init__.py` (~5 lines)
- **New**: `tests/test_eval_harness.py` (~200 lines)
- **Modified**: `core/observability.py` (+5 lines for EVAL_COMPLETE, EVAL_WARNING event types)

### Test Changes
- **Tests**: +15 (metric + harness unit tests)
- **Baseline**: 1170 → 1185 passed (or within ±5)
- **Status**: All pass without external dependencies (metrics are pure functions; harness is self-contained)

### Static Analysis
- **Ruff**: 0 errors (file-scoped cleanup)
- **Mypy**: 294 → 300-305 errors (+6-10 acceptable for eval typing)
- **Bandit**: 3179 low (no new security issues)
- **pip-audit**: 19 CVEs (no new dependencies expected)

### Architectural Impact
- ✅ Eval harness integrated with trace emitter (optional, via constructor injection per AR11)
- ✅ Metrics module provides reusable scoring functions
- ✅ EvalHarness is async-friendly and accumulates results
- ✅ All code AR1-AR4 compliant (no circular imports, clean separation)

---

## Success Criteria

✅ Plan 62 is complete when:
1. All file edits finish syntax-clean (S1-S6)
2. All ruff/mypy errors fixed (or acceptable within baseline)
3. Full test suite passes with new eval tests included
4. Harness successfully evaluates sample predictions and computes metrics
5. Git tag `prompt-62` created and pushed to origin
6. CHANGELOG updated with Plan 62 entry
7. PLANS.md updated: completed prompts row, baseline, queue shift

**Gate**: Full test suite passes. Harness evaluates a batch of 10+ sample pairs and summary stats are computed without errors. All metrics (exact_match, token_f1, bleu, cosine_similarity) functional.

---

## Notes

- **Metrics library**: Use stdlib only (math, collections, dataclasses). Cosine similarity uses self-contained bag-of-words implementation (no sklearn dependency required). This keeps the eval harness lightweight and self-contained.
- **Trace integration**: Optional — system works without trace emitter. Eval results are always accumulated in harness.results. Both `_emit_eval_result` and `_emit_eval_warning` check `if not self.trace_emitter: return` at the start (AR11 compliance).
- **Batch validation**: `evaluate_batch()` explicitly validates that `task_ids` length matches `predictions` length if task_ids is provided. Raises `ValueError` with clear message to prevent silent misalignment (line 327-328).
- **Exception handling**: Metric failures are caught and logged (AR18 compliant). If a metric function raises an exception, the score defaults to 0.0 and an EVAL_WARNING trace event is emitted. Harness continues processing remaining metrics.
- **No external LLM calls**: Eval harness is purely offline. It does NOT call Claude, GPT, etc. (AR9 compliance).
- **Datetime**: All timestamps use `datetime.now(timezone.utc)` (OR20).
- **Async by default**: All public harness methods are async (AR12), even if they don't need it yet — future-proofs for when evals are wired into the improvement loop (Plan 63). Metric functions remain synchronous (CPU-bound, lightweight).

---

**Plan created**: 2026-06-23  
**Target execution**: Next available Devin session  
**Estimated duration**: 1.5-2 hours (including tests)
