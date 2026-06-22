# Plan 58.5 — Bare datetime.now() Cleanup (231 calls across 28 files)

**Prompt number**: 58.5
**Priority**: P3 (L19 compliance — completes Plan 58's work)
**Estimated scope**: 231 bare `datetime.now()` replacements across 28 files (7 production + 21 test)
**Baseline test count**: 1167 passed, 55 skipped, 0 failed (post-prompt-58)
**Baseline bare datetime.now()**: 231 across 28 files (verified via clone grep, NOT Devin's incomplete "46+" report)

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

**L25. When removing unused parameters identified by vulture in test files, verify the parameter is not required by pytest fixture dependencies or framework protocols. If removal breaks tests, defer to Category C.**

### CHANGELOG append position

**L21. CHANGELOG entries are ALWAYS appended to the END using `Add-Content -Encoding utf8`. NEVER insert at the top.**

### Environment

**L22. This project runs on Windows. Use PowerShell, not Unix commands.**

---

## Why this plan exists

Plan 58 fixed all `datetime.utcnow()` calls (106 replaced) but deferred bare `datetime.now()` calls (without timezone) to this plan. Plan 58's S4.3 HARD STOP reported "46+ calls across 9 files" — but that was an **incomplete scan**. The actual count (verified via clone grep) is **231 calls across 28 files**.

**Why the discrepancy**: Plan 58's S4.3 scan used `Select-String "datetime\.now\(\)" -Path core/ -Recurse -Include *.py` but Devin's report only listed files it found during a partial scan. Many test files with bare `datetime.now()` were missed. This plan uses the verified full count.

**L19 compliance**: bare `datetime.now()` returns local time (naive) — same L19 violation as `datetime.utcnow()`. This plan completes the L19 compliance work Plan 58 started.

**Triage required**: some bare `datetime.now()` calls may be intentional (e.g., displaying local time to user, logging local timestamps). Each call needs individual review before converting. This plan uses a 3-category triage like Plan 57.

---

## Opening steps (S0)

### S0.1 — Verify prompt-58 completed

```powershell
git ls-remote --tags origin | Select-String "prompt-58"
```

**Expected**: returns `51b4a3f26974730b3c1b5b94a8cd966a1ed8f362  refs/tags/prompt-58`. If empty, STOP.

### S0.2 — Pull latest master

```powershell
git pull origin master
```

### S0.3 — Verify HEAD

```powershell
git rev-parse HEAD
```

**Expected**: `d1907f1ae9d9870a5125e6d218f6f9e73f59517c`. If different, STOP.

---

## Step 1 (S1) — Capture baseline (run SEQUENTIALLY per L24, use -AllMatches)

### S1.1 — Test count baseline

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
```

**Expected**: `1167 passed, 55 skipped`. Record actual count.

### S1.2 — Count bare datetime.now() occurrences (use -AllMatches per Plan 58 lesson)

**Production files:**
```powershell
Get-ChildItem -Path core/ -Recurse -Include *.py | Select-String "datetime\.now\(\)" -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: 26 occurrences across 7 files.

**Test files:**
```powershell
Get-ChildItem -Path tests/ -Recurse -Include *.py | Select-String "datetime\.now\(\)" -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: 205 occurrences across 21 files.

**Total**: 231 across 28 files.

**STOP condition**: if actual count differs significantly from 231, investigate. The count was verified via clone grep on master HEAD `d1907f1`.

### S1.3 — Get per-file breakdown

```powershell
Get-ChildItem -Path core/ -Recurse -Include *.py | Select-String "datetime\.now\(\)" -AllMatches | Group-Object Path | Sort-Object Count -Descending | Select-Object Count, Name
Get-ChildItem -Path tests/ -Recurse -Include *.py | Select-String "datetime\.now\(\)" -AllMatches | Group-Object Path | Sort-Object Count -Descending | Select-Object Count, Name
```

**Expected production breakdown** (7 files, 26 total):
- core/session.py: 9
- core/instruction_generator.py: 6
- core/instruction_versioning.py: 5
- core/rating_system.py: 3
- core/handlers.py: 1
- core/scratchpad.py: 1
- core/task_state_machine.py: 1

**Expected test breakdown** (21 files, 205 total):
- tests/test_schemas.py: 31
- tests/test_task_state_machine.py: 18
- tests/test_instruction_versioning.py: 32
- tests/test_anthropic_adapter.py: 10
- tests/test_instruction_generator.py: 12
- tests/test_orchestrator.py: 7
- tests/test_together_adapter.py: 7
- (and 15 more files with 1-7 each)

---

## Step 2 (S2) — Triage into 3 categories

For EACH of the 231 findings, classify into:

**Category A — Safe to convert (test fixtures, no user-facing impact)**:
- Test files using `datetime.now()` in fixture setup, mock data, assertions
- These are always safe to convert to `datetime.now(timezone.utc)` — tests don't display time to users

**Category B — Convert with care (production code, internal timestamps)**:
- Production code using `datetime.now()` for internal timestamps (created_at, updated_at, etc.)
- Convert to `datetime.now(timezone.utc)` — these should be UTC for consistency
- Per L19, if the corresponding test file also has bare `datetime.now()`, fix both together

**Category C — Defer (intentional local time, user-facing display, or external systems expecting local time)**:
- Production code using `datetime.now()` for user-facing display (e.g., "last login: 2026-06-21 14:30 local time")
- Datetime written to external files/systems that expect local convention (e.g., Obsidian notes with local timestamps)
- These may need `datetime.now(tz)` with a specific local timezone, not UTC
- Document each deferral with: file:line, reason for deferral, suggested fix

### S2.1 — Triage production files first (26 calls, 7 files)

For each production file:
1. Read the file
2. For each `datetime.now()` call, examine the context (what variable is it assigned to? what's the downstream usage?)
3. Classify as A/B/C based on the criteria above
4. Record: `file:line | category | context (1-line summary)`

**Production files to triage**:
- core/session.py (9 calls) — likely Category B (session timestamps)
- core/instruction_generator.py (6 calls) — likely Category B
- core/instruction_versioning.py (5 calls) — likely Category B
- core/rating_system.py (3 calls) — likely Category B
- core/handlers.py (1 call) — check context (may be user-facing → Category C)
- core/scratchpad.py (1 call) — check context
- core/task_state_machine.py (1 call) — likely Category B

**Note on test files with no production coupling**: test_schemas.py, test_anthropic_adapter.py, test_orchestrator.py, test_together_adapter.py, and 17 other test files have NO production-side coupling risk because their corresponding production files have zero remaining bare `datetime.now()` calls (per S1.3 — `core/schemas.py` is not in the 7-file production list). These are safe to process independently in S3.2 as Category A.

### S2.2 — Triage test files (205 calls, 21 files)

Test files are almost always Category A (safe to convert) — tests don't display time to users. But verify:
- If a test asserts on a datetime FORMAT (e.g., "timestamp must be ISO format without timezone") → Category C (the test is explicitly checking naive format)
- Otherwise → Category A

**Expected**: ~200 Category A, ~5 Category C (edge cases)

---

## Step 3 (S3) — Convert Category A and B findings

Process by file, test+production pairs together per L9/L19.

### S3.1 — Process production files (Category B)

For each production file with Category B findings:
1. Replace `datetime.now()` with `datetime.now(timezone.utc)`
2. Ensure `timezone` is imported (add `from datetime import timezone` if missing)
3. Check if the corresponding test file also has bare `datetime.now()` — if yes, fix both in the same step (L9/L19)
4. Run the test file: `python -m pytest tests/test_<name>.py -v | Select-Object -Last 5`

**Production files + test counterparts**:
- core/session.py → tests/test_session.py
- core/instruction_generator.py → tests/test_instruction_generator.py
- core/instruction_versioning.py → tests/test_instruction_versioning.py
- core/rating_system.py → tests/test_rating_system.py (if exists)
- core/handlers.py → tests/test_handlers.py (if exists) or tests/test_query_handler.py
- core/scratchpad.py → tests/test_scratchpad.py
- core/task_state_machine.py → tests/test_task_state_machine.py

### S3.2 — Process test files (Category A)

For each test file with Category A findings:
1. Replace `datetime.now()` with `datetime.now(timezone.utc)`
2. Ensure `timezone` is imported
3. Run the test file: `python -m pytest tests/test_<name>.py -v | Select-Object -Last 5`

**CAUTION per Plan 58 lesson**: do NOT use a single find-and-replace across the whole file. Plan 58's `replace_all` corrupted a2a_protocol.py and escalation.py by mangling adjacent lines. Worse, a blanket `(Get-Content file) -replace 'datetime\.now\(\)', ...` would convert EVERY occurrence in the file — including any Category C deferrals living in the same file. Since S2 requires per-occurrence triage and some production files (handlers.py, scratchpad.py) may have mixed A/B/C in one file, a file-wide regex would silently re-convert occurrences that were supposed to stay deferred. **Target each occurrence by its specific line/context.**

**Skip occurrences already converted during S3.1's coupled-pair handling** — process only the remaining Category A occurrences not already touched. For example, if tests/test_session.py had 6 occurrences and 2 were converted during S3.1 (coupled with core/session.py), only convert the remaining 4 in S3.2.

### S3.3 — Document Category C deferrals

For each Category C finding (intentional local time):
1. Do NOT convert
2. Add `# L19-exception: intentional local time display` comment on the line (do NOT use `# noqa` syntax — ruff doesn't flag bare datetime.now() in the first place, so `noqa` would be a useless suppression that could trigger RUF100 unused-noqa errors, ironically creating new ruff errors in a plan that expects ruff count to stay unchanged)
3. Record in the triage log: `file:line | Category C | reason | suggested fix`

---

## Step 4 (S4) — Verify zero bare datetime.now() remain (except Category C)

### S4.1 — Production files

```powershell
Get-ChildItem -Path core/ -Recurse -Include *.py | Select-String "datetime\.now\(\)" -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: `<Category C count>` (only intentional deferrals remain).

### S4.2 — Test files

```powershell
Get-ChildItem -Path tests/ -Recurse -Include *.py | Select-String "datetime\.now\(\)" -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: `<Category C count>` (only intentional deferrals remain).

### S4.3 — Verify no new utcnow calls introduced

```powershell
Get-ChildItem -Path core/,tests/ -Recurse -Include *.py | Select-String "datetime\.utcnow\(\)" -AllMatches | ForEach-Object { $_.Matches.Count } | Measure-Object -Sum
```
**Expected**: `0` (Plan 58 already achieved this; verify no regression).

---

## Step 5 (S5) — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Expected**: `1167 passed, 55 skipped` (unchanged — datetime fix shouldn't change test count).

**STOP condition**: if test count drops or new failures appear, use the bisection fallback from Plan 57 §S5 (prompt-57 tag, commit e874f2b).

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

### C5 — Commit

```powershell
git add <in-scope files only>
git commit -m "refactor: replace <N> bare datetime.now() with datetime.now(timezone.utc) (Plan 58.5)"
```

### C6 — Tag

```powershell
git tag prompt-58.5
```

### C7 — Tag verification

```powershell
git show prompt-58.5 --stat | Select-Object -First 35
```

**Verify**: file list contains ONLY the files edited in S3. If unexpected files appear, fix.

### C8 — Update CHANGELOG.md (temp-file pattern)

```powershell
$lines = @(
    "",
    "## 2026-06-21 HH:MM — prompt-58.5",
    "",
    "**Plan**: Bare datetime.now() cleanup — L19 compliance completion",
    "",
    "**Changed**:",
    "- <N> bare datetime.now() calls replaced with datetime.now(timezone.utc)",
    "- <M> Category C deferrals (intentional local time) — documented with L19-exception comments",
    "",
    "**Results**:",
    "- Tests: 1167 passed, 55 skipped (unchanged)",
    "- bare datetime.now() count: 231 → <Category C count>",
    "- L19 compliance: achieved for all datetime calls (utcnow + bare now)",
    "- Tag: prompt-58.5 verified on origin"
)
Set-Content -Path "C:\Jarvis\scan\logs\changelog-entry-prompt-58.5.md" -Value $lines -Encoding utf8
$oldCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\logs\changelog-entry-prompt-58.5.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
$newCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 12
```

### C9 — Rule proposal (per L20 — MANDATORY)

Your closing report MUST include either a rule proposal OR explicit "none". **Silence is NOT acceptable.**

**Suggested reflection for this plan**:
- Did any Category A/B/C triage decisions surprise you? (e.g., a "safe" test conversion broke tests)
- Did you find more bare `datetime.now()` calls than expected? (the scope was 231, not 46+)
- Did the `replace_all` corruption from Plan 58 recur? (if so, propose a rule about targeted replacements vs replace_all)
- Did any production `datetime.now()` call turn out to be user-facing local time? (Category C)

### C10 — Update SOVEREIGN_AI_HANDOFF.md

1. **"Last updated" line**: change to `2026-06-21 — post-prompt-58.5 (bare datetime.now() cleanup)`
2. **Completed prompts table**: add row 58.5:
   ```
   | 58.5 | Bare datetime.now() cleanup | <C1 test count> | <N> bare datetime.now() replaced. <M> Category C deferrals. L19 compliance complete. |
   ```
3. **Next 5 prompts**: remove Plan 58.5, shift up:
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
git commit -m "docs: prompt-58.5 changelog and handoff update"
```

### C12 — Push

```powershell
git push origin master
git push origin prompt-58.5
```

### C13 — Post-push verification

```powershell
git ls-remote --tags origin | Select-String "prompt-58.5"
```

**Expected**: returns `<commit-sha>\trefs/tags/prompt-58.5`.

---

## STOP conditions summary

STOP and report if:
1. **S0.1**: prompt-58 tag not on origin
2. **S0.3**: master HEAD doesn't match `d1907f1`
3. **S1.1**: test count ≠ 1167 passed
4. **S1.2**: bare datetime.now() count differs significantly from 231
5. **S3.1-S3.2**: any test fails after conversion — revert that file's edits, move findings to Category C
6. **S5**: test count drops — use bisection fallback from Plan 57 §S5
7. **C7**: unexpected files in prompt-58.5 tag
8. **C13**: prompt-58.5 tag not on origin

When in doubt, STOP and report. (L4)

---

## Out of scope (deferred)

- **111 ruff errors** → future plan
- **283 mypy errors** → future plans
- **22 B108 in tests/** → future housekeeping plan
- **19 pip-audit CVEs** → wait for upstream patches
- **20 vulture findings** → permanent (16 Category C from Plan 57 + 4 from Plan 58)
- **Marine stack Python implementation** → Plan 59
- **Category C deferrals from this plan** → permanent (intentional local time, documented with L19-exception comments)
