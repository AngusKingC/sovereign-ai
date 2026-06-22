# Plan 59 — Ruff Cleanup (113→0) + B108 Scoped Suppressions

**Prompt number**: 59
**Priority**: P2 (Phase 1 debt cleanup)
**Estimated scope**: ~113 ruff fixes + 22 B108 nosec annotations (per handoff Plan 55 baseline)
**Baseline test count**: 1166 passed, 56 skipped (UNVERIFIED per B2 — actual captured at S1.1)
**Baseline ruff**: 113 errors across 8 rules (per handoff Plan 55 baseline; actual captured at S1.2)
**Baseline B108**: 22 findings across 5 test files (per handoff Plan 54 deferral list; actual captured at S1.3)

> **L19 compliance note**: GLM must NOT run ruff/bandit/pytest/mypy/pip-audit/vulture on clone. All counts in this plan come from (a) the handoff's Plan 55 full-scan baseline, or (b) Devin's execution log captured at S1.1/S1.2/S1.3. Do not trust counts from GLM's Linux sandbox — different OS, different Python env, different tool versions.

---

## Section 0: Rules (read first, follow always)

**Note**: AGENTS.md is now active (always-on). The 22 stable rules in AGENTS.md (which include the temp-file rule, L15) are already loaded — don't repeat them here. Section 0 contains only the evolving L-rules that grow via L20 self-evolution.

**AGENTS.md SHA**: d296e8091d616cd90b14635d49a2a8036327df64 (captured at S0.4)

**Tripwire**: this plan assumes AGENTS.md rules 1-22 as of 2026-06-22 (post-58.7). If AGENTS.md has been modified since, STOP and verify the stable rules haven't drifted from what L1-L26 below assume.

**Note on L-numbering**: handoff "Known landmines" also uses labels L1-L24 with DIFFERENT meanings (handoff L20 = "line numbers verified against clone SHA," but this Section 0 L20 = "self-evolution rule proposal"). This collision is tracked as handoff landmine L25, deferred fix to Plan 60 (renumber handoff landmines to M1-M24). When this plan cites an L-rule, it refers to Section 0 above, NOT the handoff landmines.

### Evolving rules (L1-L26)

**L1.** Follow the plan's verification gates in order. Run them, paste evidence, STOP on failure. Never assert file content from memory — always read the actual file first.

**L2.** Run the relevant test file after each file change. Run the full suite at gates, not after every edit.

**L3.** When you fix a bug, grep for the same pattern across the codebase before closing the prompt.

**L4.** Never silently substitute. If the spec says X, implement X. When in doubt, STOP and report. Do not improvise.

**L5.** Do not expand scope when tests find pre-existing issues outside the plan.

**L6.** TraceEvent is defined in `core/observability.py`. Use exactly these fields: `event_type`, `component`, `level`, `message`, `data`, `duration_ms`.

**L7.** Every class that emits trace events MUST use constructor-injected emitter. Never use the global `emit_trace()` function.

**L8.** Raise domain exceptions OUTSIDE try-except blocks. Never broad-except without a trace event.

**L9.** When fixing a production file, fix its test file in the same step.

**L10.** Do not remove working implementation to make a test pass.

**L11.** Verify field and class names against the actual schema file before using them.

**L12.** Patch at the location where a class is defined, not where it is used.

**L13.** Never mutate Pydantic model instances after construction in tests.

**L14.** Tests must verify behaviour, not just confirm the code runs.

**L15.** In tests, construct `MemoryTraceEmitter()` and pass it via constructor injection. Retrieve events via `emitter.get_events()`, never `emitter.events`.

**L16.** The CHANGELOG must match the commit. Verify before reporting completion.

**L17.** CHANGELOG format is simplified — ~10 lines per plan. Title, changed files, result, test count math. Record only non-trivial decisions.

**L18.** The correct closing sequence for every prompt: test → ruff → mypy (file-scoped) → commit → tag → tag-verify → CHANGELOG → handoff → rule-proposal → docs-commit → push → post-push-verify. **Or just run `/jarvis-close`.** Even docs-only plans must create a tag.

**L19.** Tests and production code MUST use the same timezone strategy. Never mix naive and aware `datetime`. Use `datetime.now(timezone.utc)` everywhere. Never `datetime.utcnow()` or bare `datetime.now()`.

**L20.** When you hit a recurring error pattern or a landmine not covered by these rules, propose a new rule to GLM in your closing report. Format: Trigger / Recurrence / Proposed rule / Anchor / Why existing rules didn't catch it. If none, list patterns considered with reasons. Silence is NOT acceptable.

**L21.** CHANGELOG entries are ALWAYS appended to the END using the temp-file pattern. NEVER insert at the top.

**L22.** This project runs on Windows. Use PowerShell, not Unix commands.

**L23.** Verification gates must check the actual scope of prior plans, not the entire codebase.

**L24.** Run scan tools SEQUENTIALLY, never in parallel. Each tool's output must be captured and verified before running the next.

**L25.** When removing unused parameters identified by vulture in test files, verify the parameter is not required by pytest fixture dependencies or framework protocols. If removal breaks tests, defer to Category C.

**L26.** When grepping for `datetime.utcnow`, always search for BOTH patterns: `datetime.utcnow()` (with parens) AND `datetime.utcnow` (without parens — function references like `default_factory`). Use `Select-String "datetime\.utcnow"` without the parentheses to catch both patterns.

---

## Why this plan exists

Two debt items bundled into one plan (both mechanical, low-risk, prepare the workbench for Phase 2's measurement layer):

1. **Ruff cleanup**: 113 errors across 8 rules → target 0. Uses safe auto-fix, unsafe auto-fix with triage, and manual fixes.
2. **B108 scoped suppressions**: 22 bandit findings → 0 via scoped `# nosec B108` annotations. CI already skips B108 via `-s B108`, but scoped suppressions are strictly better (fail loudly on new violations). After suppressions, remove the `-s B108` skip from CI.

**This is the first plan using the Devin Desktop config** — AGENTS.md is always-on, `/jarvis-close` and `/jarvis-verify` workflows are available, `jarvis-b108-suppress` and `jarvis-f841-triage` skills auto-invoke.

---

## Opening steps (S0)

### S0.1 — Verify prompt-58.7 tag on origin

```powershell
git ls-remote --tags origin | Select-String "prompt-58.7"
```

Expected: returns `66315df...`. If empty, STOP — prompt-58.7 wasn't pushed.

### S0.2 — Verify local working copy (do NOT pull)

```powershell
git status
git branch --show-current
git rev-parse HEAD
```

Expected:
- `git status`: "nothing to commit, working tree clean"
- `git branch --show-current`: `master`
- `git rev-parse HEAD`: the post-58.7 master HEAD (commit `66315df` or its descendant)

**Do NOT run `git pull origin master`.** Devin's local working copy is authoritative. The previous-tag check at S0.1 is sufficient to confirm prompt-58.7 was pushed.

### S0.3 — Verify Plan 59 review fixes are applied locally

This plan had a GLM review (2026-06-22) that produced 4 commits on branch `review/plan-59-revisions` in GLM's sandbox. GLM cannot push to origin (no credentials). The review fixes must be applied to Devin's local copy BEFORE this plan starts. Verify they are present:

```powershell
# B1 fix: prompt-57 should appear exactly ONCE in CHANGELOG (was 3 times before fix)
(Get-Content CHANGELOG.md | Select-String "^## .* prompt-57").Count
# Expected: 1

# B2 fix: 58.6 and 58.7 entries should have NOTE blocks about baseline contradiction
(Get-Content CHANGELOG.md | Select-String "B2 fix from Plan 59 review").Count
# Expected: 2

# Handoff optimizations: repo URL should be present
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "github.com/AngusKingC/sovereign-ai").Count
# Expected: >= 1

# Handoff optimizations: "do NOT pull" should be in opening steps
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "Do NOT run.*git pull").Count
# Expected: >= 1
```

If any check fails, STOP — the review fixes have not been applied to the local copy. Apply them manually:
1. Copy `CHANGELOG.md` from GLM's download folder to `c:\Jarvis\CHANGELOG.md`
2. Copy `SOVEREIGN_AI_HANDOFF.md` from GLM's download folder to `c:\Jarvis\SOVEREIGN_AI_HANDOFF.md`
3. Copy `plan-59.md` from GLM's download folder to `c:\Jarvis\GLM Prompts\50s\plan-59.md`
4. Commit the docs changes: `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: apply Plan 59 review fixes (B1, B2, handoff optimizations)"`
5. Re-run S0.3 checks.

### S0.4 — Capture AGENTS.md SHA (per handoff L20)

```powershell
git rev-parse HEAD:AGENTS.md
```

Record this SHA in the plan's Section 0 tripwire. If AGENTS.md has been modified since the post-58.6 state (commit `2ef110a`), STOP and verify the stable rules haven't drifted from what L1-L26 in Section 0 assume.

---

## Step 1 (S1) — Capture baseline (run SEQUENTIALLY per L24)

### S1.1 — Test count baseline

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
```

Expected: check AGENTS.md for current baseline. The handoff says "1166 passed, 56 skipped" but per B2 from Plan 59 review, this is UNVERIFIED — the CHANGELOG entries for 58.5/58.6/58.7 are contradictory (see NOTE blocks in CHANGELOG.md). Capture the actual count. If actual is 1167/55 (not 1166/56), update the handoff and CHANGELOG notes accordingly. If actual is 1166/56, investigate per L3 landmine (silent skip in 58.6) — identify which test moved from passed to skipped.

### S1.2 — Ruff baseline

```powershell
ruff check . --statistics 2>&1
```

Expected breakdown (verified via clone — actual may differ slightly):
```
 47  F841   [-] unused-variable
 22  E402   [ ] module-import-not-at-top-of-file
 22  F821   [ ] undefined-name
 15  F541   [*] f-string-missing-placeholders
  3  F811   [*] redefined-while-unused
  2  F401   [*] unused-import
  1  E731   [ ] lambda-assignment
  1  E741   [ ] ambiguous-variable-name
```

Total: ~113 errors. Record the actual count.

### S1.3 — B108 baseline

```powershell
bandit -r tests/ -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108" | Measure-Object -Line
```

Expected: 22 B108 findings.

**STOP condition**: if actual counts differ from expected by >5, investigate per AGENTS.md rule 15 (baseline reconciliation).

---

## Step 2 (S2) — Safe auto-fixes (20 errors: F541 + F401 + F811)

### S2.1 — Run safe ruff fix

```powershell
ruff check . --fix
```

Expected: fixes F541 (15 f-strings), F401 (2 unused imports), F811 (3 redefinitions) = 20 errors.

### S2.2 — After fix, run `/jarvis-verify`

Syntax check all touched files, diff check, run tests.

### S2.3 — Re-check ruff count

```powershell
ruff check . --statistics 2>&1
```

Expected: ~93 errors remaining (113 - 20 fixed). Record actual.

---

## Step 3 (S3) — F841 unsafe auto-fix (47 errors)

**The `jarvis-f841-triage` skill auto-invokes here.** Follow its A/B/C triage procedure.

### S3.1 — Triage ALL F841 findings (per-finding, NOT bulk)

```powershell
ruff check . --select F841 2>&1
```

For EACH of the 47 findings, read the line and classify:
- **Category A** (safe auto-fix): RHS is TRULY pure — no function calls, no attribute access that could be a property with side effects, no subscript access that could trigger `__getitem__` overrides, no descriptor getters. Only literals and simple variable references qualify. One-line manual scan of each RHS required.
- **Category B** (manual fix): RHS has side effects. Remove `variable = `, keep RHS.
- **Category C** (defer): framework-required (pytest fixture, middleware, pydantic validator). Add `# noqa: F841 -- <reason>`.

**Do NOT skip triage and run `--fix --unsafe-fixes` without reviewing each finding.**

**Reclassification rule**: if a Category A fix fails verification (S3.3 `/jarvis-verify` catches a test failure or side effect), reclassify that finding to Category B (manual fix — remove `variable = `, keep RHS) and re-apply. Do NOT just re-run the unsafe fix.

**Vulture overlap note**: Some F841 findings in `tests/` may overlap with Plan 57's vulture Category C deferrals (mock_client x9 in adapter test fixtures, req x4 in test_security middleware tests, raw_output x3 in test_task_state_machine, auth x1 in test_serve — see Plan 57 closing notes in CHANGELOG.md). If a finding corresponds to a Plan 57 deferral, classify as Category C with `# noqa: F841 -- Plan 57 vulture Category C deferral (same pattern: <mock_client|req|raw_output|auth>)`.

### S3.2 — Apply F841 fixes after triage

Category A: `ruff check . --select F841 --fix --unsafe-fixes` (only after confirming all A are truly pure)
Category B: edit each individually (NEVER `replace_all`). Remove `variable = `, keep RHS.
Category C: add `# noqa: F841 -- <reason>`

### S3.3 — After fixes, run `/jarvis-verify`

### S3.4 — Re-check ruff

```powershell
ruff check . --statistics 2>&1
```

Expected: ~46 errors remaining (E402 + F821 + E731 + E741). Record actual.

---

## Step 4 (S4) — Manual fixes (46 errors: E402 + F821 + E731 + E741)

### S4.1 — E402: module-import-not-at-top-of-file (22 errors)

For each E402 finding:
1. Read the file
2. If import CAN be moved to top (no circular dependency): move it
3. If conditional/TYPE_CHECKING import: add `# noqa: E402 -- <reason>`

**Specific fix for schemas.py line 442**: the `from typing import Protocol, runtime_checkable` mid-file should be moved to the existing import block at line 10. Change `from typing import Any, Optional` to `from typing import Any, Optional, Protocol, runtime_checkable` at line 10, delete line 442, remove the `# noqa: E402`. (This was flagged in Claude's review of Plan 58.6.)

### S4.2 — F821: undefined-name (22 errors) — with explicit decision procedure

**CAUTION**: F821 can be REAL BUGS. Apply this 3-step procedure:

**Step 1**: Grep the file for the undefined name:
```powershell
Select-String "<undefined_name>" -Path <file>
```

**Step 2**: Grep the codebase:
```powershell
Select-String "<undefined_name>" -Path . -Recurse -Include *.py
```

**Step 3**: Classify — **classify each occurrence independently**. Don't assume a fix that worked once worked everywhere. The same undefined name may have different correct resolutions in different files (e.g., a typo in one file, a missing import in another).
- **Missing import** (exists elsewhere): add import
- **Typo** (name exists but different spelling): fix reference
- **Forward reference** (class referenced before definition): use `from __future__ import annotations`
- **TYPE_CHECKING import** (only needed for type hints): move to `if TYPE_CHECKING:` block
- **Genuinely undefined** (doesn't exist ANYWHERE): **STOP and report** — runtime crash

**Specific fix for notification.py line 54**: `TelegramGateway` type annotation is unresolvable (core/ can't import from gateways/ per architecture rule 16). Use TYPE_CHECKING guard:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gateways.telegram.gateway import TelegramGateway
```
Remove the `# noqa: F821` suppression.

**STOP condition**: if any F821 is a genuinely undefined name, STOP and report. Commit S2-S3 fixes independently first, then report.

**(Note: an earlier draft of this plan referenced a "REV2 rollback note" — that note does not exist in this fresh rewrite and the reference has been removed. If S2-S3 need to be committed independently of S4-S6, use the standard checkpoint commit pattern: `git commit -m "checkpoint: prompt-59 S2-S3 (safe + F841 fixes)"` without tagging, then continue from S4.)**

### S4.3 — E731 + E741 (2 errors)

- **E731** (1): convert `x = lambda y: ...` to `def x(y): ...`
- **E741** (1): rename ambiguous single-letter variable (e.g., `l` → `length`)

### S4.4 — After manual fixes, run `/jarvis-verify`

### S4.5 — Re-check ruff

```powershell
ruff check . --statistics 2>&1
```

Expected: `0 errors` or only `# noqa`-suppressed findings. Record actual.

---

## Step 5 (S5) — B108 scoped suppressions (22 findings)

**The `jarvis-b108-suppress` skill auto-invokes here.** Follow its procedure.

### S5.0 — Verify all B108 findings are in tests/ (scope check)

```powershell
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108" | Measure-Object -Line
```

Expected: `22` (must equal the S1.3 tests/-only count). If > 22, STOP — production B108 findings exist. Expand S5.2 to suppress those too with reason `# nosec B108 -- local-first; <justification>` for production, or fix the underlying hardcoded temp path. **Per handoff Plan 54 deferral list**: all 22 B108 findings are in tests/ across 5 files — test_approval_gate.py (11), test_query_handler.py (7), test_skill_registry.py (2), test_security.py (1), tests/skills/test_file_writer.py (1). Devin verifies this at S5.0 by comparing full-repo count to tests/-only count.

### S5.1 — Get exact line numbers from bandit

```powershell
bandit -r tests/ -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108"
```

### S5.2 — For each finding, add scoped `# nosec B108` on the EXACT line bandit reports

Format: `# nosec B108 -- local-first; test fixture path`

Edit each occurrence individually (NEVER `replace_all`).

### S5.3 — Verify all B108 suppressed

```powershell
bandit -r tests/ -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108" | Measure-Object -Line
```

Expected: `0`.

### S5.4 — Run tests

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

Expected: same as S1.1 baseline.

### S5.5 — Remove CI's `-s B108` skip flag

Edit `.github/workflows/ci.yml`:
```yaml
# Before:
run: bandit -r . -ll -s B108 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache

# After:
run: bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache
```

Verify locally:
```powershell
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108" | Measure-Object -Line
```
Expected: `0`.

### S5.6 — Verify bandit config doesn't globally skip B108

```powershell
Select-String "B108|skips|skip" -Path .bandit,pyproject.toml -ErrorAction SilentlyContinue
```

Expected: no B108 references in bandit config files. If found, remove the global skip before relying on S5.5's verification -- otherwise the verification would be vacuously true (B108 skipped at config level, not at CI level).

---

## Step 6 (S6) — Final verification

### S6.1 — Ruff clean
```powershell
ruff check . 2>&1 | Select-Object -Last 3
```
Expected: `All checks passed!` or `Found 0 errors.`

### S6.2 — Bandit B108 clean
```powershell
bandit -r tests/ -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108" | Measure-Object -Line
```
Expected: `0`.

### S6.3 — Full test suite
```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```
Expected: same as S1.1 baseline.

---

## Closing: Run `/jarvis-close`

**Before relying on `/jarvis-close`**, verify it exists and contains the expected steps (per L1 — never assert file content from memory):
```powershell
Test-Path .windsurf\workflows\jarvis-close.md
Get-Content .windsurf\workflows\jarvis-close.md | Select-String "tag|push|verification"
```
If the file doesn't exist or is missing expected steps, STOP and report — don't improvise the closing sequence from memory. Fall back to the handoff's C1-C13 steps (Section: Opening + Closing steps).

Run the `/jarvis-close` workflow with tag `prompt-59`. It handles C1-C13 automatically.

**C8 CHANGELOG note**: per AGENTS.md rule 8 (suppression accounting), list every `# nosec` and `# noqa` added:
```
Suppressions added:
- # nosec B108 x22 — local-first; test fixture paths (5 test files)
- # noqa: F841 x<N> — <reason per finding>
- # noqa: E402 x<N> — <reason per finding>
```

**C9 rule proposal**: reflect on the F841 triage, F821 investigation, and B108 suppression process. Did any "safe" fix break tests? Did any F821 turn out to be a real bug? If so, propose a rule.

---

## STOP conditions

1. **S0.1**: prompt-58.7 tag not on origin
2. **S1.1**: test count ≠ baseline — **CRITICAL**: per B2 from Plan 59 review, the 1166/56 baseline is UNVERIFIED (CHANGELOG entries for 58.5/58.6/58.7 are contradictory). Capture actual count at S1.1. If actual count is 1167/55, a test was NOT silently skipped in 58.6 (the 58.6 CHANGELOG entry was simply misreported). If actual count is 1166/56, investigate per L3 landmine (silent skip) — identify which test moved from passed to skipped between 58.5 and 58.6. Update the 58.6 and 58.7 CHANGELOG NOTE blocks with the finding.
3. **S1.2**: ruff count differs from 113 by >5 (per handoff Plan 55 baseline; Devin captures actual at S1.2)
4. **S3.3**: tests fail after F841 fix — revert offending file
5. **S4.2**: any F821 is a genuinely undefined name — STOP, commit S2-S3 independently, report
6. **S5.0**: full-repo B108 count > tests/-only count (production B108 findings exist — expand scope before suppressing)
7. **S5.3**: B108 suppressions don't suppress all findings
8. **S5.6**: bandit config globally skips B108 (S5.5 verification would be vacuous)
9. **S6.3**: test count drops
10. **C13**: prompt-59 tag not on origin
11. **Pre-Plan-59 (already done)**: B1 (duplicate prompt-57 CHANGELOG entries) and B2 (58.6/58.7 baseline contradiction) were fixed in commit `9fe2cf5` on branch `review/plan-59-revisions` before this plan starts. If running this plan from a clean checkout, verify those fixes are present: `git log --oneline | Select-String "B1+B2 fix"`.

---

## Out of scope (deferred)

- **283 mypy errors** → Phase 4 (Plans 66-74)
- **20 vulture findings** → permanent (Category C deferrals)
- **19 pip-audit CVEs** → wait for upstream patches
- **Marine stack** → deferred indefinitely
- **Eval harness / trace store** → Phase 2 (Plans 61-63b)
- **Postgres persistence** → Phase 3 (Plans 64-65)
- **Any F821 that's a real runtime bug** → STOP and report
