# Plan 62 Context Brief — Eval Harness Implementation

**Plan**: Eval Harness Implementation (Priority 3)  
**Status**: Ready for Claude review  
**Date**: 2026-06-23

---

## What This Plan Does

Implements a self-contained evaluation harness for measuring LLM output quality. The harness computes 4 metrics (exact match, token F1, BLEU, cosine similarity) and returns structured eval results. It optionally integrates with the trace emitter for recording eval events.

**Key scope boundaries**:
- ✅ Only touches `evals/` (new), `core/observability.py` (2 enum values), `tests/`
- ❌ Does NOT touch memory/, cli/, web/, skills/, adapters/
- ❌ No external LLM calls (AR9 compliant)
- ❌ No async I/O in metrics (they're pure functions)

---

## File Changes Summary

| File | Type | Lines | Purpose |
|---|---|---|---|
| `evals/metrics.py` | New | ~180 | 4 metric functions: exact_match, token_f1, bleu, cosine_similarity |
| `evals/harness.py` | New | ~250 | EvalHarness class, EvalResult dataclass, batch eval logic |
| `evals/__init__.py` | New | ~5 | Module imports |
| `tests/test_eval_harness.py` | New | ~200 | 12-15 unit tests |
| `core/observability.py` | Modify | +5 | Add EVAL_COMPLETE, EVAL_WARNING to TraceEventType enum |

---

## Potential Issues to Catch

1. **Type annotations**: EvalResult is a dataclass; check that __init__ signature is clean and return types are explicit.
2. **Async/sync mismatch**: Metrics are synchronous (CPU-bound), but EvalHarness methods are async. This is intentional (harness will be awaited in Plan 63).
3. **Trace emitter injection**: Optional parameter, should not break if None. Check that _emit_eval_result and _emit_eval_warning handle None gracefully.
4. **Metric failures**: Plan includes AR18-compliant try/except in evaluate() loop. Verify exception is caught and logged, not silent.
5. **Enum extension**: TraceEventType gains 2 new values. Verify no breaking changes to existing event types.
6. **Test coverage**: Should have at least 1 test per metric function, plus 8-10 harness tests. Check that test count aligns with expectations (~1185 total).

---

## Known Good Patterns (from recent plans)

- **Fire-and-forget tasks**: Plan 61 established asyncio.create_task pattern for non-blocking operations. This plan doesn't use it, but async methods are available if needed in Plan 63.
- **Constructor injection**: Plan 61 showed how to optionally inject dependencies (trace_emitter) without requiring them. Eval harness follows the same pattern.
- **Timestamp handling**: All dates use `datetime.now(timezone.utc)` (OR20). EvalResult should too.

---

## Questions for Claude

1. ✅ **Metrics implementation**: Are the 4 metric implementations reasonable (exact_match, token_f1, bleu, cosine_similarity)? Any edge cases (empty strings, unicode) to guard?
2. ✅ **Harness interface**: Is the batch eval signature clean? Should task_ids be required or optional?
3. ✅ **Trace integration**: Is the optional trace_emitter pattern clear? Should eval warnings be async or sync?
4. ✅ **Test structure**: Do the sketched tests cover the key paths (success, partial match, exception handling)?

---

## Red Flags to Watch

- ❌ **Scope creep**: If you spot a suggestion to wire this into memory/ or adapters/, that's Plan 63 (not yet).
- ❌ **Async-inside-metric**: Metrics must stay synchronous. Any suggestion to make them async should be questioned.
- ❌ **LLM calls in harness**: Do not add any Claude/GPT calls to the eval harness itself. (That's Plan 62.5+.)
- ❌ **Breaking observability changes**: Adding new enum values is safe; renaming or removing existing TraceEventType values is not.

---

## What Happens After Claude Review

1. Claude reviews the plan and files above.
2. User pastes Claude's findings back to GLM.
3. GLM applies blocking/high findings and updates the plan files.
4. Devin executes the final plan.
5. Devin reports results back to GLM for Step 2 verification.

---

**Ready for review** ✅
