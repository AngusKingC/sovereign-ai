# Plan 49: Fix ApprovalGate schema Optional fields + TraceEvent kwargs (eliminates ~108 mypy errors)

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise.
>
> Drift check (run first):
> `git diff --stat prompt-48.1..HEAD -- core/approval_gate.py`
> If `core/approval_gate.py` changed since prompt-48.1, compare Current
> state excerpts against live code; on mismatch, STOP.

## Status
- Priority: P1
- Effort: S
- Risk: LOW
- Depends on: prompt-48.1 (CHANGELOG append procedure fix complete)
- Planned at: commit prompt-48.1, 2026-06-20
- Revision: REV1 (2026-06-20) — initial draft.
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 review findings 1-2 (C8 global_rules.md → SOVEREIGN_AI_HANDOFF.md L16 landmine; Steps 1-3 line-number drift note added).

## Why this matters

The 2026-06-20 full repo scan found 224 mypy errors related to ApprovalGate. Investigation revealed these break into 4 categories:

1. **~101 errors: Optional fields not recognized by mypy** — `ApprovalRequest` (4 fields), `ApprovalResponse` (2 fields), `ApprovalScope` (4 fields) all use `Field(None, description=...)` instead of `Field(default=None, description=...)`. The pydantic mypy plugin doesn't recognize the positional `None` as a default, so it flags these fields as required. 21 callers across `skills/` get 4 "Missing named argument" errors each = 84 errors. Plus `ApprovalScope` (13 errors) and `ApprovalResponse` (4 errors). **Fix: 10 one-line edits** (change `Field(None,` to `Field(default=None,`).

2. **3 errors: TraceEvent kwargs drift in approval_gate.py** — `core/approval_gate.py:226` uses `layer=`, `payload=`, `success=` but `TraceEvent` has `level=`, `data=`, no `success` field. **Fix: 1 block edit** (~5 lines).

3. **~4 errors: ApprovalResponse construction missing fields** — `core/approval_gate.py:280,439,553` construct `ApprovalResponse` without `scope_id` and `decision_reason`. **Fix: add `default=None` to the schema fields (already in category 1)** — once the schema fields are properly Optional, these construction sites don't need changes.

4. **~30 errors: Old-API callers** — 14 callers in `skills/` use `request_approval(action=, context=)` but the current signature is `request_approval(self, request: ApprovalRequest)`. These callers would crash with `TypeError` if reached. **Deferred to Plan 49b** (separate plan — ~140 lines across 14 files, exceeds S6 50-line per-step limit).

5. **~32 errors: MockMemoryRouter/MockStateMachine inheritance** — test-only. **Deferred to Plan 50**.

Plan 49 fixes categories 1-3 (~108 mypy errors) with ~15 lines of code change in a single file (`core/approval_gate.py`). Categories 4-5 are deferred to Plan 49b and Plan 50 respectively.

## Current state

**Files in scope (Plan 49 may edit only these — 1 file):**
- `core/approval_gate.py` — contains `ApprovalRequest` (line 41), `ApprovalResponse` (line 73), `ApprovalScope` (line 92), and the `TraceEvent` usage at line 226. All 3 schema classes have `Field(None, ...)` instead of `Field(default=None, ...)` on their Optional fields. The TraceEvent call at line 226 uses deprecated kwargs.

**Step 0 — verify current state (paste all output to CHANGELOG entry "Step 0"):**

0.1. `git rev-parse HEAD` — capture commit SHA. Expected: prompt-48.1 or descendant. Paste to CHANGELOG.

0.2. `git ls-remote --tags origin | findstr prompt-48.1` — confirm tag on origin. If absent, STOP (landmine L5).

0.3. `mypy core/approval_gate.py --ignore-missing-imports` — capture full output. **Count the total errors and paste to CHANGELOG** (L13 — capture actual count, don't predict). Expected: ~119 errors (7 in approval_gate.py itself + ~112 from callers that mypy checks transitively). The actual count is the baseline for Gate 4.

0.4. `mypy core/approval_gate.py --ignore-missing-imports 2>&1 | grep "error:" | sed -E 's/.*error: //' | sed -E 's/ \[.*\]//' | sort | uniq -c | sort -rn | head -15` — paste the per-category breakdown to CHANGELOG. Confirm the top categories are: "Missing named argument" for ApprovalRequest/ApprovalScope/ApprovalResponse fields, and "Unexpected keyword argument" for TraceEvent.

0.5. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — capture baseline test count. Must match prompt-48.1 baseline (1167 passed, 55 skipped, 0 failed, 0 warnings). If not, STOP (S4).

0.6. `Get-Content core/approval_gate.py | Select-Object -Skip 40 -First 80` — paste lines 41-120 to CHANGELOG. Confirm:
  - `ApprovalRequest` (line 41) has 4 Optional fields with `Field(None, ...)` at lines 65-70: `approved_by`, `approved_at`, `denied_reason`, `matched_scope_id`.
  - `ApprovalResponse` (line 73) has 2 Optional fields with `Field(None, ...)` at lines 82, 89: `decision_reason`, `scope_id`.
  - `ApprovalScope` (line 92) has 4 Optional fields with `Field(None, ...)` at lines 104-105, 114-115: `size_limit_mb`, `time_limit_seconds`, `revoked_at`, `revoked_by`.

0.7. `Get-Content core/approval_gate.py | Select-Object -Skip 220 -First 15` — paste lines 221-235 to CHANGELOG. Confirm: line 226 has `TraceEvent(...)` with `layer=`, `payload=`, `success=` kwargs.

If any of these do not match, STOP — the plan was written against stale state.

**Repo conventions:**
- `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, or `system/` (Rule 1). Plan 49 only edits `core/approval_gate.py` — no new imports needed.
- All public functions have return type annotations (Rule 9).
- No broad `except Exception: pass` without inline comment + WARNING trace (Rule 17). Plan 49 doesn't add new except blocks.

## What to change

### Step 1 — Fix ApprovalRequest Optional fields (4 edits)

**Note (REV2)**: Line numbers below are approximate — confirm against Step 0.6's pasted output before editing. Use the field name (`approved_by`, `approved_at`, etc.) as the primary locator, not the line number. Lines 68-69 between the listed fields are non-Optional fields (status, etc.) and should not be edited.

In `core/approval_gate.py`, change 4 fields in `ApprovalRequest` (approximately lines 65-70) from `Field(None, ...)` to `Field(default=None, ...)`:

1.1. Line 65: `approved_by: Optional[str] = Field(None, description=...)` → `approved_by: Optional[str] = Field(default=None, description=...)`

1.2. Line 66: `approved_at: Optional[datetime] = Field(None, description=...)` → `approved_at: Optional[datetime] = Field(default=None, description=...)`

1.3. Line 67: `denied_reason: Optional[str] = Field(None, description=...)` → `denied_reason: Optional[str] = Field(default=None, description=...)`

1.4. Line 70: `matched_scope_id: Optional[str] = Field(None, description=...)` → `matched_scope_id: Optional[str] = Field(default=None, description=...)`

**Verification**:
```
mypy core/approval_gate.py --ignore-missing-imports 2>&1 | grep "Missing named argument.*ApprovalRequest" | wc -l
```
Expected: 0 (was 84 — 21 callers × 4 fields). Paste literal output to CHANGELOG.

### Step 2 — Fix ApprovalResponse Optional fields (2 edits)

**Note (REV2)**: Line numbers below are approximate — confirm against Step 0.6's pasted output before editing. Use the field name (`decision_reason`, `scope_id`) as the primary locator.

In `core/approval_gate.py`, change 2 fields in `ApprovalResponse` (approximately lines 82, 89):

2.1. Line 82: `decision_reason: Optional[str] = Field(None, description=...)` → `decision_reason: Optional[str] = Field(default=None, description=...)`

2.2. Line 89: `scope_id: Optional[str] = Field(None, description=...)` → `scope_id: Optional[str] = Field(default=None, description=...)`

**Verification**:
```
mypy core/approval_gate.py --ignore-missing-imports 2>&1 | grep "Missing named argument.*ApprovalResponse" | wc -l
```
Expected: 0 (was ~4). Paste literal output to CHANGELOG.

### Step 3 — Fix ApprovalScope Optional fields (4 edits)

**Note (REV2)**: Line numbers below are approximate — confirm against Step 0.6's pasted output before editing. Use the field name (`size_limit_mb`, `time_limit_seconds`, `revoked_at`, `revoked_by`) as the primary locator.

In `core/approval_gate.py`, change 4 fields in `ApprovalScope` (approximately lines 104-105, 114-115):

3.1. Line 104: `size_limit_mb: Optional[int] = Field(None, ge=0, description=...)` → `size_limit_mb: Optional[int] = Field(default=None, ge=0, description=...)`

3.2. Line 105: `time_limit_seconds: Optional[int] = Field(None, ge=0, description=...)` → `time_limit_seconds: Optional[int] = Field(default=None, ge=0, description=...)`

3.3. Line 114: `revoked_at: Optional[datetime] = Field(None, description=...)` → `revoked_at: Optional[datetime] = Field(default=None, description=...)`

3.4. Line 115: `revoked_by: Optional[str] = Field(None, description=...)` → `revoked_by: Optional[str] = Field(default=None, description=...)`

**Verification**:
```
mypy core/approval_gate.py --ignore-missing-imports 2>&1 | grep "Missing named argument.*ApprovalScope" | wc -l
```
Expected: 0 (was ~13). Paste literal output to CHANGELOG.

### Step 4 — Fix TraceEvent kwargs at line 226

In `core/approval_gate.py`, fix the `TraceEvent(...)` call at line 226. The current code uses deprecated kwargs:

```python
# Before (line 226):
await self.emitter.emit(TraceEvent(
    event_id=uuid4(),
    timestamp=datetime.utcnow(),
    layer="L1",
    component=TraceComponent.ORCHESTRATOR,
    ...
    payload={...},
    success=True,
))
```

Change to match `TraceEvent`'s actual schema:
- `layer="L1"` → `level=TraceLevel.INFO` (or `TraceLevel.WARNING` if this is an error path — check context)
- `payload={...}` → `data={...}`
- `success=True` → remove (no equivalent field; if needed, add to `data={"success": True}` or `tags={"success": "true"}`)

**CAUTION**: read the surrounding context (lines 220-235) to determine the correct `TraceLevel`. If this is in an `except Exception` block (error path), use `TraceLevel.WARNING`. If it's a success path, use `TraceLevel.INFO`. The `success=True` kwarg suggests this was originally a success notification, but it's inside a try/except — verify before choosing.

4.1. Read lines 220-235, determine the correct `TraceLevel`, make the edit.

4.2. **Verification**:
```
mypy core/approval_gate.py --ignore-missing-imports 2>&1 | grep "TraceEvent.*Unexpected keyword"
```
Expected: 0 (was 3 — `layer`, `payload`, `success`). Paste literal output to CHANGELOG.
```
ruff check core/approval_gate.py
```
Expected: 0 errors. Paste literal output.
```
python -m pytest tests/test_approval_gate.py -v
```
Expected: all tests pass. Paste `Select-Object -Last 5` to CHANGELOG. If a test fails, STOP — the TraceEvent fix may have broken a test that mocked the old kwargs. Fix the test mock (don't skip — landmine L3).

### Step 5 — Verify total mypy error reduction

5.1. **Verification**:
```
mypy core/approval_gate.py --ignore-missing-imports
```
Expected: (Step 0.3 baseline count) minus ~108. The remaining errors should be:
- ~30 "Unexpected keyword argument" for `request_approval(action=, context=)` — old-API callers, deferred to Plan 49b
- ~32 "MockMemoryRouter"/"MockStateMachine" — test-only, deferred to Plan 50
- Any other pre-existing errors not related to ApprovalGate schema

Paste literal output AND the count comparison to CHANGELOG. **If the reduction is less than 100**, STOP — investigate (some `Field(None, ...)` instances may have been missed, or the mypy pydantic plugin doesn't recognize `default=None` either).

5.2. **Full test suite**:
```
python -m pytest tests/ -q --tb=no | Select-Object -Last 3
```
Expected: 1167 passed, 55 skipped, 0 failed, 0 warnings (unchanged from baseline). Paste literal output. If any test fails, STOP.

## Verification gates (run in order, all must pass)

1. `mypy core/approval_gate.py --ignore-missing-imports 2>&1 | grep "Missing named argument" | wc -l` — expected: 0 (was ~101). Paste literal output.
2. `mypy core/approval_gate.py --ignore-missing-imports 2>&1 | grep "TraceEvent.*Unexpected keyword" | wc -l` — expected: 0 (was 3). Paste literal output.
3. `mypy core/approval_gate.py --ignore-missing-imports 2>&1 | grep -c "error:"` — expected: (Step 0.3 baseline - ~108). Paste literal output AND the count comparison.
4. `ruff check core/approval_gate.py` — expected: 0 errors. Paste literal output.
5. `python -m pytest tests/test_approval_gate.py -v` — expected: all tests pass. Paste `Select-Object -Last 5`.
6. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: 1167 passed, 55 skipped, 0 failed, 0 warnings. Paste literal output.
7. Manual smoke:
   ```python
   python -c "from core.approval_gate import ApprovalRequest, ApprovalResponse, ApprovalScope; r = ApprovalRequest(request_id='test', task_id='t', session_id='s', action_type='file_write', action_description='test', risk_level='low', reason_for_approval='test', expires_at='2026-12-31T23:59:59'); print('ApprovalRequest OK:', r.approved_by is None)"
   ```
   Expected: `ApprovalRequest OK: True`. Paste literal output.

## STOP conditions

- **S0**: If Step 0.1 reveals HEAD is not a descendant of prompt-48.1, STOP.
- **S1**: If Step 0.2 shows prompt-48.1 tag absent from origin, STOP (landmine L5).
- **S2**: If Step 0.3 fails to capture mypy baseline (mypy can't run), STOP. If the count differs from ~119, that's OK — use the actual count as baseline (L13).
- **S3**: If Step 0.6 reveals the `Field(None, ...)` pattern is NOT present (someone already fixed it), STOP — plan has nothing to do.
- **S4**: If Step 0.5 reveals test baseline is NOT 1167/55/0, STOP — baseline drift.
- **S5**: If Step 4.2 reveals a test fails due to the TraceEvent fix, fix the test mock (don't skip — landmine L3). If fixing requires >50 lines, STOP (S10).
- **S6**: If Step 5.1's mypy reduction is less than 100, STOP — investigate (some Field instances may have been missed, or `default=None` doesn't work with this pydantic/mypy version).
- **S7**: If a file outside the in-scope list needs editing, STOP — out-of-scope. The 1 in-scope file is `core/approval_gate.py`.
- **S8**: If Gate 6 shows MORE failures than the prompt-48.1 baseline (1167/55/0), STOP. Do not tag.
- **S9**: If any verification gate is marked PASSED without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S10**: If the fix requires >50 lines of new code in any single step, STOP — underscoped. File a follow-up plan.
- **S11**: If any closing step (C1-C11 below) is marked DONE without literal output, STOP (landmine L2 / Rule 19).
- **S12**: If C5 reveals a file outside the in-scope list, STOP — delete tag, unstage, re-tag.
- **S13**: If C11 tag-push fails verification, STOP — retry; if retry fails, report.

## Closing steps (mandatory, every prompt)

**Use the temp-file CHANGELOG pattern (L15) for ALL entries >20 lines.**

**C1** — Run full test suite: `python -m pytest tests/ -v`. Confirm zero new failures. Paste `Select-Object -Last 5`.

**C2** — Ruff: `ruff check core/approval_gate.py`. Expected: 0 errors. Paste literal output.

**C3** — Mypy: `mypy core/approval_gate.py --ignore-missing-imports`. Expected: (Step 0.3 baseline - ~108). Paste literal output + count comparison.

**C4** — Commit and tag:
```
git add core/approval_gate.py
git commit -m "checkpoint: prompt-49"
git tag prompt-49
```
Verify: `git log -1 --oneline` + `git tag --list prompt-49`. Paste literal output.

**C5** — Verify file list: `git show prompt-49 --stat`. Expected: ONLY `core/approval_gate.py` (plus CHANGELOG + handoff in the docs commit). If unexpected file, delete tag, unstage, re-tag. Paste literal output.

**C6** — Update `CHANGELOG.md` (per-step entries, temp-file pattern for >20 lines). Each entry: date/time, step ref, what was done, files modified, testing results, gate output.

**C7** — Update `SOVEREIGN_AI_HANDOFF.md`:
- Move Plan 49 from "Next 5 prompts" to "Completed prompts": `| 49 | ApprovalGate schema Optional fields + TraceEvent kwargs | 1167 | Fixed 10 Field(None→default=None) + 3 TraceEvent kwargs. ~108 mypy errors eliminated. |`
- Update "Static analysis baseline" — mypy: (Step 0.3 baseline - ~108) errors remaining.
- **Refill the "Next 5 prompts" queue**: Plan 49b (old-API caller migration, P2), Plan 50 (MockMemoryRouter inheritance, P2), Plan 51 (adapter type fixes + del e, P2), Plan 52 (F4 wiring, P2), Plan 53 (test suite health + B108, P2).
- Update "Last updated" header.

**C8** — Update `SOVEREIGN_AI_HANDOFF.md` (NOT `global_rules.md` — landmine L1) — add a new landmine entry after L15 in the known landmines list:
  ```
  - **Pydantic v2 + mypy plugin does not recognize `Field(None, ...)` as Optional (L16, prompt-49)**: pydantic v2's mypy plugin requires `default=None` as a keyword argument (not positional `None`) to infer the field as Optional in type-checking mode. `Field(None, description=...)` produces "Missing named argument" errors at every caller site. Fix: use `Field(default=None, description=...)` for all Optional fields. This is a schema-level fix — no caller changes needed.
  ```
  **Verification**: `Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "L16"` → expected: ≥1 match. Paste literal output to CHANGELOG.
  
  (This replaces the REV1 instruction to update `global_rules.md`, which is Devin-local and unreachable per landmine L1. The pydantic `Field(default=None)` pattern belongs in the handoff's known landmines, not in a Devin-local file.)

**C9** — Commit docs:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-49 changelog and handoff update"
```
Verify with `git log -1 --oneline` + `git show HEAD --stat`. Paste literal output.

**C10** — Push:
```
git push origin master
git push origin prompt-49
```
**Tag-push gate (L5)**: verify `git ls-remote --tags origin | findstr prompt-49` returns the tag. If empty, retry. If retry fails, report. Paste literal output.

**C11** — Verify tag on origin: paste literal output of `git ls-remote --tags origin | findstr prompt-49`.

## CHANGELOG append procedure (PowerShell — L15 temp-file pattern)

Per handoff lines 324-350. For entries >20 lines, use temp-file pattern:
```powershell
$entry = @"
## 2026-06-20 HH:MM — Plan 49 Step N
...
"@
$entry | Out-File -FilePath C:\Jarvis\scan\changelog-entry.md -Encoding utf8
$before = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\changelog-entry.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md"
$after = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Write-Host "Before: $before, After: $after"
Get-Content "C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5
Remove-Item C:\Jarvis\scan\changelog-entry.md
```
The closing `"@` MUST be at column 1 (no leading whitespace). If the here-string hangs, write the entry to the temp file using the editor directly.

## Out of scope

- **Old-API caller migration** (14 files, ~140 lines) — `request_approval(action=, context=)` → construct ApprovalRequest. Deferred to **Plan 49b**. These callers would crash with TypeError if reached, but are currently dormant (approval_gate is None by default, no test coverage).
- **MockMemoryRouter/MockStateMachine inheritance** (32 errors, test-only) — **Plan 50**.
- **Adapter type fixes** (27 errors) — **Plan 51**.
- **F4 wiring** — **Plan 52**.
- **B108 in tests** (22 findings) — **Plan 53**.
- **F401 bulk cleanup** — **Plan 54**.
- **Marine stack** — **Plan 55**.
- **Dependency updates** — **Plan 56**.
- **Dead code cleanup** — **Plan 57**.
- **Any change to `request_approval()` method signature** — the current signature `request_approval(self, request: ApprovalRequest)` is correct; the old callers are wrong, not the method.
- **Any change to test files** — Plan 49 is production-code-only. Test fixes are Plan 50.

## For Claude review (Devin: do not execute)

1. **Is `Field(default=None, ...)` the correct fix?** The pydantic v2 mypy plugin should recognize `default=None` as making the field Optional. But if the plugin version doesn't support this, the fix won't work and Step 5.1's S6 will fire. Alternative: use `= None` without `Field()` (lose the description), or use `Optional[str] | None = None` syntax. Is `Field(default=None, ...)` the right first attempt?

2. **Step 4 TraceEvent level**: the plan says "read the surrounding context to determine the correct TraceLevel". The `success=True` kwarg suggests this was a success notification, but it's inside a try/except block. Is the delegation to Devin's judgment correct, or should the plan dictate `TraceLevel.WARNING` (since it's in an except block)?

3. **Scope split (Plan 49 vs 49b)**: Plan 49 fixes the schema (~108 errors, ~15 lines). Plan 49b fixes the old-API callers (~30 errors, ~140 lines). Is this the right split, or should Plan 49 also fix the old-API callers (making it an L-effort plan instead of S)?

4. **Dormant code paths**: the 14 old-API callers would crash with TypeError if reached. They're currently dormant (untested, approval_gate is None by default). Should Plan 49 flag these as a new F-bug in "What's broken", or is the Plan 49b deferral sufficient?

5. **ApprovalResponse `approved_by` and `approved_at` are required** (line 85-86: `Field(..., description=...)` with `...` meaning required). But `ApprovalRequest`'s same fields are Optional. Is this intentional (the response MUST record who approved), or a schema inconsistency?
