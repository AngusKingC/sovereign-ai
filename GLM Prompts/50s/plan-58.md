# Plan 58 — Remaining datetime.utcnow() Cleanup (28 test + 90 production)

**Prompt number**: 58
**Priority**: P3 (technical debt — L19 compliance)
**Estimated scope**: 118 utcnow replacements across 21 files
**Baseline test count**: 1167 passed, 55 skipped, 0 failed (post-prompt-57)
**Baseline utcnow**: 28 in tests (4 files) + 90 in production (17 core/ files) = 118 total

---

## Section 0: Rules (read first, follow always)

These rules exist because each one prevents a specific failure that has actually occurred in this project. They are not aspirational — every rule traces to a documented mistake in the CHANGELOG. Follow them exactly. When in doubt, stop and ask.

**Numbering**: L1-Ln. These rules are related to but NOT 1:1 aligned with the handoff's "Known landmines" L-numbering. When citing a rule, specify which system: "Section 0 L14" or "handoff L14".

**Self-evolution**: Rule **L20** is the meta-rule. Every plan's closing sequence MUST prompt Devin to propose new rules when it hits a recurring error pattern not covered here.

### Execution discipline

**L1. Follow the plan's verification gates in order. Run them, paste evidence, STOP on failure.**

**L2. Run the relevant test file after each file change. Run the full suite at gates, not after every edit.**

**L3. When you fix a bug, grep for the same pattern across the codebase before closing the prompt.**

**L4. Never silently substitute. If the spec says X, implement X. When in doubt, STOP and report.**

**L5. Do not expand scope when tests find pre-existing issues outside the plan.**

### Code construction

**L6. TraceEvent is defined in `core/observability.py`. Use exactly these fields: `event_type`, `component`, `level`, `message`, `data`, `duration_ms`.**

**L7. Every class that emits trace events MUST use constructor-injected emitter. Never use the global `emit_trace()` function.**

**L8. Raise domain exceptions OUTSIDE try-except blocks. Never broad-except without a trace event.**

**L9. When fixing a production file, fix its test file in the same step.**

**L10. Do not remove working implementation to make a test pass.**

**L11. Verify field and class names against the actual schema file before using them.**

**L12. Patch at the location where a class is defined, not where it is used.**

**L13. Never mutate Pydantic model instances after construction in tests.**

### Testing

**L14. Tests must verify behaviour, not just confirm the code runs.**

**L15. In tests, construct `MemoryTraceEmitter()` and pass it via constructor injection. Retrieve events via `emitter.get_events()`, never `emitter.events`.**

### Datetime consistency

**L19. Tests and production code MUST use the same timezone strategy. Never mix naive and aware `datetime` objects.**
Preferred project convention: `datetime.now(timezone.utc)` everywhere (aware, no deprecation in Python 3.12+). Never use `datetime.utcnow()` in new code. When fixing one side, fix the other side in the same step (L9 applies).

### CHANGELOG and documentation

**L16. The CHANGELOG must match the commit. Verify before reporting completion.**

**L17. CHANGELOG format is simplified — ~10 lines per plan. Title, changed files, result, test count math. Record only non-trivial decisions.**

### Git and closing sequence

**L18. The correct closing sequence for every prompt:**
1. Run full test suite. Confirm zero new failures.
2. `ruff check <files_touched>` — zero errors.
3. `mypy <files_touched> --ignore-missing-imports` — zero errors. **Never `mypy .`** — file-scoped only.
4. `git add <in-scope files only> && git commit -m "checkpoint: prompt-{N}"`
5. `git tag prompt-{N}`
6. **Tag verification:** `git show prompt-{N} --stat` — verify file list.
7. Update `CHANGELOG.md` (temp-file pattern, append to END).
8. Update `SOVEREIGN_AI_HANDOFF.md`.
9. **Rule proposal (L20):** scan your work for failure patterns not covered by Section 0.
10. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-{N}"`
11. `git push origin master && git push origin prompt-{N}`
12. **Post-push verification:** `git ls-remote --tags origin | Select-String "prompt-{N}"`

**L18 note**: even if no code changes (docs-only plan), you MUST still create the tag. Tag the docs commit if no code commit exists.

### Meta-rule: self-evolution

**L20. When you hit a recurring error pattern or a landmine not covered by these rules, propose a new rule to GLM in your closing report.**
Format:
```
## Rule proposal for global_rules.md
Trigger: <what happened this prompt>
Recurrence: <prompt numbers or "first occurrence">
Proposed rule: L{n+1}. <one-line statement>
Anchor: <prompt + file + line>
Why existing rules didn't catch it: <one line>
```
If no new failure patterns: `## Rule proposal — none (no new failure patterns this prompt)`. **Silence is NOT acceptable.**

### Verification gate scoping

**L23. Verification gates must check the actual scope of prior plans, not the entire codebase.**

### Sequential scan execution

**L24. Run scan tools SEQUENTIALLY, never in parallel. Each tool's output must be captured and verified before running the next.**

### Test fixture parameter removal

**L25. When removing unused parameters identified by vulture in test files, verify the parameter is not required by pytest fixture dependencies or framework protocols (e.g., middleware call_next signatures, pydantic validator cls). If removal breaks tests, defer to Category C.**

### CHANGELOG append position

**L21. CHANGELOG entries are ALWAYS appended to the END using `Add-Content -Encoding utf8`. NEVER insert at the top.**

### Environment

**L22. This project runs on Windows. Use PowerShell, not Unix commands.**

---

## Why this plan exists

Plan 53 fixed 81 `datetime.utcnow()` calls in 15 test files but deferred 28 test occurrences (outside its scope) and didn't touch production code (correctly, per L5). Plan 53 also expanded scope minimally to fix 2 production utcnow calls in `core/approval_gate.py` that were causing test failures (naive vs aware datetime comparison).

L19 (added in Plan 54's rules ship) makes naive/aware datetime mixing a rule violation. This plan completes the cleanup: 28 remaining test utcnow + 90 production utcnow = 118 total replacements. All must use `datetime.now(timezone.utc)` (aware) per L19.

**Critical per L19/L23**: test and production files that share datetime values MUST be fixed together. Plan 53's approval_gate issue showed what happens when only one side is fixed — `TypeError: can't compare offset-naive and offset-aware datetimes`.

---

## Opening steps (S0)

### S0.1 — Verify prompt-57 completed

```powershell
git ls-remote --tags origin | Select-String "prompt-57"
```

**Expected**: returns `e874f2b710f3c68e148dc370034fc8f197a7d7ed  refs/tags/prompt-57`. If empty, STOP.

### S0.2 — Pull latest master

```powershell
git pull origin master
```

### S0.3 — Verify HEAD

```powershell
git rev-parse HEAD
```

**Expected**: `06ff457f481b6c54c5598a7742aafac61821265c`. If different, STOP.

---

## Step 1 (S1) — Capture baseline

### S1.1 — Test count baseline

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
```

**Expected**: `1167 passed, 55 skipped`. Record actual count.

### S1.2 — Count utcnow occurrences (run SEQUENTIALLY per L24, use -AllMatches per Claude review)

**Note on counting**: use `Select-String -AllMatches` to count ALL occurrences, not just lines. A single line may contain multiple `datetime.utcnow()` calls (e.g., ternary expressions, inline comparisons). Without `-AllMatches`, the count would undercount and S4's "Expected: 0" verification could pass while a same-line duplicate still lurks.

**Test files:**
```powershell
Select-String "datetime\.utcnow\(\)" -Path tests/ -Recurse -Include *.py -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: 28 occurrences across 4 files.

**Production files:**
```powershell
Select-String "datetime\.utcnow\(\)" -Path core/ -Recurse -Include *.py -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: 90 occurrences across 17 files.

**List the actual files + counts** for both. This is your work list.

---

## Step 2 (S2) — Identify test-production datetime coupling

Per L19, test and production files that share datetime values MUST be fixed together. Before any edits, identify which test files pass datetimes to which production files.

### S2.1 — For each of the 4 test files, identify ALL production files they import (proactive coupling check)

Per L19, test and production files that share datetime values MUST be fixed together. The naive mapping (test_retention.py → core/retention.py) misses indirect coupling — a test file may import from multiple core/ modules.

**Proactive coupling check** (per Claude review — don't rely on reactive TypeError discovery):
```powershell
# For each test file, find ALL core/ imports to surface indirect production dependencies
Select-String "from core\.|import core\." -Path tests/test_retention.py
Select-String "from core\.|import core\." -Path tests/test_memory_compactor.py
Select-String "from core\.|import core\." -Path tests/test_event_trigger.py
Select-String "from core\.|import core\." -Path tests/test_memory_router.py
```

Record the full import list for each test file. For each imported core/ module:
1. Check if it has utcnow calls (from S1.2's production count)
2. If yes → it's a coupled file that MUST be edited in the same step as the test file
3. If no → no action needed (but note it for awareness)

**Expected mapping** (verify against actual import scan):
- test_retention.py → core/retention.py (direct) + possibly core/memory_router.py, core/task_state_machine.py (indirect)
- test_memory_compactor.py → core/memory_compactor.py (direct) + possibly core/memory_router.py (indirect)
- test_event_trigger.py → core/event_trigger.py (direct) + possibly core/orchestrator.py, core/task_state_machine.py (indirect)
- test_memory_router.py → core/memory_router.py (direct)

Any indirect coupling discovered here gets added to the S3.2 edit list — do NOT wait for TypeError to surface it.

### S2.2 — Group the 90 production utcnow by file

```powershell
Select-String "datetime\.utcnow\(\)" -Path core/ -Recurse -Include *.py | Group-Object Path | Sort-Object Count -Descending | Select-Object Count, Name
```

**Expected**: 17 files, with counts summing to 90. Record the actual breakdown.

---

## Step 3 (S3) — Replace utcnow → now(timezone.utc) in coupled pairs

Process test-production pairs together per L19. For each pair:

### S3.1 — Pattern

For each coupled pair (test file + production file):
1. Read both files
2. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` in BOTH files
3. Ensure both files import `timezone` from `datetime` (add `from datetime import timezone` if missing, or append `timezone` to existing `from datetime import ...` line)
4. Run the test file: `python -m pytest tests/test_<name>.py -v | Select-Object -Last 5`
5. If tests pass, move to next pair. If tests fail with `TypeError: can't compare offset-naive and offset-aware datetimes`, STOP — you missed a coupled file. Grep for `datetime.utcnow` in related files.

### S3.2 — Process the 4 test files + their production counterparts

For each pair, edit both files, then test:
```powershell
# Pair 1: test_retention.py + core/retention.py
python -m pytest tests/test_retention.py -v | Select-Object -Last 5

# Pair 2: test_memory_compactor.py + core/memory_compactor.py
python -m pytest tests/test_memory_compactor.py -v | Select-Object -Last 5

# Pair 3: test_event_trigger.py + core/event_trigger.py
python -m pytest tests/test_event_trigger.py -v | Select-Object -Last 5

# Pair 4: test_memory_router.py + core/memory_router.py
python -m pytest tests/test_memory_router.py -v | Select-Object -Last 5
```

### S3.3 — Process remaining 13 production files (no test counterpart has utcnow)

The other 13 production files with utcnow don't have a test file with utcnow — but they may still have datetime coupling. For each:

1. Read the production file
2. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`
3. Ensure `timezone` is imported
4. Run the corresponding test file: `python -m pytest tests/test_<name>.py -v | Select-Object -Last 5`
5. If tests fail with naive/aware comparison error, the test file ALSO has utcnow (or hardcoded naive datetimes) — fix it in the same step per L9

**The 13 remaining production files** (from S2.2):
- core/orchestrator.py
- core/escalation.py
- core/approval_gate.py (2 remaining from Plan 53 — verify)
- core/task_state_machine.py
- core/multi_worker.py
- core/voice_interface.py
- core/auth.py
- core/notification.py
- core/a2a_protocol.py
- core/schemas.py
- core/evaluator.py
- core/orchestrator_improvement.py
- core/worker_factory.py

---

## Step 4 (S4) — Verify zero utcnow remain

### S4.1 — Test files (use -AllMatches per Claude review)

```powershell
Select-String "datetime\.utcnow\(\)" -Path tests/ -Recurse -Include *.py -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: `0`.

### S4.2 — Production files (use -AllMatches)

```powershell
Select-String "datetime\.utcnow\(\)" -Path core/ -Recurse -Include *.py -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: `0`.

**STOP condition**: if any utcnow remain, find and fix them. Per L19, mixing naive/aware is a rule violation.

### S4.3 — Check for `datetime.now()` without timezone (HARD STOP if found — per Claude review)

```powershell
Select-String "datetime\.now\(\)" -Path core/ -Recurse -Include *.py | Measure-Object -Line
Select-String "datetime\.now\(\)" -Path tests/ -Recurse -Include *.py | Measure-Object -Line
```

**HARD STOP condition**: if ANY bare `datetime.now()` calls exist (count > 0), STOP — do not fix or defer unilaterally. Report the count and full file:line list to GLM. This is a scope-expansion decision GLM must make. Per L4, do not resolve by discretion.

**Rationale**: bare `datetime.now()` returns local time (naive, timezone-unaware) — same L19 violation as `datetime.utcnow()`. But it wasn't in the original handoff scope. Fixing it requires explicit authorization because:
1. It may be intentional (e.g., displaying local time to user)
2. The count could be large (expanding scope significantly)
3. Some calls may need `datetime.now(tz)` with a specific timezone, not UTC

Report format:
```
HARD STOP — bare datetime.now() found outside Plan 58 scope.
Count: <N> in core/, <M> in tests/
File list:
  core/<file>:<line>
  tests/<file>:<line>
  ...
Awaiting GLM decision: fix in this plan (scope expansion) or defer to separate plan?
```

---

## Step 5 (S5) — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Expected**: `1167 passed, 55 skipped` (unchanged — datetime fix shouldn't change test count).

**STOP condition**: if test count drops or new failures appear (especially `TypeError: can't compare offset-naive and offset-aware datetimes`), a coupled file was missed. Use the bisection fallback from Plan 57 §S5 (prompt-57 tag, commit e874f2b) if needed — the procedure is documented there.

---

## Closing steps (C1-C13) — MANDATORY

### C1 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Paste**: last 5 lines. **Expected**: `1167 passed, 55 skipped`.

### C2 — Ruff check on touched files

```powershell
ruff check <files_touched> 2>&1 | Select-Object -Last 3
```

### C3 — Ruff total

```powershell
ruff check . 2>&1 | Select-Object -Last 3
```

### C4 — File-scoped mypy on touched files

```powershell
mypy <files_touched> --ignore-missing-imports 2>&1 | Select-Object -Last 3
```

**Expected**: error count ≤ baseline (datetime fix shouldn't introduce mypy errors).

### C5 — Commit

```powershell
git add <in-scope files only>
git commit -m "refactor: replace 118 datetime.utcnow() with datetime.now(timezone.utc) (Plan 58)"
```

### C6 — Tag

```powershell
git tag prompt-58
```

### C7 — Tag verification

```powershell
git show prompt-58 --stat | Select-Object -First 30
```

**Verify**: file list contains ONLY the files edited in S3. If unexpected files appear, fix.

### C8 — Update CHANGELOG.md (temp-file pattern)

```powershell
$lines = @(
    "",
    "## 2026-06-21 HH:MM — prompt-58",
    "",
    "**Plan**: datetime.utcnow() cleanup — 118 replacements (28 test + 90 production)",
    "",
    "**Changed**:",
    "- <list of files edited, grouped by test/production pairs>",
    "",
    "**Results**:",
    "- Tests: 1167 passed, 55 skipped (unchanged)",
    "- utcnow remaining: 0 (was 118)",
    "- L19 compliance: all datetime calls now use datetime.now(timezone.utc)",
    "- Tag: prompt-58 verified on origin"
)
Set-Content -Path "C:\Jarvis\scan\logs\changelog-entry-prompt-58.md" -Value $lines -Encoding utf8
$oldCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\logs\changelog-entry-prompt-58.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
$newCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 12
```

### C9 — Rule proposal (per L20 — MANDATORY)

Your closing report MUST include either a rule proposal OR explicit "none". **Silence is NOT acceptable.**

**Suggested reflection**: did any test-production pair have hidden coupling that caused naive/aware comparison errors? Did you find `datetime.now()` (without timezone) in addition to `datetime.utcnow()`? Did the 4 test files have datetime values flowing to MULTIPLE production files (not just their direct counterpart)? If so, propose a rule.

### C10 — Update SOVEREIGN_AI_HANDOFF.md

1. **"Last updated" line**: change to `2026-06-21 — post-prompt-58 (datetime cleanup)`
2. **Completed prompts table**: add row 58:
   ```
   | 58 | datetime.utcnow() cleanup | <C1 test count> | 118 utcnow replaced (28 test + 90 production). L19 compliance achieved. |
   ```
3. **Next 5 prompts**: remove Plan 58, shift up, add Plan 63:
   ```
   ### Plan 59 — Marine stack Python implementation (P2)
   ### Plan 60 — Full checkpoint scan (P1)
   ### Plan 61 — (open slot)
   ### Plan 62 — (open slot)
   ### Plan 63 — (open slot)
   ```

### C11 — Commit docs

```powershell
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-58 changelog and handoff update"
```

### C12 — Push

```powershell
git push origin master
git push origin prompt-58
```

### C13 — Post-push verification

```powershell
git ls-remote --tags origin | Select-String "prompt-58"
```

**Expected**: returns `<commit-sha>\trefs/tags/prompt-58`.

---

## STOP conditions summary

STOP and report if:
1. **S0.1**: prompt-57 tag not on origin
2. **S0.3**: master HEAD doesn't match `06ff457`
3. **S1.1**: test count ≠ 1167 passed
4. **S3.1-S3.3**: any test fails with `TypeError: can't compare offset-naive and offset-aware datetimes` — missed a coupled file
5. **S4.1/S4.2**: any utcnow remain after S3
6. **S5**: test count drops
7. **C7**: unexpected files in prompt-58 tag
8. **C13**: prompt-58 tag not on origin

When in doubt, STOP and report. (L4)

---

## Out of scope (deferred)

- **111 ruff errors** → future plan
- **283 mypy errors** → future plans
- **22 B108 in tests/** → future housekeeping plan
- **19 pip-audit CVEs** → wait for upstream patches
- **20 vulture findings** → permanent (16 Category C deferrals from Plan 57 — confirmed via Plan 57 CHANGELOG/handoff: 32→20, 16 removed, 16 deferred. Note: Plan 57's pre-execution REV2 expected ~7 deferrals, but the cls-decorator verification step from Claude's review surfaced more genuine C-deferrals than originally estimated. The 16 is the actual result, not the estimate.)
- **Marine stack Python implementation** → Plan 59
