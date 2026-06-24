# Plan 66 Context Brief -- System Cleanup and Final Core Hardening

## What to Review

1. **S2 pre-step ordering** -- Is the `from __future__ import annotations` check correctly placed as a pre-step before Error 4 (and any other union syntax fixes)?
2. **S2 Error 2 httpx verification** -- Is the `inspect.signature` approach the right way for Devin to check httpx types, or should we suggest reading source code directly?
3. **S3 causality check** -- Is the three-way classification (pre-existing / caused by Plan 65 / unrelated new) clear enough for Devin to apply without ambiguity?
4. **S5 net reduction requirement** -- Is requiring error count < S1 baseline (not just <=) too strict? What if S1 had 0 errors and S3 introduces 1?
5. **S6 tolerance tightened** -- Changed from 1230-1234 (±2) to 1231-1233 (±1). Is this too tight for Windows CI variance?

## Key Pointers

- Plans 64-65 fixed 49 mypy errors across 21 core files.
- `system/model_acquisition.py` has 4 deferred errors from Plan 65.
- Plan 68 is already scheduled as a 5-plan milestone full scan.
- OR27 (compatibility shims) is now in AGENTS.md; L9 (runtime type changes break tests) is in LANDMINES.md.

## Architecture Notes

**system/ domain**: `model_acquisition.py` handles model downloading, registry, and resource checking. Different domain from `core/` but still critical path for worker execution.

**Cross-file risk**: Plan 65 changed enum values in `session.py`, `task_state_machine.py`, etc. Callers in other files may still pass strings, causing new mypy errors visible only in full-repo scan.

## Known Risks

- **system/ may have complex dependencies** -- ModelRegistry, AsyncClient, ResourceManager interactions.
- **Cross-file errors may be numerous** -- If many callers still use string literals, S3 could expand significantly. S1.5 and S3 STOP thresholds mitigate this.
- **No system/ test coverage** -- S0.3 pre-check notes this. S2 fixes must be verified via mypy alone, not tests.
- **Plan 68 overlap** -- S1 full-repo scan results saved to `plan-66-baseline.log` for Plan 68 reference to avoid duplication.
- **S5 net reduction requirement** -- If S1 baseline is very clean (e.g., 2 errors) and S3 introduces 1 new error, net reduction is impossible. The STOP condition handles this.

## Questions for Claude

1. Is the S2 `inspect.signature` approach for httpx type checking reliable, or should Devin read the source directly?
2. Is the S6 tolerance of 1231-1233 (±1) too tight for Windows CI, or appropriately strict?
3. Should S5 allow error count == S1 count if the errors are "better" (e.g., fewer files affected), or is strict net reduction correct?
