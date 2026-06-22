# Plan 55 — Full Checkpoint Scan + Marine Stack Start (5-Plan Milestone)

**Prompt number**: 55
**Priority**: P1 (5-plan milestone scan) + P2 (Marine stack start)
**Estimated scope**: 6 full-repo scans + 4 SKILL.md files created
**Baseline test count**: 1167 passed, 55 skipped, 0 failed (post-prompt-54)
**Baseline ruff**: 111 errors (post-prompt-54, F401=0)
**Baseline mypy**: 282 errors (file-scoped samples; full-repo count TBD this plan)

---

## Section 0: Rules (read first, follow always)

These rules exist because each one prevents a specific failure that has actually occurred in this project. They are not aspirational — every rule traces to a documented mistake in the CHANGELOG. Follow them exactly. When in doubt, stop and ask.

**Numbering**: L1-Ln. These rules are related to but NOT 1:1 aligned with the handoff's "Known landmines" L-numbering (handoff L1-L24). Some rules appear in both systems with the same number (e.g. L19 datetime consistency); others appear in only one. When citing a rule, specify which system: "Section 0 L14" or "handoff L14". New Section 0 rules are added ONLY via L20 self-evolution (Devin proposes via C9, GLM accepts/rejects) — not by GLM mid-plan-drafting.

**Self-evolution (read this first)**: Rule **L20** is the meta-rule. Every plan's closing sequence MUST prompt Devin to propose new rules when it hits a recurring error pattern not covered here. This file is not static — it grows with the project's failures.

### Execution discipline

**L1. Follow the plan's verification gates in order. Run them, paste evidence, STOP on failure.**
Each prompt is delivered as a plan file with explicit verification gates and STOP conditions. Run each gate in the listed order. Do not mark a gate PASSED before running it. Do not mark a gate PASSED if its producing step is incomplete. Do not mark a gate SKIPPED unless the plan explicitly allows it. Gate output must be pasted literally into the CHANGELOG; "PASSED" without evidence is forbidden. If a gate fails, STOP and report — do not attempt to fix it by expanding scope. If a STOP condition fires, STOP. Plans 36 and 36.5 are the reference examples. **Never assert file content from memory** — when citing regex patterns, line numbers, method signatures, or tag formats, always read the actual file first (`Get-Content path\to\file`).

**L2. Run the relevant test file after each file change. Run the full suite at gates, not after every edit.**
After editing a production file, run its specific test file (`python -m pytest tests/test_<name>.py -v`). Run the full suite (`python -m pytest tests/ -q`) only at the plan's verification gates — before commit, before tag.

**L3. When you fix a bug, grep for the same pattern across the codebase before closing the prompt.**
When you fix a bug, search for the same pattern everywhere: `Select-String "pattern" -Path . -Recurse -Include *.py`. Fix all instances or document which are deferred.

**L4. Never silently substitute. If the spec says X, implement X. When in doubt, STOP and report. Do not improvise.**
If a plan specifies an exact value, format, method name, or file scope, implement exactly that. If a different approach seems better, STOP and flag it as an explicit deviation with rationale. **If anything is ambiguous** — a spec that seems wrong, a test that fails for an unexpected reason, a file outside scope that seems to need editing, a commit that didn't push, a tag that didn't create — STOP and report. Every regression in this project's history started with someone improvising past a STOP condition.

**L5. Do not expand scope when tests find pre-existing issues outside the plan.**
If a compliance test or new test reveals pre-existing violations in files outside the current plan's scope, do not fix them in the current prompt. Log them in the CHANGELOG, note them in the handoff's "What's broken" section, and flag for a dedicated housekeeping plan.

### Code construction

**L6. TraceEvent is defined in `core/observability.py`. Use exactly these fields: `event_type`, `component`, `level`, `message`, `data`, `duration_ms`.**
Never use `layer`, `payload`, or `success`. The correct import is `from core.observability import TraceEvent`.

**L7. Every class that emits trace events MUST use constructor-injected emitter. Never use the global `emit_trace()` function.**
Correct pattern: `def __init__(self, ..., emitter: TraceEmitter | None = None): self._emitter = emitter or MemoryTraceEmitter()`. Correct emit call: `await self._emitter.emit(TraceEvent(...))`.

**L8. Raise domain exceptions OUTSIDE try-except blocks. Never broad-except without a trace event.**
If you must use a broad `except Exception`, emit a trace event at WARNING level with the exception message inside the except block.

**L9. When fixing a production file, fix its test file in the same step.**
Sequence: fix one production file → fix its test file → run the relevant test file → confirm zero new failures → only then move to the next file.

**L10. Do not remove working implementation to make a test pass.**
When a regression appears, find the root cause and fix the test — never remove the implementation.

**L11. Verify field and class names against the actual schema file before using them.**
Before using any class or field from `core/schemas.py`, verify the exact name exists: `Select-String "^class " -Path core/schemas.py`.

**L12. Patch at the location where a class is defined, not where it is used.**
If the import is `from core.foo import Bar`, patch `core.foo.Bar`, not the importing module's `Bar`. Use `Select-String "import ClassName" -Path . -Recurse -Include *.py` to find the correct patch path.

**L13. Never mutate Pydantic model instances after construction in tests.**
Always construct the model with the desired state from the start.

### Testing

**L14. Tests must verify behaviour, not just confirm the code runs.**
Every test must capture the actual constructed object or call the actual function and assert something specific about the result. Do not mark a test `@pytest.mark.skip` for tests that "couldn't be mocked" — fix the mock or refactor the SUT.

**L15. In tests, construct `MemoryTraceEmitter()` and pass it via constructor injection. Retrieve events via `emitter.get_events()`, never `emitter.events`.**
Never use `ConsoleTraceEmitter` in tests — it prints to stdout and can't be inspected.

### Datetime consistency

**L19. Tests and production code MUST use the same timezone strategy. Never mix naive and aware `datetime` objects.**
Preferred project convention: `datetime.now(timezone.utc)` everywhere (aware, no deprecation in Python 3.12+). Never use `datetime.utcnow()` in new code. When fixing one side, fix the other side in the same step (L9 applies).

### CHANGELOG and documentation

**L16. The CHANGELOG must match the commit. Verify before reporting completion.**
Before writing the CHANGELOG entry, run `git show --stat HEAD` and verify the file list matches what you actually changed.

**L17. CHANGELOG format is simplified — ~10 lines per plan. Title, changed files, result, test count math. Record only non-trivial decisions, not every failed attempt.**
Each plan's CHANGELOG entry should be approximately 10 lines containing: Title, Changed files (bullet list), Result (1-2 sentences), Test count math (`baseline + new = final`), Non-trivial decisions only.

### Git and closing sequence

**L18. The correct closing sequence for every prompt:**
1. Run full test suite: `python -m pytest tests/ -q`. Confirm zero new failures vs baseline.
2. `ruff check <files_touched>` — zero errors.
3. `mypy <files_touched> --ignore-missing-imports` — zero errors. **Never `mypy .`** — file-scoped only. **EXCEPTION: 5-plan checkpoint plans (55, 60, 65...) use `mypy .` as part of the full scan — this is the point of those plans.**
4. `git add <in-scope files only> && git commit -m "checkpoint: prompt-{N}"`
5. `git tag prompt-{N}`
6. **Tag verification (mandatory):** `git show prompt-{N} --stat` — verify file list contains ONLY in-scope files.
7. Update `CHANGELOG.md` (append-only, using temp-file pattern — see Appendix A2).
8. Update `SOVEREIGN_AI_HANDOFF.md` per the plan's closing-step instructions.
9. **Rule proposal (L20):** scan your work for recurring error patterns not covered by Section 0. If found, append a "Rule proposal" section to your closing report.
10. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-{N} changelog and handoff update"`
11. `git push origin master && git push origin prompt-{N}`
12. **Post-push verification (mandatory):** `git ls-remote --tags origin | Select-String "prompt-{N}"` — verify tag exists on remote.

### Meta-rule: self-evolution

**L20. When you hit a recurring error pattern or a landmine not covered by these rules, propose a new rule to GLM in your closing report. This file grows with the project's failures.**
If you encountered a failure this prompt that recurred in 2+ previous prompts, required significant debugging time, or was not anticipated by an existing rule, propose a new rule. Format:

```
## Rule proposal for global_rules.md

Trigger: <what happened this prompt — concrete, with file + line>
Recurrence: <prompt numbers where this pattern bit, or "first occurrence">
Proposed rule: L{n+1}. <one-line rule statement>
Anchor: <prompt number + file + line>
Why existing rules didn't catch it: <one line>
```

If no new failure patterns, append: `## Rule proposal — none (no new failure patterns this prompt)`. **Silence is NOT acceptable.**

### Verification gate scoping

**L23. Verification gates must check the actual scope of prior plans, not the entire codebase. Verification commands must be scoped to match the prior plan's actual file scope, not the broadest possible directory.**
When writing a verification gate that checks a prior plan's work, first identify the prior plan's actual file scope (from its CHANGELOG entry or `git show prompt-{N} --stat`), then scope the verification command to those files only. Broad scans are for 5-plan checkpoints (Plan 55, 60, 65...), not for per-plan verification gates. *(Proposed by Devin during Plan 54 C9 — first L20 activation.)*

### CHANGELOG append position

**L21. CHANGELOG entries are ALWAYS appended to the END using `Add-Content -Encoding utf8`. NEVER insert at the top. Oldest entry at top, newest at the bottom.**
Use the temp-file pattern (Appendix A2). Before appending, record current line count; after appending, verify the new count exceeds the old count.

### Environment

**L22. This project runs on Windows. Use PowerShell, not Unix commands.**
Never use `grep`, `cat`, `touch`, `head`, `tail`, or any Unix shell command. Always use PowerShell equivalents.

### Appendix A1: PowerShell command cheatsheet

| Need | PowerShell | Never use |
|---|---|---|
| Search file contents | `Select-String "pattern" -Path path\to\file` | `grep` |
| Recursive search (Python only) | `Select-String "pattern" -Path . -Recurse -Include *.py` | `grep -r` |
| Count pattern matches | `Select-String -Path file -Pattern "pat" \| Measure-Object -Line` | `grep -c` |
| Read entire file | `Get-Content path\to\file` | `cat` |
| Read first N lines | `Get-Content file \| Select-Object -First N` | `head -N` |
| Read last N lines | `Get-Content file \| Select-Object -Last N` | `tail -N` |
| Line count | `(Get-Content file).Count` | `wc -l` |
| List directory | `Get-ChildItem` | `ls` |
| Create empty file | `New-Item -Path file -ItemType File` | `touch` |

### Appendix A2: CHANGELOG append procedure

For entries >5 lines, use the temp-file pattern (avoids here-string hang):
1. Write entry to `C:\Jarvis\scan\logs\changelog-entry-prompt-{N}.md` using `Set-Content -Value $lines -Encoding utf8` where `$lines = @(...)`.
2. Record old count: `$oldCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count`.
3. Append: `Get-Content $temp | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8`.
4. Verify: `$newCount > $oldCount` and last N lines show the entry.

---

## Why this plan exists

This is the **5-plan milestone** (Plans 51-55 complete). Per L18, full-repo `mypy .` is ONLY allowed at 5-plan checkpoints. This plan:
1. Runs the full checkpoint scan (ruff + mypy . + bandit -r + pip-audit + vulture + pytest) to establish fresh baselines for Plans 56-60.
2. Starts the Marine stack (weather, AIS, tidal, passage_planner) as portable SKILL.md files — the first new horizontal capability since the cognition-loop wiring.

---

## Opening steps (S0)

### S0.1 — Verify prompt-54 completed and tag on origin

```powershell
git ls-remote --tags origin | Select-String "prompt-54"
```

**Expected**: returns `e90b44d7893912953670d443c642ddc4cecadaf80  refs/tags/prompt-54`. If empty, STOP.

### S0.2 — Pull latest master

```powershell
git pull origin master
```

### S0.3 — Verify HEAD matches expected commit

```powershell
git rev-parse HEAD
```

**Expected**: `32344c07e416a300fef1b8caa304ce384dcb9ffc` (Plan 54 docs commit). If different, STOP — master has moved.

---

## Step 1 (S1) — Full checkpoint scan (6 tools)

This is the ONLY step where `mypy .` is allowed. Run all 6 tools and paste output. These become the new baselines for Plans 56-60.

### S1.1 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Expected**: `1167 passed, 55 skipped` (unchanged from Plan 54). Record the actual count.

### S1.2 — Ruff full-repo

```powershell
ruff check . 2>&1 | Select-Object -Last 5
```

**Expected**: ~111 errors (post-prompt-54 baseline). Record the actual count and breakdown by rule.

### S1.3 — Mypy full-repo (ALLOWED HERE ONLY — L18 exception)

```powershell
mypy . --ignore-missing-imports 2>&1 | Select-Object -Last 5
```

**Expected**: ~282 errors (handoff baseline). Record the actual count. This will take 2-5 minutes — that's expected.

**STOP condition**: if mypy count increased significantly (>50) from the 282 baseline, investigate — Plans 51-54 should have reduced it, not increased it.

### S1.4 — Bandit full-repo

```powershell
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache,globalrules 2>&1 | Select-Object -Last 10
```

**Expected**: 22 B108 in tests/ (pre-existing, deferred) + other medium+ findings. Record the breakdown by severity and rule.

**Mandatory**: the `--exclude` list must include `.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache` (per handoff landmine L14 — bandit commands MUST use this exclude list to avoid scanning virtualenvs and caches). Added `globalrules` to excludes (rules files aren't code).

### S1.5 — pip-audit

```powershell
pip-audit 2>&1 | Select-Object -Last 10
```

**Expected**: ~55 CVEs across ~14 packages (handoff baseline). Record the actual count and list.

### S1.6 — Vulture

```powershell
vulture . --min-confidence 80 2>&1 | Select-Object -Last 10
```

**Expected**: ~47 high-confidence findings (handoff baseline). Record the actual count.

---

## Step 2 (S2) — Compile scan summary

Create a summary file for the handoff update:

```powershell
$summary = @(
    "## Plan 55 Full Checkpoint Scan Results",
    "",
    "**Date**: 2026-06-21",
    "**Test baseline**: <S1.1 result>",
    "",
    "**Ruff**: <S1.2 result> errors total",
    "- F401: 0 (fixed in Plan 54)",
    "- Other: <breakdown>",
    "",
    "**Mypy (full-repo)**: <S1.3 result> errors",
    "- Was 282 (handoff baseline)",
    "- Delta: <+/-N>",
    "",
    "**Bandit**: <S1.4 result>",
    "- B108: 22 (pre-existing in tests/, deferred to follow-up)",
    "- Other medium+: <count>",
    "",
    "**pip-audit**: <S1.5 result> CVEs across <N> packages",
    "",
    "**Vulture**: <S1.6 result> high-confidence findings",
    "",
    "**New baselines for Plans 56-60**: tests=<S1.1>, ruff=<S1.2>, mypy=<S1.3>, bandit=<S1.4>, pip-audit=<S1.5>, vulture=<S1.6>"
)
Set-Content -Path "C:\Jarvis\scan\logs\plan-55-checkpoint-scan.md" -Value $summary -Encoding utf8
Get-Content C:\Jarvis\scan\logs\plan-55-checkpoint-scan.md
```

**Paste**: the full summary content. This is used in C10 to update the handoff.

---

## Step 3 (S3) — Start Marine stack (4 SKILL.md files)

The Marine stack is the first new horizontal capability. Per the project vision, these are portable SKILL.md files (not Python skills). Create 4 skill directories under `skills/marine/`:

### S3.1 — Create directory structure

```powershell
New-Item -Path skills\marine\weather -ItemType Directory -Force
New-Item -Path skills\marine\ais -ItemType Directory -Force
New-Item -Path skills\marine\tidal -ItemType Directory -Force
New-Item -Path skills\marine\passage_planner -ItemType Directory -Force
```

### S3.2 — Create SKILL.md for weather

Create `skills/marine/weather/SKILL.md` using this exact template structure (markdown `##` headers — S4.1 verifies these headers exist):

```markdown
# Marine Weather Skill

## Name
Marine Weather

## Purpose
Fetch and summarize marine weather forecasts (wind, waves, precipitation, visibility) for a given lat/lon box.

## Inputs
- lat (float): latitude
- lon (float): longitude
- days (int, default 7): forecast horizon

## Outputs
Structured forecast summary (JSON) with per-day wind speed/direction, wave height, precipitation, visibility.

## Data Source
Open-Meteo Marine API (free, no API key required)
- Marine: `https://marine-api.open-meteo.com/v1/marine`
- Weather: `https://api.open-meteo.com/v1/forecast`

## Rate Limits
10,000 calls/day (free tier)

## Caching
30-minute TTL (weather doesn't change faster)

## Error Handling
If API unreachable, return last cached forecast + WARNING trace event.

## Approval Gate
NOT required (read-only, no side effects)

## Example Invocation
`marine_weather --lat 1.3521 --lon 103.8198 --days 7`
```

Use this exact `## Name`, `## Purpose`, `## Inputs`, `## Outputs` header structure — S4.1 verifies these headers exist via regex.

### S3.3 — Create SKILL.md for AIS

Create `skills/marine/ais/SKILL.md` using the same `## Name` / `## Purpose` / `## Inputs` / `## Outputs` header structure as S3.2 (S4.1 verifies these headers). Content:

```markdown
# AIS Vessel Tracker Skill

## Name
AIS Vessel Tracker

## Purpose
Query AIS (Automatic Identification System) data for vessel positions within a bounding box.

## Inputs
- min_lat (float): minimum latitude
- max_lat (float): maximum latitude
- min_lon (float): minimum longitude
- max_lon (float): maximum longitude

## Outputs
List of vessels with MMSI, name, lat, lon, speed, heading, timestamp.

## Data Source
AISHub (requires API key — user must provide via env var `AISHUB_API_KEY`)
- Endpoint: `http://data.aishub.net/ws.php?username={KEY}&format=1&output=json&compress=0&latmin={min_lat}&latmax={max_lat}&lonmin={min_lon}&lonmax={max_lon}`

## Security Note
AISHub does not offer HTTPS as of writing (2026-06). The API key is sent as a plaintext query parameter over HTTP. This is a known limitation of the upstream service, not a project defect. When a HTTPS endpoint becomes available, switch to it. Do not log the API key or vessel MMSIs in trace events — only counts.

## Rate Limits
Per AISHub plan (free tier: 5 queries/hour)

## Caching
60-second TTL (vessel positions update frequently)

## Error Handling
If API unreachable or no API key set, return empty list + WARNING trace event.

## Approval Gate
NOT required (read-only)

## Privacy
Do not log vessel names or MMSIs in trace events — only counts.
```

**Note**: the `## Security Note` section documents the HTTP plaintext-credential limitation per Claude's review flag.

### S3.4 — Create SKILL.md for tidal

Create `skills/marine/tidal/SKILL.md` using the same `## Name` / `## Purpose` / `## Inputs` / `## Outputs` header structure as S3.2 (S4.1 verifies these headers). Content:

```markdown
# Tidal Height Predictor Skill

## Name
Tidal Height Predictor

## Purpose
Predict tide heights and times for a given station and date range.

## Inputs
- station_id (str): NOAA station identifier
- start_date (date): forecast start
- end_date (date): forecast end

## Outputs
List of high/low tide events with timestamp and height (meters).

## Data Source
NOAA CO-OPS API (free, no API key)
- Endpoint: `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station={STATION}&begin_date={YYYYMMDD}&end_date={YYYYMMDD}&product=predictions&datum=MLLW&units=metric&time_zone=gmt&format=json`

## Rate Limits
Per NOAA (generous, no documented limit)

## Caching
24-hour TTL (tide predictions are deterministic for future dates)

## Error Handling
If station_id invalid, return empty list + ERROR trace event.

## Approval Gate
NOT required (read-only)
```

### S3.5 — Create SKILL.md for passage_planner

Create `skills/marine/passage_planner/SKILL.md` using the same `## Name` / `## Purpose` / `## Inputs` / `## Outputs` header structure as S3.2 (S4.1 verifies these headers). Content:

```markdown
# Passage Planner Skill

## Name
Passage Planner

## Purpose
Plan a sailing passage between two waypoints, considering weather, tides, and vessel characteristics.

## Inputs
- start (lat, lon): departure waypoint
- end (lat, lon): destination waypoint
- vessel_speed (knots, default 6): average cruising speed
- departure_time (datetime): earliest departure

## Outputs
Passage plan with waypoints, ETA, weather windows, tidal constraints.

## Data Source
Aggregates weather (marine_weather skill), tidal (marine_tidal skill), and optional AIS (marine_ais skill).

## Dependencies
Calls marine_weather, marine_tidal skills; optionally calls marine_ais.

## Algorithm
1. Calculate great-circle distance and bearing
2. Fetch weather along route (sample every 50nm)
3. Fetch tides at start/end points
4. Identify weather windows (wind < 25 knots, waves < 2m)
5. Output plan with recommended departure window

## Approval Gate
NOT required for planning (read-only aggregation). If the plan triggers an action (e.g. "send to chart plotter"), that action would require approval.

## Limitation
v1 is advisory only — does not account for current, leeway, or vessel-specific polars. Documented here.
```

### S3.6 — Verify all 4 SKILL.md files exist

```powershell
Get-ChildItem -Path skills\marine -Recurse -Filter "SKILL.md" | Select-Object FullName
```

**Expected**: 4 files listed. If any missing, create it before proceeding.

---

## Step 4 (S4) — Verify SKILL.md files are valid

### S4.1 — Check each SKILL.md has required sections

```powershell
Get-ChildItem -Path skills\marine -Recurse -Filter "SKILL.md" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $hasName = $content -match "## Name"
    $hasPurpose = $content -match "## Purpose"
    $hasInputs = $content -match "## Inputs"
    $hasOutputs = $content -match "## Outputs"
    Write-Output "$($_.Name): Name=$hasName Purpose=$hasPurpose Inputs=$hasInputs Outputs=$hasOutputs"
}
```

**Expected**: all 4 files show `Name=True Purpose=True Inputs=True Outputs=True`. If any False, fix the SKILL.md before proceeding.

### S4.2 — Verify no Python code created (Marine stack is SKILL.md only this plan)

```powershell
Get-ChildItem -Path skills\marine -Recurse -Include "*.py"
```

**Expected**: empty. This plan creates SKILL.md files only — Python implementation is deferred to a future plan. If any .py files exist, STOP — scope creep.

---

## Closing steps (C1-C13) — MANDATORY

### C1 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Paste**: last 5 lines. **Expected**: `1167 passed, 55 skipped` (unchanged — SKILL.md files don't affect tests).

### C2 — Ruff check on touched files

```powershell
ruff check skills/marine/ 2>&1 | Select-Object -Last 3
```

**Paste**: last 3 lines. **Expected**: `All checks passed!` or `Found 0 errors.` (SKILL.md files aren't Python).

### C3 — Ruff total (post-plan)

```powershell
ruff check . 2>&1 | Select-Object -Last 3
```

**Paste**: last 3 lines. **Expected**: same as S1.2 (~111 errors — this plan doesn't touch Python).

### C4 — Mypy (file-scoped — no Python files touched this plan)

No mypy check needed — this plan creates .md files only. Skip with note: "C4 skipped — no Python files touched (SKILL.md files only). Per L18, mypy is file-scoped and there are no files to scope."

### C5 — Commit (code/skills only, NO docs yet)

```powershell
git add skills/marine/
git commit -m "feat: start marine stack — 4 SKILL.md files (weather, AIS, tidal, passage_planner)"
```

### C6 — Tag

```powershell
git tag prompt-55
```

### C7 — Tag verification (mandatory per L17)

```powershell
git show prompt-55 --stat | Select-Object -First 15
```

**Paste**: first 15 lines. **Verify**: file list contains ONLY `skills/marine/*/SKILL.md` files (4 files). If any unexpected file appears, `git tag -d prompt-55`, clean, re-commit, re-tag.

### C8 — Update CHANGELOG.md (SIMPLIFIED, ~10 lines, temp-file pattern per L21)

```powershell
$lines = @(
    "",
    "## 2026-06-21 HH:MM — prompt-55",
    "",
    "**Plan**: 5-plan milestone — full checkpoint scan + Marine stack start",
    "",
    "**Changed**:",
    "- skills/marine/weather/SKILL.md: created (Open-Meteo Marine API)",
    "- skills/marine/ais/SKILL.md: created (AISHub, requires API key)",
    "- skills/marine/tidal/SKILL.md: created (NOAA CO-OPS API)",
    "- skills/marine/passage_planner/SKILL.md: created (aggregates weather + tidal)",
    "",
    "**Results**:",
    "- Tests: 1167 passed, 55 skipped (unchanged)",
    "- Ruff: <S1.2> (unchanged — no Python touched)",
    "- Mypy (full-repo): <S1.3> (was 282)",
    "- Bandit: <S1.4>",
    "- pip-audit: <S1.5> CVEs",
    "- Vulture: <S1.6> findings",
    "- Tag: prompt-55 verified on origin"
)
Set-Content -Path "C:\Jarvis\scan\logs\changelog-entry-prompt-55.md" -Value $lines -Encoding utf8
$oldCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\logs\changelog-entry-prompt-55.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
$newCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 12
```

**Verify**: `$newCount > $oldCount`, last 12 lines show prompt-55 entry.

### C9 — Rule proposal (per L20 — MANDATORY)

Your closing report MUST include either:

**Option A** — propose a new rule:
```
## Rule proposal for global_rules.md

Trigger: <what happened this prompt — concrete, with file + line>
Recurrence: <prompt numbers where this pattern bit, or "first occurrence">
Proposed rule: L{n+1}. <one-line rule statement>
Anchor: <prompt number + file + line>
Why existing rules didn't catch it: <one line>
```

**Option B** — explicit none:
```
## Rule proposal — none (no new failure patterns this prompt)
```

**Silence is NOT acceptable.**

### C10 — Update SOVEREIGN_AI_HANDOFF.md

Update ALL of:

1. **"Last updated" line** (line 3): change to `2026-06-21 — post-prompt-55 (5-plan milestone: full scan + Marine stack start)`

2. **Test baseline** (line 5): keep as `1167 passed, 55 skipped, 0 failures, 0 warnings`

3. **Static analysis baseline** (lines 7-12): update with S1 results:
   ```
   **Static analysis baseline (post-prompt-55 — 5-plan milestone)**:
   - Ruff: <S1.2> errors (F401=0 since Plan 54)
   - Mypy (full-repo): <S1.3> errors (was 282 — delta <+/-><N>)
   - Bandit: <S1.4> (22 B108 pre-existing in tests/, deferred)
   - pip-audit: <S1.5> CVEs across <N> packages (deferred to Plan 56)
   - Vulture: <S1.6> high-confidence findings (deferred to Plan 57)
   ```

4. **Completed prompts table** (after row 54): add row 55:
   ```
   | 55 | 5-plan milestone: full scan + Marine stack start | 1167 | 4 SKILL.md files created (weather, AIS, tidal, passage_planner). Full-repo scan: ruff=<S1.2>, mypy=<S1.3>, bandit=<S1.4>, pip-audit=<S1.5>, vulture=<S1.6>. Fresh baselines for Plans 56-60. |
   ```

5. **Next 5 prompts** (replace Plan 55 section): shift up, add Plan 60:
   ```
   ### Plan 56 — Dependency updates (P2)
   - Fix <S1.5> CVEs across <N> packages. Upgrade or pin vulnerable dependencies.

   ### Plan 57 — Vulture cleanup (P3)
   - Fix <S1.6> high-confidence dead code findings.

   ### Plan 58 — Remaining datetime.utcnow() cleanup (P3)
   - Fix 28 remaining utcnow in 4 test files + 90 in 17 production files. Per L19.

   ### Plan 59 — Marine stack Python implementation (P2)
   - Implement the 4 Marine SKILL.md files as Python skills (weather first, then tidal, AIS, passage_planner).

   ### Plan 60 — Full checkpoint scan (P1)
   - 5-plan milestone: full scan. Verify Plans 56-59 progress.
   ```

6. **What's built but not reachable** table: add 4 new rows for the Marine skills (currently SKILL.md only, no Python):
   ```
   | MarineWeather (SKILL.md) | skills/marine/weather/SKILL.md | Spec only — no Python implementation yet (Plan 59) |
   | MarineAIS (SKILL.md) | skills/marine/ais/SKILL.md | Same |
   | MarineTidal (SKILL.md) | skills/marine/tidal/SKILL.md | Same |
   | MarinePassagePlanner (SKILL.md) | skills/marine/passage_planner/SKILL.md | Same |
   ```

### C11 — Commit docs

```powershell
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-55 changelog, handoff update, 5-plan milestone baselines"
```

### C12 — Push

```powershell
git push origin master
git push origin prompt-55
```

### C13 — Post-push verification (MANDATORY per L17)

```powershell
git ls-remote --tags origin | Select-String "prompt-55"
```

**Paste**: the output. **Expected**: returns `<commit-sha>\trefs/tags/prompt-55`.

---

## Plan completion checklist (Devin must paste ALL before reporting done)

```
1. S1.1 tests: <paste last 5 lines — must show 1167 passed, 55 skipped>
2. S1.2 ruff: <paste last 5 lines — full-repo count>
3. S1.3 mypy (full-repo): <paste last 5 lines — full-repo count>
4. S1.4 bandit: <paste last 10 lines>
5. S1.5 pip-audit: <paste last 10 lines>
6. S1.6 vulture: <paste last 10 lines>
7. S2 scan summary: <paste the full summary file content>
8. S3.6 marine files: <paste Get-ChildItem output — 4 SKILL.md files>
9. S4.1 SKILL.md sections: <paste verification output — all True>
10. S4.2 no Python: <paste empty output>
11. C1 tests: <paste last 5 lines>
12. C5 commit: <paste git commit output>
13. C6 tag: <paste git tag --list prompt-55>
14. C7 file list: <paste git show prompt-55 --stat — 4 SKILL.md files only>
15. C8 CHANGELOG: <paste last 12 lines>
16. C9 rule proposal: <paste proposal block OR "none">
17. C10 handoff: <paste new Completed row 55 + new Next-5-Prompts>
18. C11 docs commit: <paste git commit output>
19. C12 push: <paste git push output>
20. C13 tag on origin: <paste git ls-remote --tags origin | Select-String "prompt-55">
```

---

## STOP conditions summary

STOP and report if:
1. **S0.1**: prompt-54 tag not on origin
2. **S0.3**: master HEAD doesn't match `32344c0`
3. **S1.1**: test count ≠ 1167 passed (baseline drift)
4. **S1.3**: mypy count increased >50 from 282 baseline
5. **S3.6**: any SKILL.md file missing
6. **S4.1**: any SKILL.md missing required sections (Name, Purpose, Inputs, Outputs)
7. **S4.2**: any .py files created in skills/marine/ (scope creep)
8. **C7**: unexpected files in prompt-55 tag
9. **C13**: prompt-55 tag not on origin after push

When in doubt, STOP and report. (L4)

---

## Out of scope (deferred)

- **Marine stack Python implementation** → Plan 59
- **28 test + 90 production utcnow** → Plan 58
- **pip-audit CVEs** → Plan 56
- **vulture findings** → Plan 57
- **111 ruff errors (non-F401)** → future plan
- **282 mypy errors** → future plans
- **22 B108 in tests/** → future plan (not Plan 56-57, separate housekeeping)
