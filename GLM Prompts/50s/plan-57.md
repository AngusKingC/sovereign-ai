# Plan 57 — Vulture Cleanup (32 high-confidence findings)

**Prompt number**: 57
**Priority**: P3 (dead code removal)
**Estimated scope**: ~32 dead-code removals across 4 directories (adapters, core, tests, workers)
**Baseline test count**: 1167 passed, 55 skipped, 0 failed (post-prompt-56)
**Baseline vulture**: 32 high-confidence findings (post-prompt-55 scan)

---

## Section 0: Rules (read first, follow always)

These rules exist because each one prevents a specific failure that has actually occurred in this project. They are not aspirational — every rule traces to a documented mistake in the CHANGELOG. Follow them exactly. When in doubt, stop and ask.

**Numbering**: L1-Ln. These rules are related to but NOT 1:1 aligned with the handoff's "Known landmines" L-numbering (handoff L1-L24). Some rules appear in both systems with the same number; others appear in only one. When citing a rule, specify which system: "Section 0 L14" or "handoff L14".

**Self-evolution (read this first)**: Rule **L20** is the meta-rule. Every plan's closing sequence MUST prompt Devin to propose new rules when it hits a recurring error pattern not covered here.

### Execution discipline

**L1. Follow the plan's verification gates in order. Run them, paste evidence, STOP on failure.**
Run each gate in listed order. Do not mark a gate PASSED before running it. Gate output must be pasted literally into the CHANGELOG. If a gate fails, STOP and report. **Never assert file content from memory** — always read the actual file first.

**L2. Run the relevant test file after each file change. Run the full suite at gates, not after every edit.**

**L3. When you fix a bug, grep for the same pattern across the codebase before closing the prompt.**

**L4. Never silently substitute. If the spec says X, implement X. When in doubt, STOP and report. Do not improvise.**

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

**L18 note**: even if no code changes (docs-only plan), you MUST still create the tag. The tag marks the prompt's completion, not just the code commit. Tag the docs commit if no code commit exists.

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
Plan 55 ran 6 scan tools in parallel — output streams mixed, producing contaminated results. The corrupted pip-audit output reported "37 CVEs" when the actual count was 55; this wrong baseline propagated to the handoff. Run scan tools one at a time, capture each tool's output, verify it matches expected format before running the next.

### CHANGELOG append position

**L21. CHANGELOG entries are ALWAYS appended to the END using `Add-Content -Encoding utf8`. NEVER insert at the top.**

### Environment

**L22. This project runs on Windows. Use PowerShell, not Unix commands.**

---

## Why this plan exists

Plan 55's full scan found 32 high-confidence vulture findings. This plan removes dead code (unused variables, unreachable functions, unused imports that ruff F401 didn't catch). Vulture findings at 100% confidence are safe to remove — vulture only flags code that is provably never referenced.

**Breakdown from Plan 55 scan:**
- adapters: 13 (all `structured_output` unused variable)
- core: 8 (last_check_time, record_type, cls x4, structured_output x2)
- tests: 10 (mock clients, req, raw_output, auth)
- workers: 1 (structured_output)
- **Total: 32** (13 + 8 + 10 + 1)

---

## Opening steps (S0)

### S0.1 — Verify prompt-56 completed

```powershell
git ls-remote --tags origin | Select-String "prompt-56"
```

**Expected**: returns `b2f8682835ea95b5cba7f08be4e473b9e3f02473  refs/tags/prompt-56`. If empty, STOP.

### S0.2 — Pull latest master

```powershell
git pull origin master
```

### S0.3 — Verify HEAD

```powershell
git rev-parse HEAD
```

**Expected**: `b2f8682835ea95b5cba7f08be4e473b9e3f02473`. If different, STOP.

---

## Step 1 (S1) — Capture baseline

### S1.1 — Test count baseline

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
```

**Expected**: `1167 passed, 55 skipped`. Record actual count.

### S1.2 — Vulture baseline (run SEQUENTIALLY — per L24, do not run other tools in parallel)

```powershell
vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache
```

**Expected**: 32 findings. **Paste the FULL output** — this is the work list for this plan. Verify the count matches Plan 55's scan (32). If different, investigate why before proceeding.

**STOP condition (per L24)**: if vulture output looks contaminated (mixed with other tools' output, missing the expected `file:line: unused variable 'name' (100% confidence)` format), STOP — re-run vulture alone until output is clean.

---

## Step 2 (S2) — Triage findings into 3 categories

For EACH of the 32 findings, classify into one of:

**Category A — Safe to remove (just delete the line)**:
- Unused local variables assigned but never read (e.g. `structured_output = ...` where the variable is never used)
- Unused mock assignments in tests (e.g. `mock_client = patch(...)` where `mock_client` is never asserted on)

**Category B — Remove the variable, keep the call (side effects matter)**:
- Cases where the assignment has a side effect (e.g. `result = await handler.execute(command)` where `execute()` emits trace events but `result` is unused). Remove the `result = ` part, keep the `await handler.execute(command)` call.

**Category C — Defer (don't remove, document why)**:
- Cases where the variable looks unused but might be intentional (e.g. `cls` parameters in class methods that pydantic/mypy require)
- Cases where removal would change behavior subtly

For each finding, record: `file:line | category | action taken`

---

## Step 3 (S3) — Remove Category A and B findings

Work through the 32 findings one file at a time. Per L9, fix the test file in the same step as the production file.

### S3.1 — Process adapters (13 findings)

For each adapter file with `structured_output` unused:
```powershell
# Read the file
Get-Content adapters\anthropic.py | Select-Object -First 80
```

Identify the `structured_output = ...` line. Determine if it's Category A (delete the line) or Category B (remove `structured_output = `, keep the right-hand expression if it has side effects).

After editing each adapter, run its test file:
```powershell
python -m pytest tests/test_anthropic_adapter.py -v | Select-Object -Last 5
```

**STOP condition**: if any test fails, revert the edit and move the finding to Category C (defer).

### S3.2 — Process core (8 findings)

Files and findings:
- `core/event_trigger.py` — 1 finding (`last_check_time`)
- `core/memory_router.py` — 1 finding (`record_type`)
- `core/schemas.py` — 4 findings (`cls` x4)
- `core/worker_base.py` — 1 finding (`structured_output`)
- `core/worker_factory.py` — 1 finding (`structured_output`)

**BEFORE processing `core/schemas.py` cls findings — verify decorator context** (per Claude review):
```powershell
Select-String "@validator|@root_validator|@field_validator|@classmethod" core/schemas.py -Context 1,0
```
For each of the 4 `cls` findings in `core/schemas.py`:
- If the `cls` parameter belongs to a method decorated with `@validator`, `@root_validator`, `@field_validator`, or `@classmethod` that genuinely uses `cls` → Category C (defer — pydantic/classmethod protocol requires it)
- If the `cls` parameter belongs to a `@classmethod` that NEVER references `cls` in its body → Category A (refactor to `@staticmethod`, remove `cls` parameter). This is real dead code, not a false positive.
- If the method has no decorator → STOP and report (unexpected; investigate before proceeding)

**CAUTION**: do NOT blanket-defer all 4 `cls` findings. Verify each one individually against the decorator context above.

After editing each core file, run its corresponding test file:
```powershell
python -m pytest tests/test_event_trigger.py -v | Select-Object -Last 5
python -m pytest tests/test_memory_router.py -v | Select-Object -Last 5
python -m pytest tests/test_schemas.py -v | Select-Object -Last 5
python -m pytest tests/test_worker_base.py -v | Select-Object -Last 5
python -m pytest tests/test_worker_factory.py -v | Select-Object -Last 5
```

If `tests/test_schemas.py` doesn't exist, fall back to `tests/test_di_compliance.py` or run the full suite to verify schemas changes. Per L1, don't guess filenames — verify with `Test-Path tests/test_schemas.py` first.

### S3.3 — Process tests (10 findings)

Files: `tests/test_anthropic_adapter.py` (mock_anthropic_client), `tests/test_cohere_adapter.py` (mock_cohere_client), etc. + `tests/test_security.py` (req), `tests/test_serve.py` (auth), `tests/test_task_state_machine.py` (raw_output).

For mock variables: if the mock is assigned but never asserted on, change `with patch('...') as mock_x:` to `with patch('...'):` (drop the `as mock_x`).

After editing each test file, run it:
```powershell
python -m pytest tests/test_anthropic_adapter.py -v | Select-Object -Last 5
```

### S3.4 — Process workers (1 finding)

File: `workers/echo_worker.py` (structured_output).

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
```

---

## Step 4 (S4) — Re-run vulture to verify cleanup

```powershell
vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache
```

**Expected**: findings count should drop from 32 to ~7 (the Category C deferrals — mostly `cls` parameters in `core/schemas.py`).

Record the new count and the list of remaining findings (these are the Category C deferrals).

---

## Step 5 (S5) — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Expected**: `1167 passed, 55 skipped` (unchanged — dead code removal shouldn't affect tests).

**STOP condition**: if test count drops or new failures appear, a "dead code" removal was actually load-bearing. Revert and move that finding to Category C.

**Bisection fallback** (if S5 fails despite all S3 individual tests passing): this indicates a cross-file interaction — multiple "safe" edits combine to break something. By this point dozens of edits sit uncommitted in the working tree together. To isolate the offending edit:
1. Review the full edit set: `git diff --stat`
2. Bisect by reverting roughly half the edits: `git checkout -- <half of the edited files>`
3. Re-run the full suite: `python -m pytest tests/ -q --tb=short | Select-Object -Last 3`
4. If tests pass → the offending edit is in the reverted half. Re-apply half of those and re-test.
5. If tests still fail → the offending edit is in the non-reverted half. Revert more.
6. Repeat until you've isolated the single offending edit. Move that finding to Category C (defer) and document why in the CHANGELOG.

This bisection takes O(log N) full-suite runs for N edits — far faster than reverting one-at-a-time from the end.

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

List the actual files touched in S3. **Expected**: zero errors on touched files.

### C3 — Ruff total

```powershell
ruff check . 2>&1 | Select-Object -Last 3
```

**Expected**: ~111 errors or fewer (vulture cleanup may also resolve some F841 ruff errors).

### C4 — File-scoped mypy on touched files

```powershell
mypy <files_touched> --ignore-missing-imports 2>&1 | Select-Object -Last 3
```

**Expected**: error count ≤ baseline (vulture cleanup shouldn't introduce mypy errors).

### C5 — Commit

```powershell
git add <in-scope files only>
git commit -m "refactor: remove 32 dead-code findings (vulture, Plan 57)"
```

### C6 — Tag

```powershell
git tag prompt-57
```

### C7 — Tag verification

```powershell
git show prompt-57 --stat | Select-Object -First 20
```

**Verify**: file list contains ONLY the files edited in S3. If unexpected files appear, fix.

### C8 — Update CHANGELOG.md (temp-file pattern)

```powershell
$lines = @(
    "",
    "## 2026-06-21 HH:MM — prompt-57",
    "",
    "**Plan**: Vulture cleanup — 32 high-confidence dead-code findings",
    "",
    "**Changed**:",
    "- <list of files edited, one per line, with finding count>",
    "",
    "**Results**:",
    "- Tests: 1167 passed, 55 skipped (unchanged)",
    "- Vulture: 32 → <S4 result> findings (<N> removed, <M> deferred as Category C)",
    "- Category C deferrals: <list with reasons>",
    "- Tag: prompt-57 verified on origin"
)
Set-Content -Path "C:\Jarvis\scan\logs\changelog-entry-prompt-57.md" -Value $lines -Encoding utf8
$oldCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\logs\changelog-entry-prompt-57.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
$newCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 12
```

### C9 — Rule proposal (per L20 — MANDATORY)

Your closing report MUST include either a rule proposal OR explicit "none". **Silence is NOT acceptable.**

**Suggested reflection for this plan**: did any "dead code" removal turn out to be load-bearing (broke tests)? Did vulture produce false positives that wasted triage time? Did the Category A/B/C split work, or did you find a better triage approach? If so, propose a rule.

### C10 — Update SOVEREIGN_AI_HANDOFF.md

1. **"Last updated" line**: change to `2026-06-21 — post-prompt-57 (vulture cleanup)`
2. **Static analysis baseline**: update vulture line to `<S4 result> findings (was 32 — Plan 57 removed <N>, deferred <M> as Category C)`
3. **Completed prompts table**: add row 57:
   ```
   | 57 | Vulture cleanup | <C1 test count> | <N> dead-code findings removed. <M> deferred (Category C). Vulture: 32→<result>. |
   ```
4. **Next 5 prompts**: remove Plan 57, shift up, add Plan 62:
   ```
   ### Plan 58 — Remaining datetime.utcnow() cleanup (P3)
   ### Plan 59 — Marine stack Python implementation (P2)
   ### Plan 60 — Full checkpoint scan (P1)
   ### Plan 61 — (open slot for next GLM scoping)
   ### Plan 62 — (open slot)
   ```

### C11 — Commit docs

```powershell
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-57 changelog and handoff update"
```

### C12 — Push

```powershell
git push origin master
git push origin prompt-57
```

### C13 — Post-push verification

```powershell
git ls-remote --tags origin | Select-String "prompt-57"
```

**Expected**: returns `<commit-sha>\trefs/tags/prompt-57`.

---

## Plan completion checklist

```
1. S1.1 tests: <paste last 3 lines — must show 1167 passed, 55 skipped>
2. S1.2 vulture: <paste FULL output — must show 32 findings>
3. S2 triage: <paste the 32 findings with Category A/B/C classification>
4. S3.1 adapters: <paste test output after each adapter edit>
5. S3.2 core: <paste test output after each core edit>
6. S3.3 tests: <paste test output after each test edit>
7. S3.4 workers: <paste test output>
8. S4 vulture re-run: <paste output — must show reduced count>
9. S5 tests: <paste last 5 lines — must show 1167 passed, 55 skipped>
10. C1 tests: <paste last 5 lines>
11. C2 ruff touched files: <paste last 3 lines>
12. C3 ruff total: <paste last 3 lines>
13. C4 mypy: <paste last 3 lines>
14. C5 commit: <paste git commit output>
15. C6 tag: <paste git tag --list prompt-57>
16. C7 file list: <paste git show prompt-57 --stat>
17. C8 CHANGELOG: <paste last 12 lines>
18. C9 rule proposal: <paste proposal block OR "none">
19. C10 handoff: <paste new Completed row 57 + updated vulture baseline>
20. C11 docs commit: <paste git commit output>
21. C12 push: <paste git push output>
22. C13 tag on origin: <paste git ls-remote --tags origin | Select-String "prompt-57">
```

---

## STOP conditions summary

STOP and report if:
1. **S0.1**: prompt-56 tag not on origin
2. **S0.3**: master HEAD doesn't match `b2f8682`
3. **S1.1**: test count ≠ 1167 passed
4. **S1.2**: vulture output contaminated (per L24) — re-run until clean
5. **S3.1-S3.4**: any test fails after a removal — revert that finding to Category C
6. **S5**: test count drops — a "dead code" removal was load-bearing
7. **C7**: unexpected files in prompt-57 tag
8. **C13**: prompt-57 tag not on origin

When in doubt, STOP and report. (L4)

---

## Out of scope (deferred)

- **111 ruff errors** → future plan
- **283 mypy errors** → future plans
- **22 B108 in tests/** → future housekeeping plan
- **19 pip-audit CVEs** → wait for upstream patches (chromadb, diskcache) or FastAPI starlette 1.x support
- **28 test + 90 production utcnow** → Plan 58
- **Marine stack Python implementation** → Plan 59
- **Category C deferrals** (cls parameters in core/schemas.py) → permanent (pydantic protocol requirement)
