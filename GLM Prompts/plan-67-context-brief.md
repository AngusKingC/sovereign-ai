# Plan 67 Context Brief — Skills and Tests Mypy Remediation

## Purpose
Review guide for Claude. Plan-67 fixes the remaining 134 mypy errors outside core/ and system/ (which are at 0 since Plan 66). Targets skills/ (42 errors, 7 files) and tests/ (76 errors, 9 files) plus 6 smaller files (16 errors).

## Current State
- **Tag**: prompt-66 on origin, verified
- **Tests**: 1231 passed, 68 skipped
- **Mypy (core/system)**: 0 errors (Plan 66)
- **Mypy (full-repo)**: 134 errors in 26 files (down from 294 at Plan 60)
- **Ruff**: 0 errors
- **Bandit**: 3,179 low / 0 medium / 0 high
- **pip-audit**: 19 CVEs (stable)
- **Vulture**: 23 findings

## Error Distribution

| Directory | Errors | Files | Top Files |
|---|---|---|---|
| tests/ | 76 | 9 | test_postgres_trace_store (15), test_query_handler (15), test_model_acquisition (14) |
| skills/ | 42 | 11 | email (12), notes (11), reminder (6), calculator (6), calendar (5) |
| memory/ | 2 | 1 | router.py (2) |
| cli/ | 4 | 2 | tui.py (2), rich_cli.py (2) |
| scripts/ | 4 | 1 | verify_tui_e2e.py (4) |
| workers/ | 1 | 1 | ollama_worker.py (1) |

## Error Type Patterns

### Skills errors
- `arg-type`: `str | None` where `str` expected (email, calendar)
- `union-attr`: `dict | list | None` missing methods (notes, reminder)
- `operator`: Unsupported operand types (calculator)
- `attr-defined`: Platform-specific modules (tts/winsound)

### Tests errors
- `union-attr`: `X | None` missing attributes (assert guard fixes)
- `arg-type`: Mock subclass not matching real class (type: ignore)
- `var-annotated`: Missing type annotations on fixture variables
- `override`: Test subclass signature mismatch (type: ignore[override])

### Other errors
- `assignment`: None not assignable to concrete types (memory, cli)
- `attr-defined`: Missing attributes on dynamic classes (scripts, workers)
- `abstract`: Missing abstract method implementation (workers)

## Key Decisions

1. **Tests are in-scope** — Unlike Plans 64-66, this plan explicitly allows test file edits for type remediation. Test behavior must not change.
2. **`# type: ignore` is acceptable** for: mock subclass mismatches, platform-specific modules, test-only methods on production classes. Each must include a comment explaining the reason (e.g., "mock isolation test, MockOrchestrator intentionally differs").
3. **OR28 + L10** — New rule and landmine for PowerShell zombie processes (platform-agnostic: Windows PowerShell check + Linux/macOS fallback)
4. **S1 STOP gate** — If core/ or system/ show any mypy errors, it's a regression from Plan 66

## Pre-Execution Triage (New in Review)

### S2.0 — Skills triage (READ-ONLY)
Before fixing any skills file, classify each:
- **Is the union type intentional or accidental?** Intentional → `isinstance()` guards. Accidental → consider normalizing return type.
- **Platform-specific concerns?** e.g., winsound in tts.
- **Effort estimate**: easy (guards), medium (isinstance + cast), hard (interface redesign → STOP and report)

### S3.0 — Test fixture audit (READ-ONLY)
Before fixing any test file, categorize fixtures:
- **Required but not typed**: Add return type annotation
- **Optional by design**: Add `assert x is not None` in test body
- **Mock mismatches**: Add `# type: ignore[arg-type]` with explanatory comment

## Decision Guide: assert vs. if/return

- **`assert x is not None`**: None is a programmer error — should never happen in production
- **`if x is None: return <default>`**: None is a valid, recoverable input (from config, env vars, user input)
- **When in doubt**: Read the caller context. Internal constructors → assert. External inputs → if/return.

## Rollback Strategy

If a fix breaks a test: `git checkout -- <file>` to revert. Max 2 iterations per file, then STOP and report.

## # type: ignore Tracking

Log every `# type: ignore[...]` added: file, line, reason. S5.3 flags any file with >3 ignores for future refactoring.

## New Rules
- **OR28**: PowerShell session cleanup — close sessions after use, check for orphans every 20 commands (platform-agnostic: Windows + Linux/macOS fallback)
- **L10**: Zombie PowerShell processes from Devin execution

## Verification Tiers (S5)

| Scenario | Action |
|---|---|
| Mypy full-repo ≥50 | Re-run baseline, file detailed report. Plan 67 partial. |
| Mypy full-repo 20–49 | Document as "partial remediation" in CHANGELOG |
| Mypy full-repo <20 | Major success for Plan 70 milestone |
| Test count drops >5 | `git diff tests/` to investigate before proceeding |
| File has >3 `# type: ignore` | Flag for future refactoring |

## Risk Assessment
- **skills/ (42 errors)**: Medium — some require behavioral understanding (email IMAP/SMTP, calculator operator mapping). S2.0 triage mitigates.
- **tests/ (76 errors)**: Low — mostly mechanical fixes (assert guards, type annotations, type: ignore for mocks). S3.0 audit mitigates.
- **Other (16 errors)**: Low — simple fixes in small files

## Files to Review
- Plan: `/home/z/my-project/download/plan-67.md`
- Repo: `git clone https://github.com/AngusKingC/sovereign-ai.git` (tag prompt-66)
