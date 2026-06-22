# Plan 56 — Dependency Updates (37 CVEs across 14 packages)

**Prompt number**: 56
**Priority**: P2 (security debt)
**Estimated scope**: ~10 dependency upgrades, 1 requirements file update
**Baseline test count**: 1167 passed, 55 skipped, 0 failed (post-prompt-55)
**Baseline pip-audit**: 37 CVEs across 14 packages

---

## Section 0: Rules (read first, follow always)

These rules exist because each one prevents a specific failure that has actually occurred in this project. They are not aspirational — every rule traces to a documented mistake in the CHANGELOG. Follow them exactly. When in doubt, stop and ask.

**Numbering**: L1-Ln. These rules are related to but NOT 1:1 aligned with the handoff's "Known landmines" L-numbering (handoff L1-L24). Some rules appear in both systems with the same number (e.g. L19 datetime consistency); others appear in only one. When citing a rule, specify which system: "Section 0 L14" or "handoff L14". New Section 0 rules are added ONLY via L20 self-evolution (Devin proposes via C9, GLM accepts/rejects) — not by GLM mid-plan-drafting.

**Self-evolution (read this first)**: Rule **L20** is the meta-rule. Every plan's closing sequence MUST prompt Devin to propose new rules when it hits a recurring error pattern not covered here. This file is not static — it grows with the project's failures.

### Execution discipline

**L1. Follow the plan's verification gates in order. Run them, paste evidence, STOP on failure.**
Run each gate in the listed order. Do not mark a gate PASSED before running it. Gate output must be pasted literally into the CHANGELOG; "PASSED" without evidence is forbidden. If a gate fails, STOP and report. **Never assert file content from memory** — always read the actual file first.

**L2. Run the relevant test file after each file change. Run the full suite at gates, not after every edit.**

**L3. When you fix a bug, grep for the same pattern across the codebase before closing the prompt.**

**L4. Never silently substitute. If the spec says X, implement X. When in doubt, STOP and report. Do not improvise.**
If a plan specifies an exact value, format, method name, or file scope, implement exactly that. If a different approach seems better, STOP and flag it as an explicit deviation. If anything is ambiguous, STOP and report.

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

### CHANGELOG append position

**L21. CHANGELOG entries are ALWAYS appended to the END using `Add-Content -Encoding utf8`. NEVER insert at the top.**

### Environment

**L22. This project runs on Windows. Use PowerShell, not Unix commands.**

---

## Why this plan exists

Plan 55's full scan found 37 CVEs across 14 packages. This plan upgrades vulnerable dependencies to fixed versions. Some upgrades are safe (minor/patch bumps); some are risky (major version bumps that may break code). Risky upgrades are deferred to separate plans if they cause test failures.

---

## Opening steps (S0)

### S0.1 — Verify prompt-55 completed

```powershell
git ls-remote --tags origin | Select-String "prompt-55"
```

**Expected**: returns `b6e5cb2679e2a6d0cf742b9456d6b2cbc50eb6d2  refs/tags/prompt-55`. If empty, STOP.

### S0.2 — Pull latest master

```powershell
git pull origin master
```

### S0.3 — Verify HEAD

```powershell
git rev-parse HEAD
```

**Expected**: `fb5d152cde8e80506099241d790336bdf4c8d36b`. If different, STOP.

---

## Step 1 (S1) — Capture baseline

### S1.1 — Test count baseline

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
```

**Expected**: `1167 passed, 55 skipped`. Record actual count.

### S1.2 — pip-audit baseline

```powershell
pip-audit 2>&1 | Select-Object -Last 5
```

**Expected**: `Found 37 known vulnerabilities in 14 packages`. Record actual count.

### S1.3 — Check current requirements file

```powershell
Get-Content requirements.txt
```

**Paste**: the full content. This is the file you'll be updating.

If `requirements.txt` doesn't exist, check for `pyproject.toml` or `setup.cfg`:
```powershell
Get-Content pyproject.toml
```

---

## Step 2 (S2) — Safe upgrades (minor/patch bumps)

These are low-risk upgrades. Upgrade each, run tests, move to the next only if tests pass.

### S2.1 — Upgrade safe packages

```powershell
pip install --upgrade aiohttp==3.13.4 cryptography==48.0.1 idna==3.15 pygments==2.20.0 pypdf==6.13.3 pytest==9.0.3 python-dotenv==1.2.2 python-multipart==0.0.31 urllib3==2.7.0
```

**Note**: these are the packages with available fix versions that are minor/patch bumps. Do NOT upgrade pillow, starlette, or setuptools yet (major bumps — S3).

### S2.2 — Run tests after safe upgrades

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Expected**: `1167 passed, 55 skipped` (unchanged). If tests fail, STOP — investigate which package caused the failure. If a specific package breaks, pin it back to the old version and note in CHANGELOG.

**STOP condition**: if test count drops or new failures appear, identify the offending package by upgrading one at a time:

```powershell
pip install --upgrade aiohttp==3.13.4
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
pip install --upgrade cryptography==48.0.1
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
# ... repeat for each package
```

### S2.3 — Re-run pip-audit after safe upgrades

```powershell
pip-audit 2>&1 | Select-Object -Last 5
```

**Expected**: CVE count should drop from 37 (the 9 safe packages account for ~20 CVEs: aiohttp 6 + cryptography 1 + idna 1 + pygments 1 + pypdf 1 + pytest 1 + python-dotenv 1 + python-multipart 5 + urllib3 3 = 20). Record actual count.

---

## Step 3 (S3) — Risky upgrades (major version bumps)

These are higher-risk. Upgrade ONE at a time, test after each, STOP if any break.

### S3.1 — Pillow 11.3.0 → 12.2.0

```powershell
pip install --upgrade pillow==12.2.0
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**STOP condition**: if tests fail, revert: `pip install pillow==11.3.0`. Paste the actual test failure output (first 10 lines of traceback) into the CHANGELOG entry alongside the revert — this is MANDATORY per Finding 6, so the next person revisiting this upgrade can diagnose without re-running. Note in CHANGELOG: "Pillow 12.x reverted — test failures in <test names>. Failure output: <paste>."

### S3.2 — Starlette 0.52.1 → 1.3.1

**WARNING**: Starlette 1.x is a major version bump. FastAPI depends on Starlette — upgrading may break FastAPI. Check FastAPI's actual version constraints first using `importlib.metadata` (NOT `pip show`, which only lists dependency names without version specifiers):

```powershell
python -c "import importlib.metadata as m; reqs = m.metadata('fastapi').get_all('Requires-Dist') or []; [print(r) for r in reqs if 'starlette' in r.lower()]"
```

**Expected output**: a line like `starlette<1.0,>=0.40` or `starlette>=0.40` showing the actual version constraint. Read the constraint carefully:
- If the constraint says `starlette<1.0` or similar upper bound — do NOT upgrade Starlette. Note in CHANGELOG: "Starlette 1.x deferred — FastAPI requires starlette<1.0. Will upgrade when FastAPI supports Starlette 1.x."
- If the constraint allows 1.x (e.g. `starlette>=0.40` with no upper bound, or `starlette<2.0`) — proceed with upgrade.

If the constraint allows 1.x:
```powershell
pip install --upgrade starlette==1.3.1
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**STOP condition**: if tests fail, revert: `pip install starlette==0.52.1`. Paste the actual test failure output (first 10 lines of traceback) into the CHANGELOG entry alongside the revert — this is MANDATORY per Finding 6, so the next person revisiting this upgrade can diagnose without re-running. Note in CHANGELOG: "Starlette 1.3.1 reverted — test failures in <test names>. Failure output: <paste>."

### S3.3 — Setuptools 65.5.0 → 78.1.1

```powershell
pip install --upgrade setuptools==78.1.1
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**STOP condition**: if tests fail, revert: `pip install setuptools==65.5.0`. Paste the actual test failure output (first 10 lines of traceback) into the CHANGELOG entry alongside the revert — this is MANDATORY per Finding 6, so the next person revisiting this upgrade can diagnose without re-running. Note in CHANGELOG: "Setuptools 78.x reverted — test failures in <test names>. Failure output: <paste>."

### S3.4 — Re-run pip-audit after risky upgrades

```powershell
pip-audit 2>&1 | Select-Object -Last 5
```

Record the new CVE count. Each successful risky upgrade should drop the count further.

---

## Step 4 (S4) — Document packages with no fix available

From the pip-audit output, these packages have CVEs but no fix version listed:
- **chromadb 1.5.0** — CVE-2026-45829 (no fix version)
- **diskcache 5.6.3** — CVE-2025-69872 (no fix version)

For each, follow this procedure (mirrors S2/S3 safety discipline per Finding 4):

1. **Check if a newer version exists**:
   ```powershell
   pip index versions chromadb 2>&1 | Select-Object -First 3
   pip index versions diskcache 2>&1 | Select-Object -First 3
   ```

2. **If a newer version exists, verify it actually addresses the CVE before upgrading speculatively** (per Finding 4 — don't take on upgrade risk for zero security benefit):
   - Check the package's changelog/release notes on PyPI or GitHub for the CVE ID or advisory ID
   - If the changelog explicitly mentions fixing CVE-2026-45829 (chromadb) or CVE-2025-69872 (diskcache), proceed to step 3
   - If the changelog does NOT mention the CVE, do NOT upgrade speculatively — note in CHANGELOG: "<package> <newer version> exists but does not document fixing <CVE ID>. Upgrade deferred — no confirmed security benefit."

3. **If the newer version confirmedly addresses the CVE, try upgrading**:
   ```powershell
   pip install --upgrade chromadb==<newer version>
   python -m pytest tests/ -q --tb=short | Select-Object -Last 5
   ```
   **STOP condition**: if tests fail, revert: `pip install chromadb==1.5.0`. Paste the actual test failure output (first 10 lines of traceback) into the CHANGELOG entry alongside the revert — this is MANDATORY per Finding 6. Note in CHANGELOG: "chromadb <newer version> reverted — test failures in <test names>. Failure output: <paste>."

4. **If no newer version exists OR the newer version doesn't address the CVE OR upgrade breaks tests**, document in CHANGELOG: "<package> <version> <CVE ID> — no fix available, deferred until upstream patches."

Repeat for diskcache.

---

## Step 5 (S5) — Update requirements file (branch on S1.3 finding)

**Per Finding 5**: S1.3 captured the current requirements.txt format. Branch here based on what S1.3 found:

### S5.1 — Determine requirements.txt format

```powershell
$lineCount = (Get-Content requirements.txt).Count
Write-Output "requirements.txt has $lineCount lines"
Get-Content requirements.txt | Select-Object -First 20
```

**Decision criteria**:
- If requirements.txt has **<30 lines** and lists only direct dependencies (e.g. `fastapi`, `ollama`, `pydantic`, `rich`, `textual` — NOT transitive deps like `h11`, `anyio`, `certifi`) → it's a **curated/minimal** list. Use S5.2 (targeted update).
- If requirements.txt has **>100 lines** and lists many transitive dependencies with pinned versions (e.g. `h11==0.14.0`, `anyio==4.12.1`) → it's a **full freeze**. Use S5.3 (regenerate via pip freeze).
- If unclear → default to S5.2 (targeted update) to avoid scope creep per L5.

### S5.2 — Curated/minimal requirements.txt (targeted update)

Update ONLY the packages actually upgraded this plan, preserving all other lines unchanged:

```powershell
# For each upgraded package, replace its line in requirements.txt
# Example for aiohttp (if it was upgraded):
$content = Get-Content requirements.txt
$updated = $content -replace '^aiohttp==.*', 'aiohttp==3.13.4'
$updated = $updated -replace '^cryptography==.*', 'cryptography==48.0.1'
$updated = $updated -replace '^idna==.*', 'idna==3.15'
# ... repeat for each upgraded package
Set-Content -Path requirements.txt -Value $updated -Encoding utf8
Get-Content requirements.txt | Select-String 'aiohttp|cryptography|idna|pillow|pygments|pypdf|pytest|python-dotenv|python-multipart|setuptools|starlette|urllib3'
```

**Verify**: only the upgraded packages show new versions; all other lines unchanged.

### S5.3 — Full freeze requirements.txt (regenerate)

If S1.3 confirmed the file is already a full freeze, regenerate it:

```powershell
pip freeze > requirements.txt
Get-Content requirements.txt | Select-String 'aiohttp|cryptography|idna|pillow|pygments|pypdf|pytest|python-dotenv|python-multipart|setuptools|starlette|urllib3'
```

**Verify**: the upgraded packages show the new versions.

### S5.4 — Verify diff is minimal

```powershell
git diff requirements.txt
```

**Verify**: the diff should show ONLY the upgraded package version changes. If the diff is massive (hundreds of lines changed), STOP — you likely used S5.3 on a curated file. Switch to S5.2 and redo.

---

## Closing steps (C1-C13) — MANDATORY

### C1 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Paste**: last 5 lines. **Expected**: `1167 passed, 55 skipped` (or note any changes).

### C2 — Ruff check on touched files

```powershell
ruff check requirements.txt 2>&1 | Select-Object -Last 3
```

**Expected**: `All checks passed!` (requirements.txt isn't Python, ruff should skip it).

### C3 — Ruff total

```powershell
ruff check . 2>&1 | Select-Object -Last 3
```

**Expected**: ~111 errors (unchanged — no Python code changed).

### C4 — Mypy (file-scoped — no Python files touched)

Skip with note: "C4 skipped — no Python files touched (requirements.txt only)."

### C5 — Commit

```powershell
git add requirements.txt
git commit -m "security: upgrade vulnerable dependencies (Plan 56)"
```

### C6 — Tag

```powershell
git tag prompt-56
```

### C7 — Tag verification

```powershell
git show prompt-56 --stat | Select-Object -First 10
```

**Verify**: file list contains ONLY `requirements.txt`. If unexpected files appear, fix.

### C8 — Update CHANGELOG.md (temp-file pattern)

```powershell
$lines = @(
    "",
    "## 2026-06-21 HH:MM — prompt-56",
    "",
    "**Plan**: Dependency updates — 37 CVEs across 14 packages",
    "",
    "**Changed**:",
    "- requirements.txt: upgraded <list of packages upgraded>",
    "",
    "**Results**:",
    "- Tests: <C1 result>",
    "- pip-audit: 37 → <S2.3/S3.4 result> CVEs",
    "- Packages deferred: <list of packages that couldn't be upgraded, with reasons>",
    "- Tag: prompt-56 verified on origin"
)
Set-Content -Path "C:\Jarvis\scan\logs\changelog-entry-prompt-56.md" -Value $lines -Encoding utf8
$oldCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\logs\changelog-entry-prompt-56.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
$newCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 12
```

### C9 — Rule proposal (per L20 — MANDATORY)

Your closing report MUST include either a rule proposal OR explicit "none". **Silence is NOT acceptable.**

**Suggested reflection for this plan**: did any dependency upgrade break tests in a way that took significant debugging time? Did pip-audit give misleading counts? Did a "safe" minor bump actually break something? If so, propose a rule.

### C10 — Update SOVEREIGN_AI_HANDOFF.md

1. **"Last updated" line**: change to `2026-06-21 — post-prompt-56 (dependency updates)`
2. **Static analysis baseline**: update pip-audit line to `<S2.3/S3.4 result> CVEs across <N> packages (was 37 — Plan 56 fixed <count>)`
3. **Completed prompts table**: add row 56:
   ```
   | 56 | Dependency updates | <C1 test count> | <N> packages upgraded. pip-audit: 37→<result> CVEs. <list deferred packages>. |
   ```
4. **Next 5 prompts**: remove Plan 56, shift up, add Plan 61:
   ```
   ### Plan 57 — Vulture cleanup (P3)
   ### Plan 58 — Remaining datetime.utcnow() cleanup (P3)
   ### Plan 59 — Marine stack Python implementation (P2)
   ### Plan 60 — Full checkpoint scan (P1)
   ### Plan 61 — (open slot for next GLM scoping)
   ```

### C11 — Commit docs

```powershell
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-56 changelog and handoff update"
```

### C12 — Push

```powershell
git push origin master
git push origin prompt-56
```

### C13 — Post-push verification

```powershell
git ls-remote --tags origin | Select-String "prompt-56"
```

**Expected**: returns `<commit-sha>\trefs/tags/prompt-56`.

---

## Plan completion checklist

```
1. S1.1 tests: <paste last 3 lines>
2. S1.2 pip-audit: <paste last 5 lines — must show 37 CVEs>
3. S2.2 tests after safe upgrades: <paste last 5 lines>
4. S2.3 pip-audit after safe upgrades: <paste last 5 lines>
5. S3.1 pillow test result: <paste last 5 lines OR "reverted — test failures">
6. S3.2 starlette test result: <paste last 5 lines OR "deferred — FastAPI incompatible">
7. S3.3 setuptools test result: <paste last 5 lines OR "reverted">
8. S3.4 pip-audit after risky upgrades: <paste last 5 lines>
9. S4 no-fix packages: <paste documentation>
10. S5 requirements.txt: <paste upgraded package versions>
11. C1 tests: <paste last 5 lines>
12. C5 commit: <paste git commit output>
13. C6 tag: <paste git tag --list prompt-56>
14. C7 file list: <paste git show prompt-56 --stat>
15. C8 CHANGELOG: <paste last 12 lines>
16. C9 rule proposal: <paste proposal block OR "none">
17. C10 handoff: <paste new Completed row 56 + updated pip-audit baseline>
18. C11 docs commit: <paste git commit output>
19. C12 push: <paste git push output>
20. C13 tag on origin: <paste git ls-remote --tags origin | Select-String "prompt-56">
```

---

## STOP conditions summary

STOP and report if:
1. **S0.1**: prompt-55 tag not on origin
2. **S0.3**: master HEAD doesn't match `fb5d152`
3. **S1.1**: test count ≠ 1167 passed
4. **S2.2**: safe upgrades break tests (identify offending package, revert, note in CHANGELOG)
5. **S3.1-S3.3**: risky upgrades break tests (revert, note in CHANGELOG, continue with other packages)
6. **C7**: unexpected files in prompt-56 tag
7. **C13**: prompt-56 tag not on origin

When in doubt, STOP and report. (L4)

---

## Out of scope (deferred)

- **111 ruff errors** → future plan
- **283 mypy errors** → future plans
- **22 B108 in tests/** → future housekeeping plan
- **32 vulture findings** → Plan 57
- **28 test + 90 production utcnow** → Plan 58
- **Marine stack Python implementation** → Plan 59
- **chromadb/diskcache CVEs with no fix** → wait for upstream patches
