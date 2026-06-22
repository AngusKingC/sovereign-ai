# Plan 47: Fix E402 import ordering, add missing `gateways/__init__.py`, and remove flagged unused imports in web/gateways files

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise. Update the
> status row in `plans/README.md` when done.
>
> Drift check (run first):
> `git diff --stat prompt-46..HEAD -- web/server.py web/middleware/auth_middleware.py gateways/telegram/gateway.py adapters/gemini.py`
> Also run (read-only drift on files Plan 44/45/46 touched):
> `git diff --stat prompt-46..HEAD -- cli/serve.py cli/command_history.py core/session.py core/schemas.py cli/tui.py core/escalation.py core/memory_router.py core/approval_gate.py workers/echo_worker.py core/input_sanitiser.py system/trajectory_exporter.py`
> If any in-scope file changed since prompt-46, compare Current state
> excerpts against live code; on mismatch, STOP. If `cli/serve.py`
> changed, confirm the `input_sanitiser` kwarg is still passed to
> `Orchestrator(...)` — if not, STOP (Plan 44 wiring was reverted). If
> `core/memory_router.py` changed, confirm `def fetch_by_type` is still
> present (Plan 45) — if not, STOP. If `cli/command_history.py`,
> `core/session.py`, or `workers/echo_worker.py` changed, confirm the
> F821 fixes from Plan 46 (uuid4 import, Task module-level import,
> TYPE_CHECKING block) are still present — if not, STOP.

## Status
- Priority: P2
- Effort: S
- Risk: LOW
- Depends on: prompt-46 (F821 + F811 + critical F841 cleanup complete)
- Planned at: commit prompt-46 (05f8071), 2026-06-20
- Revision: REV1 (2026-06-20) — initial draft per 2026-06-20 audit section 7 Plan 47 scope.
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 review findings 1-2 (missing mypy pre-edit baseline in Step 0; C7 hardcoded "33→~31" contradicts the cascading-effect description and Step 4.1's open-ended count).
- Revision: REV3 (2026-06-20) — incorporates Claude round-2 review findings 1-2 (3-file vs 4-file mypy baseline asymmetry — added Step 0.16 for `gateways/telegram/gateway.py`; Step 0.3 STOP predicate "top contributors" replaced with shell-verifiable "each file has ≥1 E402 error").

## Why this matters

The 2026-06-20 audit found 33 E402 (import-not-at-top) errors. Most are harmless (local imports inside functions, which Python runs fine but ruff flags for style). However, two files (`web/server.py` and `web/middleware/auth_middleware.py`) have a real anti-pattern: `logging.getLogger()` is called BEFORE the imports, forcing every subsequent import to be flagged E402. This is not a crash bug, but it's a code-smell that suggests the logging setup was bolted on without refactoring. More importantly, `gateways/__init__.py` is MISSING — this causes mypy "found twice under different module names" errors and makes the `gateways/` package invisible to some tooling. Finally, the audit flagged 4 specific unused imports (`JSONResponse` in `web/server.py`, `AuthenticationError` in `auth_middleware.py`, `asyncio` in `gateways/telegram/gateway.py` and `adapters/gemini.py`) that should be removed as part of the same cleanup pass. None of these are runtime bugs, but they block CI from passing and create noise that hides real issues. Plan 47 is the smallest of the audit-cleanup plans — 4 files modified, 1 file added — and clears the last of the E402 selector before Plan 48 (mypy) and Plan 50 (F401 bulk) run.

## Current state

**Files in scope (Plan 47 may edit only these — 4 editable + 1 new file):**
- `web/server.py` — E402: `logging.getLogger()` called before imports (audit section 4). F401: `JSONResponse` imported but unused (audit Plan 47 item 4). Plan 44 added InputSanitiser wiring here — verify it's intact.
- `web/middleware/auth_middleware.py` — E402: same `logging.getLogger()` before imports pattern (audit section 4). F401: `AuthenticationError` imported but unused (audit Plan 47 item 4).
- `gateways/telegram/gateway.py` — F401: `asyncio` imported but unused (audit Plan 47 item 4). Plan 44 added InputSanitiser wiring here — verify it's intact.
- `adapters/gemini.py` — F401: `asyncio` imported but unused (audit Plan 47 item 4). Plan 46 did NOT touch this file (the 7 adapters in Plan 46 were anthropic/cohere/deepseek/groq/mistral/openai/together).
- `gateways/__init__.py` — **NEW FILE** (audit section 6c: missing `__init__.py` causes mypy "found twice under different module names" error). Create as empty file.

**Step 0 — verify current state (do this before any edits; paste all output to CHANGELOG entry "Step 0"):**

0.1. `git rev-parse HEAD` — capture commit SHA at plan-start. Expected: `05f8071` (prompt-46) or a descendant. Paste to CHANGELOG.

0.2. `git ls-remote --tags origin | findstr prompt-46` — confirm prompt-46 tag is on origin. If absent, STOP (prior prompt's tag-push gate was skipped per landmine L5).

0.3. `ruff check . --select E402` — capture full output. Expected: 33 errors (per audit section 4). Paste full output to CHANGELOG. **Count the E402 errors by file** and paste the per-file count to CHANGELOG. **Confirm that `ruff check web/server.py --select E402` and `ruff check web/middleware/auth_middleware.py --select E402` each produce ≥1 error** (Claude round-2 review Finding 2 — replaces the vague "top contributors" predicate with a shell-verifiable test). If either file shows 0 E402 errors, the `logging.getLogger()`-before-imports anti-pattern was already fixed — STOP, the plan's Step 1 has nothing to do. If the total is not 33, also STOP — baseline has drifted; the plan's Step 1 targets may be stale.

0.4. `ruff check web/server.py web/middleware/auth_middleware.py gateways/telegram/gateway.py adapters/gemini.py --select F401` — capture full output. Expected: 4 errors (1 per file: `JSONResponse`, `AuthenticationError`, `asyncio` ×2). Paste full output to CHANGELOG. If the count is not 4, OR the unused imports don't match the audit list, STOP — baseline drift.

0.5. `Test-Path gateways/__init__.py` — confirm the file does NOT exist. Expected: `False`. If `True`, the file was added since the audit — STOP and investigate (someone may have already done part of Plan 47).

0.6. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — capture baseline test count. Must match prompt-46 baseline (1167 passed, 55 skipped, 0 failed, 0 warnings). If it does not match, STOP — baseline has drifted since prompt-46 and the plan's Gate 4 baseline is wrong.

0.7. `Select-String -Path web/server.py -Pattern "input_sanitiser"` — confirm Plan 44's InputSanitiser wiring is intact. Expected: at least 1 match. If 0 matches, STOP — Plan 44 wiring was reverted; the precondition for editing `web/server.py` is not met.

0.8. `Select-String -Path gateways/telegram/gateway.py -Pattern "input_sanitiser"` — confirm Plan 44's InputSanitiser wiring is intact here too. Expected: at least 1 match. If 0 matches, STOP.

0.9. `Get-Content web/server.py | Select-Object -First 40` — paste the first 40 lines to CHANGELOG. Confirm: `logging.getLogger(...)` appears BEFORE the `import` statements (this is the E402 anti-pattern). Note the exact line number of the `logging.getLogger()` call — Step 1.1 will move it.

0.10. `Get-Content web/middleware/auth_middleware.py | Select-Object -First 40` — paste the first 40 lines to CHANGELOG. Confirm: same `logging.getLogger()` before imports pattern. Note the exact line number.

0.11. `Select-String -Path web/server.py -Pattern "JSONResponse"` — paste output to CHANGELOG. Confirm: `JSONResponse` is imported (likely `from fastapi.responses import JSONResponse`) but never used in the file body. Note the import line number.

0.12. `Select-String -Path web/middleware/auth_middleware.py -Pattern "AuthenticationError"` — paste output to CHANGELOG. Confirm: imported but unused.

0.13. `Select-String -Path gateways/telegram/gateway.py -Pattern "asyncio"` — paste output to CHANGELOG. Confirm: `import asyncio` exists but `asyncio.` is never referenced in the file body.

0.14. `Select-String -Path adapters/gemini.py -Pattern "asyncio"` — paste output to CHANGELOG. Confirm: `import asyncio` exists but `asyncio.` is never referenced.

0.15. `mypy web/server.py web/middleware/auth_middleware.py adapters/gemini.py --ignore-missing-imports` — capture full output and paste to CHANGELOG as the **pre-existing mypy baseline** (Claude review Finding 1). This is the baseline that Gate 6 and C3 will diff against to detect NEW errors introduced by Plan 47. **Count the total errors and paste the count to CHANGELOG.** If this command produces zero errors, note that — Gate 6/C3 will then expect zero errors post-edit (any error is new). If it produces N errors, Gate 6/C3 will expect N errors post-edit (any error beyond N is new).

0.16. `mypy gateways/telegram/gateway.py --ignore-missing-imports` — capture full output and paste to CHANGELOG as the **pre-existing mypy baseline for `gateways/telegram/gateway.py`** (Claude round-2 review Finding 1). This file is NOT in Step 0.15's baseline (Step 3.1 runs `mypy gateways/` separately to cover the new `__init__.py`), but IS in Gate 6/C3's post-edit mypy run. To make the baseline symmetric with Gate 6/C3, the expected post-edit count = Step 0.15 count + Step 0.16 count. **Count the total errors and paste the count to CHANGELOG.** If zero, note it. If N errors, Gate 6/C3 will expect (Step 0.15 count + N) errors post-edit — any count beyond that is new.

If any of these do not match the description above, STOP — the plan was written against stale state.

**Repo conventions (Architecture Rules, handoff lines 437-460):**
- `web/` may import from `core/` only (Rule 6).
- `adapters/` may import from `core/` only (Rule 4).
- `gateways/` import rules: not explicitly stated in handoff, but `gateways/telegram/gateway.py` currently imports from `core/` (per Plan 44 wiring). Treat as: `gateways/` may import from `core/` only (consistent with `web/` and `adapters/`).
- All public functions have return type annotations (Rule 9).
- Exemplar for E402 fix: see any `core/` file — they all have imports at the top, no `logging.getLogger()` before imports.

## What to change

### Step 1 — Fix E402 in `web/server.py` and `web/middleware/auth_middleware.py`

1.1. **`web/server.py`**: move the `logging.getLogger(...)` call to AFTER all `import` statements. The logger initialization should be the first statement after the imports, before any code. **Verification**:
```
ruff check web/server.py --select E402
```
Expected: 0 errors (was N before — paste N from Step 0.9). Paste literal output to CHANGELOG.
```
Select-String -Path web/server.py -Pattern "input_sanitiser"
```
Expected: at least 1 match (Plan 44 wiring intact). Paste literal output to CHANGELOG. If 0 matches, STOP — Step 1.1 inadvertently reverted Plan 44 wiring; revert and re-investigate.

1.2. **`web/middleware/auth_middleware.py`**: same fix — move `logging.getLogger(...)` after all imports. **Verification**:
```
ruff check web/middleware/auth_middleware.py --select E402
```
Expected: 0 errors. Paste literal output to CHANGELOG.

### Step 2 — Remove flagged unused imports (F401)

2.1. **`web/server.py`**: remove `JSONResponse` from the `from fastapi.responses import ...` line (or remove the entire import line if `JSONResponse` was the only import from that module). If other imports from `fastapi.responses` exist, keep them. **Verification**:
```
ruff check web/server.py --select F401
```
Expected: 0 errors (was 1 before). Paste literal output to CHANGELOG.
```
Select-String -Path web/server.py -Pattern "JSONResponse"
```
Expected: 0 matches (the import is gone). Paste literal output to CHANGELOG. **IMPORTANT**: if `JSONResponse` IS used in the file body (Step 0.11 was wrong), STOP — removing the import would break the code. Re-add the import and report; the audit's F401 claim was stale.

2.2. **`web/middleware/auth_middleware.py`**: remove `AuthenticationError` from its import line. **Verification**:
```
ruff check web/middleware/auth_middleware.py --select F401
```
Expected: 0 errors (was 1 before). Paste literal output to CHANGELOG.
```
Select-String -Path web/middleware/auth_middleware.py -Pattern "AuthenticationError"
```
Expected: 0 matches. Paste literal output. If matches exist in the file body, STOP — the audit's claim was stale; re-add the import.

2.3. **`gateways/telegram/gateway.py`**: remove `import asyncio` (the audit says it's unused — verify in Step 0.13 first). **CAUTION (cross-plan hazard)**: Plan 44 added InputSanitiser wiring here. Do NOT remove any imports that the InputSanitiser wiring needs. If `asyncio` is genuinely unused (Step 0.13 confirmed `asyncio.` is never referenced), remove it. **Verification**:
```
ruff check gateways/telegram/gateway.py --select F401
```
Expected: 0 errors (was 1 before). Paste literal output to CHANGELOG.
```
Select-String -Path gateways/telegram/gateway.py -Pattern "input_sanitiser"
```
Expected: at least 1 match (Plan 44 wiring intact). Paste literal output. If 0 matches, STOP — Step 2.3 broke the wiring.
```
python -c "from gateways.telegram.gateway import TelegramGateway; print('OK')"
```
Expected: `OK`. Paste literal output.

2.4. **`adapters/gemini.py`**: remove `import asyncio` (same pattern as 2.3). **Verification**:
```
ruff check adapters/gemini.py --select F401
```
Expected: 0 errors (was 1 before). Paste literal output to CHANGELOG.
```
python -c "from adapters.gemini import GeminiAdapter; print('OK')"
```
Expected: `OK`. Paste literal output.

### Step 3 — Add `gateways/__init__.py`

3.1. Create a new empty file at `gateways/__init__.py`. The file should be completely empty (0 bytes) OR contain only a single-line docstring like `"""Telegram gateway package."""`. Either is acceptable — match the convention used by other `__init__.py` files in the repo (check `web/__init__.py` or `adapters/__init__.py` for the exemplar). **Verification**:
```
Test-Path gateways/__init__.py
```
Expected: `True`. Paste literal output to CHANGELOG.
```
python -c "import gateways; print('OK')"
```
Expected: `OK`. Paste literal output.
```
mypy gateways/ --ignore-missing-imports
```
Expected: 0 errors related to "found twice under different module names" (the audit's section 6c issue). Paste literal output. If the mypy error persists, STOP — the `__init__.py` may need additional content (e.g., re-exports).

### Step 4 — Verify no new E402/F401 errors introduced

4.1. **Verification**:
```
ruff check . --select E402
```
Expected: 33 minus the number fixed in Steps 1.1 and 1.2. Count the remaining errors and paste to CHANGELOG. The remaining E402s are local-imports-inside-functions (audit section 4 pattern 2) — these are out of scope (deferred to a future plan if needed; they're style-only and Python runs fine).

```
ruff check . --select F401
```
Expected: the F401 count should drop by 4 (the 4 unused imports removed in Step 2). Per audit section 1: F401 was 260 pre-Plan-46; Plan 46 did NOT touch F401 (it focused on F821/F811/F841). So post-Plan-46 F401 should still be 260. After Plan 47: 260 - 4 = 256. Paste the count to CHANGELOG. If the count is not 256, STOP — investigate (either Plan 46 silently removed some F401s, or new F401s were introduced).

## Verification gates (run in order, all must pass)

1. `ruff check web/server.py web/middleware/auth_middleware.py gateways/telegram/gateway.py adapters/gemini.py --select E402,F401` — expected: 0 errors. Paste literal output.
2. `Test-Path gateways/__init__.py` — expected: `True`. Paste literal output.
3. `python -c "import gateways; from gateways.telegram.gateway import TelegramGateway; from adapters.gemini import GeminiAdapter; from web.server import app; from web.middleware.auth_middleware import *; print('all imports OK')"` — expected: `all imports OK`. Paste literal output. If any import fails, STOP — a removed import was actually needed.
4. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: at-or-above prompt-46 baseline (1167 passed, 55 skipped, 0 failed, 0 warnings). If a previously-passing test now fails, STOP. If skip count rises above 55, STOP. Paste literal output.
5. `ruff check . --select E402,F401` — expected: E402 reduced by the count fixed in Step 1; F401 reduced by 4 (Step 2). Paste literal counts to CHANGELOG.
6. `mypy web/server.py web/middleware/auth_middleware.py gateways/telegram/gateway.py adapters/gemini.py --ignore-missing-imports` — expected: **error count equal to (Step 0.15 count + Step 0.16 count), plus zero new errors** (Claude round-2 review Finding 1 — Step 0.15 covers 3 files, Step 0.16 covers `gateways/telegram/gateway.py`; together they form the symmetric 4-file baseline). To verify: paste the literal output, count the total errors, and compare against (Step 0.15 count + Step 0.16 count). If the post-edit count > (Step 0.15 + Step 0.16) baseline count, STOP — new errors were introduced. If the post-edit count == baseline count, PASSED (no new errors; pre-existing errors unchanged). If the post-edit count < baseline count, that's an improvement (Plan 47 may have incidentally fixed a mypy error by removing an unused import) — note it in CHANGELOG but PASSED. Paste literal output AND the count comparison to CHANGELOG.
7. Manual smoke (any shell, no interactive requirement — landmine L11):
   ```
   python -c "from web.server import app; from gateways.telegram.gateway import TelegramGateway; print('Plan 44 wiring intact:', 'input_sanitiser' in open('web/server.py').read() and 'input_sanitiser' in open('gateways/telegram/gateway.py').read())"
   ```
   Expected: `Plan 44 wiring intact: True`. Paste literal output. If `False`, STOP — Plan 44 wiring was reverted by Plan 47.

## STOP conditions

- **S0**: If Step 0.1 reveals `HEAD` is not a descendant of `prompt-46` tag, STOP (prompt-46 was not actually merged).
- **S1**: If Step 0.2 shows `prompt-46` tag is absent from origin, STOP (landmine L5: tag-push gate was skipped).
- **S2**: If Step 0.3 reveals the E402 count is not 33, OR `ruff check web/server.py --select E402` returns 0 errors, OR `ruff check web/middleware/auth_middleware.py --select E402` returns 0 errors (Claude round-2 review Finding 2 — the `logging.getLogger()`-before-imports anti-pattern was already fixed in either file; Step 1 has nothing to do), STOP — baseline has drifted; the plan's Step 1 targets may be stale.
- **S3**: If Step 0.4 reveals the F401 count on the 4 in-scope files is not 4 (1 per file), OR the unused imports don't match the audit list (`JSONResponse`, `AuthenticationError`, `asyncio` ×2), STOP — baseline drift.
- **S4**: If Step 0.5 reveals `gateways/__init__.py` already exists, STOP — someone may have already done part of Plan 47; investigate before proceeding.
- **S5**: If Step 0.6 reveals the test baseline is NOT 1167 passed / 55 skipped / 0 failed, STOP — baseline has drifted; the plan's Gate 4 target is wrong.
- **S6**: If Step 0.7 reveals `web/server.py` has 0 matches for `input_sanitiser`, STOP — Plan 44 wiring was reverted; the precondition for editing `web/server.py` is not met.
- **S7**: If Step 0.8 reveals `gateways/telegram/gateway.py` has 0 matches for `input_sanitiser`, STOP — Plan 44 wiring was reverted here too.
- **S8**: If Step 1.1's verification `Select-String -Path web/server.py -Pattern "input_sanitiser"` returns 0 matches, STOP — Step 1.1 inadvertently reverted Plan 44 wiring. Revert Step 1.1 and re-investigate.
- **S9**: If Step 2.1's verification `Select-String -Path web/server.py -Pattern "JSONResponse"` returns matches in the file body (i.e., `JSONResponse` IS used), STOP — the audit's F401 claim was stale; re-add the import and report.
- **S10**: If Step 2.2's verification reveals `AuthenticationError` IS used in the file body, STOP — stale audit claim; re-add.
- **S11**: If Step 2.3's verification `Select-String -Path gateways/telegram/gateway.py -Pattern "input_sanitiser"` returns 0 matches, STOP — Step 2.3 broke the wiring.
- **S12**: If the fix requires >50 lines of new code in any single step, STOP — the plan was underscoped. File a follow-up plan.
- **S13**: If a file outside the in-scope list needs editing, STOP — out-of-scope. The 4 editable in-scope files + 1 new file are listed in "Current state" above.
- **S14**: If Gate 4 shows MORE failures than the prompt-46 baseline (1167 passed, 55 skipped, 0 failed) — i.e., any new failure, OR skip count rises above 55 — STOP. A regression was introduced. Do not tag.
- **S15**: If any verification gate is marked PASSED without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S16**: If any closing step (C1-C10 below) is marked DONE without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S17**: If C5 (`git show prompt-47 --stat`) reveals a file outside the in-scope list (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md`), STOP — delete the tag with `git tag -d prompt-47`, unstage the out-of-scope file, and re-tag. Do not push the bad tag.
- **S18**: If C10 (`git push origin prompt-47`) succeeds locally but `git ls-remote --tags origin | findstr prompt-47` returns empty, STOP — the tag did not reach origin (landmine L5). Retry the push. If retry fails, report to user; do not mark Plan 47 complete.

## Closing steps (mandatory, every prompt)

These run AFTER all verification gates (Gates 1-7) pass. Each step requires literal output pasted to CHANGELOG (landmine L2 / Rule 19). Do not batch.

**C1** — Run full test suite:
```
python -m pytest tests/ -v
```
Confirm: zero new failures vs prompt-46 baseline (1167 passed, 55 skipped, 0 failed). Plan 47 should not change the test count (no new tests, no removed tests). Paste `Select-Object -Last 5` literal output to CHANGELOG.

**C2** — Ruff check on all touched files:
```
ruff check web/server.py web/middleware/auth_middleware.py gateways/telegram/gateway.py adapters/gemini.py
```
Expected: 0 NEW errors in the in-scope files for E402, F401 selectors. (Pre-existing errors for other selectors — F811, F841, etc. — should have been cleared by Plan 46; if any remain, enumerate them in CHANGELOG but do not fix.) Paste literal output to CHANGELOG.

**C3** — Mypy on all touched files:
```
mypy web/server.py web/middleware/auth_middleware.py gateways/telegram/gateway.py adapters/gemini.py --ignore-missing-imports
```
Expected: **error count equal to (Step 0.15 count + Step 0.16 count), plus zero new errors** (Claude round-2 review Finding 1 — symmetric 4-file baseline). To verify: paste the literal output, count the total errors, and compare against (Step 0.15 + Step 0.16) baseline. If post-edit count > baseline, STOP — new errors introduced. If equal, PASSED. If less, note the improvement in CHANGELOG but PASSED. Paste literal output AND the count comparison to CHANGELOG. This is a re-run of Gate 6 — the count must match Gate 6's count exactly (no drift between gate and closing step).

**C4** — Commit and tag:
```
git add .
git commit -m "checkpoint: prompt-47"
git tag prompt-47
```
Verify:
```
git log -1 --oneline
git tag --list prompt-47
```
Expected: `prompt-47` appears in both outputs. Paste literal output to CHANGELOG.

**C5** — Verify file list in the tag:
```
git show prompt-47 --stat
```
Expected: file list contains ONLY these 5 files (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md` which are added in C6/C7 — they should NOT appear here because the docs commit is C9):
- `web/server.py`
- `web/middleware/auth_middleware.py`
- `gateways/telegram/gateway.py`
- `adapters/gemini.py`
- `gateways/__init__.py` (NEW FILE)

If an unexpected file appears, run `git tag -d prompt-47`, `git reset HEAD~1` (unstage the bad commit), clean, re-commit, re-tag. Do NOT push the bad tag. Paste literal output of `git show prompt-47 --stat` to CHANGELOG.

**C6** — Update `CHANGELOG.md` (append-only). **Per-step CHANGELOG entries required** — do not batch. Each entry must include:
- **Date/time**: `YYYY-MM-DD HH:MM` per handoff line 191.
- **Step reference**: "Plan 47 Step 0", "Plan 47 Step 1.1", etc.
- **What was done**: concrete actions.
- **What failed (if anything)**: mid-prompt failures and how resolved.
- **Files Modified**: per-file detail (which functions/lines changed).
- **Testing Results**: baseline → final, with the exact command run.
- **Verification Gate Output**: literal output of each gate (Gates 1-7 + Closing steps C1-C3).

Use the CHANGELOG append procedure below (PowerShell, because file locks).

**C7** — Update `SOVEREIGN_AI_HANDOFF.md`:
- Move Plan 47 from "Next 5 prompts" to "Completed prompts" table: `| 47 | E402 + missing gateways/__init__.py + flagged unused imports | 1167 | <one-line result summary> |`.
- Update "Static analysis baseline" line (handoff line 11) — change counts: **E402 33→<actual measured count from Step 4.1>** (Claude review Finding 2 — the cascading-effect of the `logging.getLogger()`-before-imports anti-pattern means Steps 1.1/1.2 may clear multiple E402 errors per file, not 1 per file; the actual reduction is whatever Step 4.1's pasted output shows, NOT a hardcoded "~31"; do NOT write a number into the handoff that wasn't measured); **F401 260→256** (4 unused imports removed: JSONResponse, AuthenticationError, asyncio ×2). Update total ruff count using the actual measured E402 reduction plus the 4 F401 reductions.
- Update test baseline line — should remain "1167 passed, 55 skipped" (no test count change in Plan 47).
- **Refill the "Next 5 prompts" queue** so it always has 5 entries. The queue after Plan 47: Plan 48 (ApprovalGate API drift + mypy remediation, P2), Plan 49 (test suite health), Plan 50 (F401 bulk cleanup), Plan 48b (F4 wiring — recommended by audit section 6b), Plan 51 (marine stack — handoff's original moat, deferred until after audit cleanup).
- Update the "Last updated" header to `2026-06-20 — post prompt-47, handoff amended by GLM session 9`.

**C8** — Update `global_rules.md` IF a new recurring mistake pattern or landmine was identified during Plan 47 execution. If no new pattern was identified, skip this step and document the skip in CHANGELOG with reason "no new recurring mistake pattern identified in prompt-47".

**C9** — Commit docs:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md global_rules.md
git commit -m "docs: prompt-47 changelog and handoff update"
```
If `global_rules.md` was not modified in C8, omit it from the `git add`. Verify with `git log -1 --oneline` and `git show HEAD --stat`. Paste literal output to CHANGELOG.

**C10** — Push to origin:
```
git push origin master
git push origin prompt-47
```
**Tag-push gate (landmine L5 — non-negotiable)**: after pushing, verify:
```
git ls-remote --tags origin | findstr prompt-47
```
Expected: a line containing `prompt-47`. If empty, retry the push. If retry fails, report to user; do NOT mark Plan 47 complete in the CHANGELOG until the tag is verified on origin. Paste literal output to CHANGELOG.

## CHANGELOG append procedure (PowerShell, because file locks)

Per handoff lines 269-273. Use these exact PowerShell idioms — do not substitute.

- **Line count**: `[System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count`. NEVER use `Get-Content | Measure-Object` — it truncates large files.
- **Append**: `Add-Content` only. NEVER paste into editor, NEVER use insert operations.
- **Before appending**: record current line count.
- **After appending**: verify new count exceeds previous, verify last 5 lines with `Select-Object -Last 5`.
- **Close the file in the IDE before running `Add-Content`** — file locks will cause silent truncation.
- **Example session for one CHANGELOG entry**:
  ```powershell
  $before = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
  Add-Content -Path r"C:\Jarvis\CHANGELOG.md" -Value @"

  ## 2026-06-20 HH:MM — Plan 47 Step 1.1

  **What was done**: Moved `logging.getLogger()` call in web/server.py from before imports to after imports. This fixes the E402 anti-pattern where every import after the getLogger call was flagged.

  **Files Modified**:
  - web/server.py: moved `logger = logging.getLogger(...)` from line ~5 to after the last import statement.

  **What failed**: <none / mid-prompt failures and resolution>

  **Testing Results**: ruff E402 in web/server.py: N → 0. Test suite unchanged.

  **Verification Gate Output**:
  ``<literal output of Step 1.1 verification command>``
  "@
  $after = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
  Write-Host "Before: $before, After: $after"
  Get-Content r"C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5
  ```

## Out of scope

The following are explicitly out of scope for Plan 47. Each requires its own plan. Do not bundle — bundling is scope creep (landmine L12).

- **Local-imports-inside-functions E402s** (~31 remaining after Step 1). These are style-only — Python runs fine. Ruff flags them, but they're not bugs. The audit section 4 explicitly says "These are fine (not runtime bugs) but ruff flags them." Defer to a separate style-cleanup plan if desired; do NOT bundle into Plan 47.
- **F401 bulk cleanup** (256 remaining after Step 2; audit Plan 50). Plan 47 only removes the 4 specific unused imports flagged in the audit's Plan 47 scope. The remaining F401s are out of scope.
- **F541 f-string no placeholders** (15 errors, audit section 1) — separate plan.
- **F841 cleanup beyond what Plan 46 already did** — Plan 46 fixed 21; remaining 55 are out of scope.
- **ApprovalGate API drift** (audit section 6b, 14+ callers) — Plan 48.
- **F4 wiring fix** (cognition-loop components built but unused in serve path) — Plan 48b.
- **mypy remediation beyond the 4 in-scope files** — Plan 48.
- **Marine stack** (handoff's original Plan 49) — Plan 51 (after the audit's P1/P2 cleanup).
- **Any change to InputSanitiser's public API or Plan 44/45/46's work** — verify-only. Plan 47's drift check confirms Plan 44's InputSanitiser wiring (STOPs S6/S7/S8/S11) and Plan 45's `fetch_by_type` are intact before any edits.
- **`adapters/gemini.py` beyond removing `import asyncio`** — Plan 46 did not touch gemini.py (only the 7 adapters: anthropic/cohere/deepseek/groq/mistral/openai/together). Plan 47 only removes the unused `asyncio` import. Any other gemini.py issues (mypy errors, F841, etc.) are out of scope.

**Note on Next 5 queue refill (handoff closing step 7)**: When Plan 47 completes, the "Next 5 prompts" queue must be refilled. The queue after Plan 47: Plan 48 (ApprovalGate API drift + mypy remediation, P2), Plan 49 (test suite health), Plan 50 (F401 bulk cleanup), Plan 48b (F4 wiring), Plan 51 (marine stack — promoted from deferred now that the audit's P1/P2 cleanup is nearing completion).

## For Claude review (Devin: do not execute)

1. **Step 1 logger-move correctness**: moving `logging.getLogger()` after imports is straightforward, but the logger variable (`logger = logging.getLogger(__name__)`) is referenced throughout the file body. After moving the assignment, verify the variable name (`logger`) is consistent — some files use `log` or `_logger`. The plan says "move the `logging.getLogger(...)` call" but doesn't specify the variable name. Is this clear enough, or should the plan dictate "preserve the existing variable name (e.g., `logger`)"?

2. **Step 2.1 `JSONResponse` import-line removal nuance**: the plan says "remove `JSONResponse` from the `from fastapi.responses import ...` line (or remove the entire import line if `JSONResponse` was the only import from that module)." This delegates the decision to Devin. Is this acceptable, or should the plan dictate one approach (e.g., "always remove the entire line if it's the only import; otherwise remove just the name")?

3. **Step 3 `__init__.py` content**: the plan allows either an empty file or a single-line docstring. Is this delegation acceptable, or should the plan dictate one approach (e.g., "match the convention of `web/__init__.py` — check that file first and use the same pattern")?

4. **Out-of-scope E402 deferral**: Plan 47 fixes only 2 of 33 E402 errors (the `logging.getLogger()` before-imports anti-pattern in `web/server.py` and `auth_middleware.py`). The remaining ~31 are local-imports-inside-functions, which the audit explicitly says are "fine (not runtime bugs) but ruff flags them." Should Plan 47 fix these too (making it an "M" effort instead of "S"), or is the deferral to a separate style-cleanup plan correct? The plan currently defers — is that the right call?

5. **Gate 6 mypy expectation**: the plan says "0 NEW errors introduced by this plan. Pre-existing errors must be enumerated." But `web/server.py` and `auth_middleware.py` likely have pre-existing mypy errors (the audit section 2 lists 180 mypy errors across 55 files). Should the plan dictate a specific pre-existing-error count to verify against, or is "enumerate them" sufficient? The risk: if Devin sees 5 mypy errors after Plan 47 and the audit said 4, they can't tell if the +1 is new or pre-existing without a baseline.
