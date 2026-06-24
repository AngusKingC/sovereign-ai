# Plan 65 Context Brief -- Mypy Remediation Phase 2

## What to Review

1. **S0 order fix** -- S0.3/S0.4 governance doc commits now happen AFTER `/jarvis-open` (clean copy verified) and BEFORE scope declaration. Correct?
2. **system/ deferred** -- `system/model_acquisition.py` removed from scope. Is deferring to a system-focused plan the right call?
3. **Decision trees** -- S2-S4 now have explicit decision trees instead of vague "check if" guidance. Are they concrete enough for Devin?
4. **STOP thresholds** -- S1 has explicit +/-1 per file and total error bounds. S6 has explicit test count tolerance (1230-1234). Are these tight enough?

## Key Pointers

- Plan 64 fixed 33 errors in 14 core files. Remaining in scope: 13 errors in 6 files (system/ deferred).
- Pattern is consistent: enum vs string (10 errors), UUID vs string (3 errors), type mismatch (1 error).
- `core/session.py` has 6 errors -- all `TaskPriority`/`TaskStatus` string literals.
- OR27 was proposed in Plan 64 closing but never added to AGENTS.md. Plan 65 adds it in S0.3.
- L9 captures the failure pattern from Plan 64: runtime type changes for mypy broke test assertions.

## Architecture Notes

**Compatibility shim pattern** (OR27): When type fixes require interface changes but tests are read-only, add shims that delegate to new implementation while accepting old signature. Mark deprecated.

**Landmine L9**: Runtime type changes (e.g., dict -> Message, str -> enum) break tests that assert on old types. Always verify test assertions before changing runtime types.

## Known Risks

- **Enum fixes may break tests** if tests assert on string values. Use OR27 compatibility shims.
- **UUID fixes may affect database serialization** -- check if UUID is stored as string in Postgres.
- **S4 decision trees may still be ambiguous** for complex inheritance hierarchies.
- **Devin missed AGENTS.md/LANDMINES.md updates in Plan 64** -- S0.3/S0.4 explicitly check and backfill.

## Questions for Claude

1. Should `system/model_acquisition.py` be deferred or included? (4 errors, different domain)
2. Are the S1 STOP thresholds (per-file +/-1, total 10-14) too tight or too loose?
3. Is the S6 test tolerance (1230-1234 passed) reasonable for a type-remediation plan?
