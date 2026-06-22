# Plan 49b: Migrate old-API callers to request_approval(request: ApprovalRequest) signature

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise.
>
> Drift check (run first):
> `git diff --stat prompt-49..HEAD -- skills/http_client/skill.py skills/git/skill.py skills/docker/skill.py skills/spreadsheet/skill.py skills/clipboard/skill.py skills/screenshot/skill.py skills/pdf/skill.py skills/home_assistant/skill.py`
> If any in-scope file changed since prompt-49, compare Current state
> excerpts against live code; on mismatch, STOP.

## Status
- Priority: P2
- Effort: M
- Risk: MED
- Depends on: prompt-49 (ApprovalGate schema Optional fields fixed — callers can now construct ApprovalRequest without all Optional fields)
- Planned at: commit prompt-49 (55d02e2), 2026-06-20
- Revision: REV1 (2026-06-20) — initial draft.
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 review findings 1-3 (Steps 2/3/4 pre-split into a/b sub-steps of 3 call sites each to avoid S10 fire; Step 7 S10 exception documented; Step 0.3b added to capture TOTAL mypy count for Step 8.1/Gate 2 baseline).

## Why this matters

The 2026-06-20 full repo scan found 32 mypy errors: "Unexpected keyword argument 'action'/'context' for request_approval". These are 14 call sites across 8 skill files that use the OLD API signature `request_approval(action="...", context={...})` which no longer exists — the current signature is `request_approval(self, request: ApprovalRequest) -> ApprovalResponse`. These callers would crash with `TypeError` if reached at runtime. They're currently dormant (the `_approval_gate` attribute is None by default in all 8 skills, and no test exercises the approval path), but they're a landmine: any feature that wires up the approval gate would immediately hit `TypeError`. Plan 49b migrates all 14 call sites to the new API by constructing `ApprovalRequest` objects. Plan 49's schema fix (Field(default=None)) means callers don't need to provide all Optional fields — only the required ones (request_id, task_id, session_id, action_type, action_description, risk_level, reason_for_approval, expires_at).

## Current state

**Files in scope (Plan 49b may edit only these — 8 files):**
- `skills/http_client/skill.py` — 6 old-API call sites
- `skills/git/skill.py` — 6 old-API call sites
- `skills/docker/skill.py` — 6 old-API call sites
- `skills/spreadsheet/skill.py` — 4 old-API call sites (2 per method × 2 methods)
- `skills/clipboard/skill.py` — 4 old-API call sites
- `skills/screenshot/skill.py` — 2 old-API call sites
- `skills/pdf/skill.py` — 2 old-API call sites
- `skills/home_assistant/skill.py` — 2 old-API call sites

**Total**: 32 mypy errors across 14 call sites in 8 files.

**Step 0 — verify current state (paste all output to CHANGELOG entry "Step 0"):**

0.1. `git rev-parse HEAD` — capture commit SHA. Expected: prompt-49 (`55d02e2`) or descendant. Paste to CHANGELOG.

0.2. `git ls-remote --tags origin | findstr prompt-49` — confirm tag on origin. If absent, STOP (landmine L5).

0.3. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l` — capture actual count of OLD-API caller errors (L13 — don't predict). Expected: ~32. Paste actual count to CHANGELOG. If count is 0, STOP — someone already migrated the callers.

0.3b. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep -c "error:"` — capture the TOTAL mypy error count (REV2 — needed for Step 8.1 and Gate 2 baseline). Expected: ~560 (per context brief). Paste actual count to CHANGELOG. This is the baseline for verifying Step 8.1's reduction: expected post-Plan-49b count = (Step 0.3b baseline - 32).

0.4. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep "Unexpected keyword argument.*request_approval" | cut -d: -f1 | sort | uniq -c | sort -rn` — paste the per-file breakdown to CHANGELOG. Confirm the 8 files match the in-scope list above.

0.5. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — capture baseline test count. Must match prompt-49 baseline (1167 passed, 55 skipped, 0 failed, 0 warnings). If not, STOP (S4).

0.6. For each of the 8 in-scope files, run `Select-String -Path skills/<path>/skill.py -Pattern "request_approval" -Context 0,5` — paste all 8 outputs to CHANGELOG. Confirm each call site uses `request_approval(action=..., context=...)`. Note the exact line numbers and the action/context values for each call site — Step 1 will need these to construct the equivalent ApprovalRequest.

0.7. `Get-Content core/approval_gate.py | Select-Object -Skip 40 -First 35` — paste lines 41-75 to CHANGELOG. Confirm: `ApprovalRequest` requires request_id, task_id, session_id, action_type, action_description, action_parameters (default_factory=dict), risk_level, reason_for_approval, expires_at. Optional fields (from Plan 49): approved_by, approved_at, denied_reason, matched_scope_id, status, timeout_seconds.

0.8. `grep -n "class ApprovalActionType" core/approval_gate.py` and `Get-Content core/approval_gate.py | Select-Object -Skip 29 -First 12` — paste the ApprovalActionType enum values to CHANGELOG. Confirm: FILE_WRITE, FILE_DELETE, MODEL_DOWNLOAD, NETWORK_REQUEST, SHELL_COMMAND, SYSTEM_CONFIG, CLOUD_ESCALATION. Step 1 will map each old `action="..."` string to one of these enum values.

If any of these do not match, STOP — the plan was written against stale state.

**Repo conventions:**
- `skills/` may import from `core/` only (Rule 5). All 8 in-scope files already import from `core/` — Plan 49b may need to add imports for `ApprovalRequest`, `ApprovalActionType` from `core.approval_gate`.
- All I/O operations are async (Rule 13). Plan 49b doesn't add new I/O.
- No broad `except Exception: pass` without inline comment + WARNING trace (Rule 17). Plan 49b doesn't add new except blocks.

## What to change

### Step 1 — Map each old-API call site to ApprovalRequest construction

**Before editing any file**, create a mapping table (paste to CHANGELOG) showing each of the 14 call sites and its equivalent ApprovalRequest construction. For each call site, determine:

1. **action_type**: map the old `action="..."` string to an `ApprovalActionType` enum value:
   - "git commit", "git push", etc. → `SHELL_COMMAND`
   - "docker ...", "container ..." → `SHELL_COMMAND`
   - "http request", "http get", etc. → `NETWORK_REQUEST`
   - "spreadsheet write_csv", "spreadsheet write_excel" → `FILE_WRITE`
   - "clipboard write", "clipboard read" → `FILE_WRITE` (or `SYSTEM_CONFIG` for clipboard access)
   - "screenshot capture" → `FILE_WRITE` (writes a file)
   - "pdf generate", "pdf read" → `FILE_WRITE`
   - "home_assistant call" → `NETWORK_REQUEST` (HA is network-based)

2. **action_description**: use the old `action="..."` string directly.

3. **action_parameters**: use the old `context={...}` dict directly.

4. **risk_level**: determine from context:
   - git commit/push, docker, shell commands → "medium" or "high"
   - http requests, home_assistant → "medium"
   - spreadsheet/clipboard/pdf/screenshot (file writes) → "low" or "medium"
   - If unsure, default to "medium" and note in CHANGELOG.

5. **reason_for_approval**: construct a brief reason, e.g., "Git commit requires approval per policy".

6. **Other required fields**:
   - `request_id`: `str(uuid4())`
   - `task_id`: `str(uuid4())` (or pass through if the skill has a task context)
   - `session_id`: `"default"` (or pass through if available)
   - `expires_at`: `datetime.utcnow() + timedelta(seconds=300)` (5-minute timeout, matching the old behavior)

1.1. **Verification (mapping table)**:
Paste the completed mapping table to CHANGELOG. It should have 14 rows (one per call site) with columns: file, line number, old action string, mapped action_type, risk_level, reason_for_approval. **If any call site can't be mapped** (ambiguous action_type, unclear risk_level), STOP and report — don't guess.

### Step 2 — Migrate callers in skills/git/skill.py (6 call sites, split into 2 sub-steps per S10)

**REV2**: this step is pre-split into 2a (call sites 1-3) and 2b (call sites 4-6) to stay under S10's 50-line per-step limit. Each sub-step is ~30 lines (3 call sites × ~10 lines each).

2.1. Add imports at the top of `skills/git/skill.py` (after existing imports):
```python
from core.approval_gate import ApprovalRequest, ApprovalActionType
from datetime import datetime, timedelta
from uuid import uuid4
```
(Only add imports that aren't already present — check first.)

2a. **Migrate call sites 1-3** (the first 3 `request_approval(action=..., context=...)` occurrences in the file). For each, replace:
```python
# Before:
approved = await self._approval_gate.request_approval(
    action="git commit",
    context={"message": message},
)

# After:
request = ApprovalRequest(
    request_id=str(uuid4()),
    task_id=str(uuid4()),
    session_id="default",
    action_type=ApprovalActionType.SHELL_COMMAND,
    action_description="git commit",
    action_parameters={"message": message},
    risk_level="medium",
    reason_for_approval="Git commit requires approval per policy",
    expires_at=datetime.utcnow() + timedelta(seconds=300),
)
response = await self._approval_gate.request_approval(request)
approved = response.approved
```

**Verification (2a)**:
```
mypy skills/git/skill.py --ignore-missing-imports 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l
```
Expected: 3 (was 6 — 3 remaining for sub-step 2b). Paste literal output to CHANGELOG.

2b. **Migrate call sites 4-6** (the remaining 3 occurrences). Same pattern as 2a.

**Verification (2b — final for git/skill.py)**:
```
mypy skills/git/skill.py --ignore-missing-imports 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l
```
Expected: 0 (was 6). Paste literal output to CHANGELOG.
```
ruff check skills/git/skill.py
```
Expected: 0 errors. Paste literal output.
```
python -m pytest tests/skills/test_git_skill.py -v
```
Expected: all tests pass (or skip gracefully if no test coverage — note in CHANGELOG). Paste `Select-Object -Last 5`.

### Step 3 — Migrate callers in skills/http_client/skill.py (6 call sites, split into 2 sub-steps per S10)

**REV2**: pre-split into 3a (call sites 1-3) and 3b (call sites 4-6), same pattern as Step 2. Use `ApprovalActionType.NETWORK_REQUEST` for all 6 call sites.

3.1. Add imports (same as Step 2.1, if not already present).

3a. **Migrate call sites 1-3**. Same construction pattern as Step 2a, but with `action_type=ApprovalActionType.NETWORK_REQUEST` and appropriate `action_description`/`action_parameters`/`reason_for_approval` from the Step 1 mapping table.

**Verification (3a)**: `mypy skills/http_client/skill.py --ignore-missing-imports 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l` — expected: 3 (was 6). Paste literal output.

3b. **Migrate call sites 4-6**. Same pattern.

**Verification (3b — final for http_client/skill.py)**: `mypy skills/http_client/skill.py --ignore-missing-imports 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l` — expected: 0 (was 6). Paste literal output. `ruff check skills/http_client/skill.py` — expected: 0 errors. `python -m pytest tests/skills/test_http_client_skill.py -v` — expected: all pass. Paste outputs.

### Step 4 — Migrate callers in skills/docker/skill.py (6 call sites, split into 2 sub-steps per S10)

**REV2**: pre-split into 4a (call sites 1-3) and 4b (call sites 4-6), same pattern as Step 2. Use `ApprovalActionType.SHELL_COMMAND` for docker commands.

4.1. Add imports.

4a. **Migrate call sites 1-3**. Same construction pattern as Step 2a, with `action_type=ApprovalActionType.SHELL_COMMAND`.

**Verification (4a)**: `mypy skills/docker/skill.py --ignore-missing-imports 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l` — expected: 3 (was 6). Paste literal output.

4b. **Migrate call sites 4-6**. Same pattern.

**Verification (4b — final for docker/skill.py)**: `mypy skills/docker/skill.py --ignore-missing-imports 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l` — expected: 0 (was 6). Paste literal output. `ruff check skills/docker/skill.py` — expected: 0 errors. `python -m pytest tests/skills/test_docker_skill.py -v` — expected: all pass. Paste outputs.

### Step 5 — Migrate callers in skills/spreadsheet/skill.py (4 call sites)

Same pattern. Use `ApprovalActionType.FILE_WRITE` for spreadsheet writes.

5.1. Add imports.

5.2. Replace each of the 4 call sites.

5.3. **Verification** (targeting `skills/spreadsheet/skill.py` and `tests/skills/test_spreadsheet_skill.py`).

### Step 6 — Migrate callers in skills/clipboard/skill.py (4 call sites)

Same pattern. Use `ApprovalActionType.FILE_WRITE` (or `SYSTEM_CONFIG` if clipboard access is considered system-level — note choice in CHANGELOG).

6.1. Add imports.

6.2. Replace each of the 4 call sites.

6.3. **Verification** (targeting `skills/clipboard/skill.py` and `tests/skills/test_clipboard_skill.py`).

### Step 7 — Migrate callers in skills/screenshot/skill.py, skills/pdf/skill.py, skills/home_assistant/skill.py (2 call sites each, 6 total)

7.1. For each of the 3 files: add imports, replace 2 call sites each.

7.2. **Verification** (run for all 3 files together):
```
mypy skills/screenshot/skill.py skills/pdf/skill.py skills/home_assistant/skill.py --ignore-missing-imports 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l
```
Expected: 0 (was 6). Paste literal output.
```
ruff check skills/screenshot/skill.py skills/pdf/skill.py skills/home_assistant/skill.py
```
Expected: 0 errors. Paste literal output.

### Step 8 — Verify total mypy error reduction

8.1. **Verification**:
```
mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l
```
Expected: 0 (was 32 per Step 0.3). Paste literal output AND the count comparison to CHANGELOG.

```
mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep -c "error:"
```
Expected: (Step 0.3b baseline - 32). **REV2**: uses Step 0.3b's TOTAL mypy count as the baseline (not Step 0.3's old-API-only count). Paste literal output AND the count comparison. **If the reduction is less than 32**, STOP — investigate (some call sites may have additional errors beyond the old-API issue, or the migration introduced new errors).

```
python -m pytest tests/ -q --tb=no | Select-Object -Last 3
```
Expected: 1167 passed, 55 skipped, 0 failed, 0 warnings (unchanged from baseline). Paste literal output. If any test fails, STOP — the migration may have broken a test that mocked the old API. Fix the test mock (don't skip — landmine L3).

## Verification gates (run in order, all must pass)

1. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep "Unexpected keyword argument.*request_approval" | wc -l` — expected: 0 (was 32). Paste literal output.
2. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep -c "error:"` — expected: (Step 0.3b baseline - 32). **REV2**: uses Step 0.3b's TOTAL mypy count as baseline. Paste literal output + count comparison.
3. `ruff check skills/http_client/skill.py skills/git/skill.py skills/docker/skill.py skills/spreadsheet/skill.py skills/clipboard/skill.py skills/screenshot/skill.py skills/pdf/skill.py skills/home_assistant/skill.py` — expected: 0 errors. Paste literal output.
4. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: 1167 passed, 55 skipped, 0 failed, 0 warnings. Paste literal output.
5. Manual smoke (any shell — landmine L11):
   ```python
   python -c "
   from skills.git.skill import GitSkill
   from skills.http_client.skill import HttpClientSkill
   from skills.docker.skill import DockerSkill
   print('all 8 skills import OK')
   "
   ```
   Expected: `all 8 skills import OK`. Paste literal output. If any import fails (missing ApprovalRequest import, etc.), STOP.

## STOP conditions

- **S0**: If Step 0.1 reveals HEAD is not a descendant of prompt-49, STOP.
- **S1**: If Step 0.2 shows prompt-49 tag absent from origin, STOP (landmine L5).
- **S2**: If Step 0.3 reveals 0 old-API caller errors (someone already migrated them), STOP — plan has nothing to do.
- **S3**: If Step 0.5 reveals test baseline is NOT 1167/55/0, STOP — baseline drift.
- **S4**: If Step 1.1's mapping table has any unmappable call site, STOP — don't guess on action_type or risk_level.
- **S5**: If any per-step verification (Steps 2.3-7.3) reveals a test failure due to the migration, fix the test mock (don't skip — landmine L3). If fixing requires >50 lines per test, STOP (S10).
- **S6**: If Step 8.1's mypy reduction is less than 32, STOP — investigate (some call sites may have additional errors, or migration introduced new errors).
- **S7**: If a file outside the in-scope list needs editing, STOP — out-of-scope. The 8 in-scope files are listed in "Current state" above.
- **S8**: If Gate 4 shows MORE failures than the prompt-49 baseline (1167/55/0), STOP. Do not tag.
- **S9**: If any verification gate is marked PASSED without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S10**: If any single step requires >50 lines of new code, STOP — underscoped. File a follow-up plan. **REV2 exceptions**: (a) Steps 2/3/4 are pre-split into a/b sub-steps of 3 call sites each (~30 lines per sub-step) — S10 does not fire on these sub-steps. (b) Step 7 covers 3 files × 2 call sites each (6 total, ~60 lines) — S10 does not fire on Step 7 because the call sites are independently verifiable per file (each file can be partially committed and tested). The per-step limit applies to non-trivial code in a single file, not to repeated construction patterns distributed across files. If a single-file step exceeds 50 lines (e.g., Step 5 or 6 if they had more call sites), split it.
- **S11**: If any closing step (C1-C11 below) is marked DONE without literal output, STOP (landmine L2 / Rule 19).
- **S12**: If C5 reveals a file outside the in-scope list, STOP — delete tag, unstage, re-tag.
- **S13**: If C11 tag-push fails verification, STOP — retry; if retry fails, report.

## Closing steps (mandatory, every prompt)

**Use the temp-file CHANGELOG pattern (L15) for ALL entries >20 lines.**

**C1** — Run full test suite: `python -m pytest tests/ -v`. Confirm zero new failures. Paste `Select-Object -Last 5`.

**C2** — Ruff on all 8 in-scope files: `ruff check skills/http_client/skill.py skills/git/skill.py skills/docker/skill.py skills/spreadsheet/skill.py skills/clipboard/skill.py skills/screenshot/skill.py skills/pdf/skill.py skills/home_assistant/skill.py`. Expected: 0 errors. Paste literal output.

**C3** — Mypy full scan: `mypy . --ignore-missing-imports --explicit-package-bases`. Expected: (Step 0.3 baseline - 32) errors. Paste literal output + count comparison.

**C4** — Commit and tag:
```
git add skills/http_client/skill.py skills/git/skill.py skills/docker/skill.py skills/spreadsheet/skill.py skills/clipboard/skill.py skills/screenshot/skill.py skills/pdf/skill.py skills/home_assistant/skill.py
git commit -m "checkpoint: prompt-49b"
git tag prompt-49b
```
Verify: `git log -1 --oneline` + `git tag --list prompt-49b`. Paste literal output.

**C5** — Verify file list: `git show prompt-49b --stat`. Expected: ONLY the 8 in-scope files (plus CHANGELOG + handoff in the docs commit). If unexpected file, delete tag, unstage, re-tag. Paste literal output.

**C6** — Update `CHANGELOG.md` (per-step entries, temp-file pattern for >20 lines). Each entry: date/time, step ref, what was done, files modified, testing results, gate output. Include the mapping table from Step 1.

**C7** — Update `SOVEREIGN_AI_HANDOFF.md`:
- Move Plan 49b from "Next 5 prompts" to "Completed prompts": `| 49b | Migrate old-API callers to request_approval(request: ApprovalRequest) | 1167 | 14 call sites across 8 skill files migrated. 32 mypy errors eliminated. |`
- Update "Static analysis baseline" — mypy: (Step 0.3 baseline - 32) errors remaining.
- **Refill the "Next 5 prompts" queue**: Plan 50 (MockMemoryRouter inheritance, P2), Plan 51 (adapter type fixes + del e, P2), Plan 52 (F4 wiring, P2), Plan 53 (test suite health + B108, P2), Plan 54 (F401 bulk cleanup, P3).
- Update "Last updated" header.

**C8** — Update `SOVEREIGN_AI_HANDOFF.md` IF a new landmine was identified. Candidate: "old API signatures in dormant code paths are silent TypeError landmines — any feature wiring will crash." If no new pattern, skip with documented reason. (Do NOT update `global_rules.md` — landmine L1.)

**C9** — Commit docs:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-49b changelog and handoff update"
```
Verify with `git log -1 --oneline` + `git show HEAD --stat`. Paste literal output.

**C10** — Push:
```
git push origin master
git push origin prompt-49b
```
**Tag-push gate (L5)**: verify `git ls-remote --tags origin | findstr prompt-49b` returns the tag. If empty, retry. If retry fails, report. Paste literal output.

**C11** — Verify tag on origin: paste literal output of `git ls-remote --tags origin | findstr prompt-49b`.

## CHANGELOG append procedure (PowerShell — L15 temp-file pattern)

Per handoff lines 324-350. For entries >20 lines, use temp-file pattern:
```powershell
$entry = @"
## 2026-06-20 HH:MM — Plan 49b Step N
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
The closing `"@` MUST be at column 1 (no leading whitespace).

## Out of scope

- **MockMemoryRouter/MockStateMachine inheritance** (32 errors, test-only) — Plan 50.
- **Adapter type fixes** (27 errors) — Plan 51.
- **F4 wiring** — Plan 52.
- **B108 in tests** (22 findings) — Plan 53.
- **F401 bulk cleanup** — Plan 54.
- **Marine stack** — Plan 55.
- **Dependency updates** — Plan 56.
- **Dead code cleanup** — Plan 57.
- **Any change to `request_approval()` method signature** — the current signature is correct; only callers are wrong.
- **Any change to `core/approval_gate.py`** — Plan 49 fixed the schema; Plan 49b only touches caller files in `skills/`.
- **Adding new tests for the approval path** — the 8 skills have no existing approval-path tests. Adding them is out of scope (would be Plan 53's test suite health work). Plan 49b only ensures the migration doesn't break existing tests.

## For Claude review (Devin: do not execute)

1. **action_type mapping**: the plan maps "git commit" → SHELL_COMMAND, "http request" → NETWORK_REQUEST, "spreadsheet write" → FILE_WRITE, etc. Are these mappings correct, or should some be different (e.g., "clipboard write" → SYSTEM_CONFIG instead of FILE_WRITE)?

2. **risk_level defaults**: the plan says "if unsure, default to 'medium'". Is this the right default, or should it be "high" (more conservative) for shell commands and "low" for file writes?

3. **task_id and session_id**: the plan uses `str(uuid4())` for task_id and `"default"` for session_id. The old API didn't require these. Is this acceptable, or should Plan 49b pass through the skill's actual task/session context if available?

4. **S10 50-line limit**: each call site migration is ~10 lines. Files with 6 call sites (git, http_client, docker) = ~60 lines, which exceeds S10. The plan says "split into 2 sub-steps of 3 call sites each". Is this the right approach, or should S10's threshold be raised for mechanical migration patterns?

5. **Test coverage gap**: the 8 skills have no existing approval-path tests. Plan 49b migrates the code but doesn't add tests. Should Plan 49b add at least 1 smoke test per skill (construct ApprovalRequest, mock the gate, verify no TypeError), or is this Plan 53's job?
