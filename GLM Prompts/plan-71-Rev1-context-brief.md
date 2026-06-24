# Plan 71 Context Brief — Critical Hygiene: AR18 + Datetime + API Validation + Dead Code

## What to Review

1. **Scope discipline (OR15/OR16)** — Does the plan touch ONLY the 11 listed production files + 1 new test file? Are any edits to governance docs (AGENTS.md, PLANS.md, etc.) correctly deferred to the closing sequence?
2. **AR18 fix patterns** — Are the three patterns (A: bare pass, B: existing log, C: re-raise) correctly scoped? Does the "no runtime behavior change" constraint hold for each?
3. **Compliance test design** — Is `pytest.mark.xfail(strict=True)` the right call for the AR18 test, given that ~150 violations are deferred to Plan 72+? Should the test instead be scoped to ONLY the 8 in-scope files (and skip the rest)?
4. **API key validation** — Is soft-warning (HF_TOKEN) + hard-fail (ANTHROPIC/OPENAI/GOOGLE keys) the right split? Reference: `cli/adapter_factory.py` raises ValueError for required keys.
5. **Dead code handling** — Is "prefer deletion over assignment when uncertain" the right default? What's the rollback risk if a downstream consumer is missed?
6. **Test count delta** — Plan expects 1254 passed (1253 + 1 new AR18 test) + 1 xfailed. Is this within ±5 tolerance per PLANS.md?

## Key Pointers

- **PLANS.md Plan 70 baseline**: 1253 passed, 67 skipped. Full-repo mypy: 0 errors in 256 source files. Ruff: 0 errors. Bandit: 3384 low, 1 medium (B608 false positive in `memory/postgres_trace_store.py:161`), 0 high. Vulture: 23 findings. pip-audit: 19 CVEs (informational).
- **AGENTS.md AR18**: "No broad `except Exception: pass` without inline comment + WARNING trace." Already a rule since pre-Plan 60. Plan 71 enforces it on the 8 worst-offender files.
- **AGENTS.md OR20**: "Never mix naive/aware `datetime`. Use `datetime.now(timezone.utc)` everywhere." 12 violations survived Plan 58 (datetime UTC consolidation) — Plan 71 finishes the job for the remaining 5 files.
- **LANDMINES.md L6**: Source landmine for OR20 — naive/aware mixing causes runtime comparison failures.
- **LANDMINES.md L9**: Source landmine for OR27 — runtime type changes for mypy break test assertions. Plan 71 must NOT change runtime types when adding API key validation. Only adds new branches for missing-key case.
- **Plan 68 (last code-touching plan)**: Added SkillTier enum + CONTEXT.md. Test count went 1230 → 1253.
- **Plan 69**: Repo hygiene (governance doc fixes, stale file cleanup). No code changes.
- **Plan 70**: 5-plan milestone full scan. No code changes. Captured baselines.

## Architecture Notes

**AR18 cleanup is mechanical but not blind**. Each fix requires reading the surrounding code to write a meaningful "why" comment. The compliance test (S8) provides structural verification but cannot verify semantic correctness — that requires manual review.

**Three fix patterns** (S2):
- Pattern A: bare `pass`/return — add inline comment + `logger.warning(...)` with exc_info
- Pattern B: already logs — add inline comment only (existing log preserved)
- Pattern C: re-raises — inline comment only (caller sees the exception)

**API key validation asymmetry** (S6):
- `HF_TOKEN`: soft warning (optional — model acquisition is best-effort)
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY`: hard `ValueError` (required — calling code expects a working client)

This matches the existing pattern in `cli/adapter_factory.py`.

**Compliance test design** (S8): `pytest.mark.xfail(strict=True)` is proposed. Alternative: scope the test to ONLY the 8 in-scope files (using an explicit path filter). The xfail approach catches new violations across the whole codebase immediately; the scoped approach is stricter but requires path maintenance. Plan 71 chose xfail for global coverage.

## Known Risks

- **Test breakage from API key validation**: If any test asserts that missing API keys are silently ignored, that test breaks. Mitigation: S6 explicitly allows updating such tests in-scope (the contract IS changing).
- **AR18 cleanup changing exception flow**: If a `except Exception: pass` is changed to `except Exception: logger.warning(...)`, the exception is still swallowed — behavior preserved. But if Devin accidentally changes the except clause (e.g., narrows to a specific exception), behavior changes. Mitigation: S2 constraint "Do NOT change runtime behavior" + per-file targeted tests.
- **Dead code deletion risk**: Lines 224 and 350 in `system/model_acquisition.py` may be intended for future use. Mitigation: S7 decision rule "prefer deletion over assignment when uncertain" — silent dead code is worse than no code, and git history preserves the deletion if needed later.
- **Compliance test false positives**: The regex in S8 may flag false positives (e.g., `except Exception:` inside a string literal). Mitigation: ast-based parsing could be more accurate, but regex is simpler and the false positive rate is low for `except Exception:` patterns.
- **Mypy on `system/model_acquisition.py`**: The file already had 23 mypy errors fixed in Plan 66. Adding new branches for missing-key validation must not regress. Mitigation: file-scoped mypy in S9 step 3.

## Questions for Claude (open — apply findings at GLM's discretion)

1. Should the AR18 compliance test be scoped (only check 8 in-scope files) or global with `xfail`? Current plan: global + xfail.
2. Is "prefer deletion over assignment when uncertain" the right default for dead code at lines 224, 350? Current plan: yes.
3. Should the API key validation be a hard `ValueError` or a custom `MissingApiKeyError` exception class? Current plan: `ValueError` (matches existing `cli/adapter_factory.py` pattern).
4. Should Plan 71 also add a similar compliance test for OR20 (datetime.now(timezone.utc))? Current plan: no — defer to Plan 72+ to avoid scope creep.
5. Is batching 273 AR18 fixes across 8 files in one plan too aggressive? Should it be split into Plan 71 (4 files) + Plan 72 (4 files)? Current plan: one plan, batched by file, with per-file verification.
