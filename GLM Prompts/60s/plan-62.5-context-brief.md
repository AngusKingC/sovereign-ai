# Plan 62.5 Context Brief — Eval Harness Validation

## What to Review

1. **Scope discipline** — Does the plan stay within `evals/` and `tests/`? No edits to `core/`, `memory/`, `adapters/`, etc.
2. **Validation data quality** — Are the 10-15 JSON fixture entries realistic and do they cover edge cases?
3. **Test coverage** — Do the 8 new validation tests actually verify metric alignment with human judgment?
4. **Harness refinement scope** — Are the allowed adjustments minimal and stdlib-only? No external deps.
5. **Baseline expectations** — ~1214 passed (+20), 67 skipped. Is this reasonable?

## Key Pointers

- `evals/harness.py` (Plan 62): EvalHarness with evaluate/evaluate_batch/summary, trace emitter integration
- `evals/metrics.py` (Plan 62): 4 stdlib-only metrics (exact_match, token_f1, bleu, cosine_similarity)
- `tests/test_eval_harness.py` (Plan 62): 24 tests covering metrics + harness. New tests appended here.
- `core/observability.py`: TraceEvent uses TraceComponent enum (not string literals). Plan 62 fixed this.
- Current baseline: 1194 passed, 67 skipped. Plan 62.5 adds ~20 validation tests.

## Known Risks

- **Metric refinement creep**: The plan allows minor metric adjustments. Watch for scope expansion beyond "minimal."
- **External dependency temptation**: If validation reveals metrics need NLTK/scikit-learn, the plan says STOP. Verify this is respected.
- **JSON fixture maintenance**: Static data files need to be committed. Ensure they're in `evals/`, not repo root.

## Questions for Claude

1. Are 8 validation tests sufficient, or should we add more categories (e.g., multilingual, code output)?
2. Should the validation suite be parameterized (one test per task) or batched (one test per category)?
3. Is the "no external deps" constraint too strict for realistic eval validation?
