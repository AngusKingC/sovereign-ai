# Plan 38.5: Finish warnings cleanup — missed PytestWarning files, real \J hunt, remaining cat 2, Gemini migration

> **This is REV1 of Plan 38.5.** Four scopes bundled:
> 1. Finish Step 3 (Plan 38 authoring error) — fix 4 test files Plan 38 missed (17 PytestWarnings)
> 2. Hunt the real `\J` escape — Plan 38 Step 4 only fixed NEWFILE_TEMPLATE.py but 1 warning remains with `<unknown>:1` source
> 3. Finish Step 6 — fix 4 remaining cat 2 warnings (PytestUnraisableException + ResourceWarning unclosed transport)
> 4. Gemini SDK migration (deferred from Plan 38 Step 7) — apply with 20-line guard; defer to Plan 38.7 if exceeded
>
> **Critical sequencing rule**: Same as Rule 19. Execute steps in order. Paste literal pytest output into CHANGELOG per step. No "PASSED" without evidence. No "SKIPPED" without plan authority.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-38..HEAD -- tests/ adapters/gemini.py system/NEWFILE_TEMPLATE.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> If any of these files changed since prompt-38, compare the "Current state" against live code before proceeding; on mismatch, STOP.

## Status

- **Priority**: P1 (debt cleanup continuation)
- **Effort**: S–M (4 small scopes, each well-defined)
- **Risk**: LOW (test file mechanical fixes + one production-code migration with guard)
- **Depends on**: prompt-38 (commit `a745d3d`, tag `prompt-38`)
- **Planned at**: master HEAD post-prompt-38, 2026-06-19
- **In scope**:
  - Production: `adapters/gemini.py` (Step 7 Gemini migration, 20-line guard)
  - Tests: `tests/test_web_server.py`, `tests/test_adapter_fallback.py`, `tests/test_model_evaluator.py`, `tests/test_verbosity.py` (Step 1 — finish Step 3 from Plan 38)
  - Tests: remaining cat 2 warning sources (Step 3 — finish Step 6 from Plan 38)
  - Search: hunt for real `\J` escape source across `.py`, `.cfg`, `.ini`, `.toml` files (Step 2)
  - Docs: `SOVEREIGN_AI_HANDOFF.md`, `CHANGELOG.md`
- **Out of scope**: broad-except audit (Plan 38.5→39+), ruff triage (Plan 43), mypy triage (Plan 44), trajectory_exporter redesign (Plan 45), Plan 38.6 (manual TUI verification — separate plan)

## Why this matters

Plan 38 landed at 26 warnings (down from 63) — good progress, but the plan missed four real issues that this plan addresses:

1. **17 PytestWarnings from 4 test files Plan 38 didn't list.** Plan 38 Step 3 fixed 8 files based on session 2's sample analysis, but 4 more files had the same `pytestmark = pytest.mark.asyncio` problem. The sample was incomplete. This plan enumerates and fixes all of them.

2. **1 remaining `\J` DeprecationWarning** with source `<unknown>:1`. Plan 38 Step 4 fixed `system/NEWFILE_TEMPLATE.py` (correctly — that file had the escape), but 1 warning remains. The `<unknown>:1` source identifier is unusual — it means the warning is from a string Python parses dynamically (docstring, config file, etc.). Devin's explanation that "it's pyvenv.cfg, not in scope" doesn't fit — `<unknown>:1` is not how pyvenv.cfg warnings surface.

3. **4 remaining cat 2 warnings** (PytestUnraisableException + ResourceWarning unclosed transport). Plan 38 Step 6 only fixed 2 of 6. The 4 remaining indicate test files where `httpx.AsyncClient` mocks aren't properly cleaning up their transports.

4. **Gemini SDK migration deferred from Plan 38 Step 7.** Devin deferred to "Phase 9" — that's not a real plan number. This plan either migrates it (if under the 20-line guard) or formally defers to Plan 38.7 with the inline `# noqa: Plan 38.7` suppression pattern from Plan 38.

**Combined effect**: 26 warnings → ≤2 warnings (1 Gemini if deferred + 1 residual). Goal is 0 warnings if Gemini migrates cleanly, 1 if it doesn't.

## What's broken (verified against grouped warning output from prompt-38)

### A. 17 PytestWarnings — `pytestmark = pytest.mark.asyncio` on 4 missed test files

Plan 38 Step 3 fixed 8 files but missed 4. Source of warning counts (from prompt-38 CHANGELOG baseline line 7040 and grouped output):

| File | Warnings |
|---|---|
| `tests/test_web_server.py` | 15 (per prompt-38 CHANGELOG baseline: "15 in web_server.py alone") |
| `tests/test_adapter_fallback.py` | ~1 (residual after Plan 38's 8-file fix) |
| `tests/test_model_evaluator.py` | ~1 (residual) |
| `tests/test_verbosity.py` | ~1 (residual) |
| **Total** | **~17** (Plan 38 baseline recorded ~17 for this category; prompt-38 final state preserves all 17 because Plan 38 Step 3 didn't touch these 4 files) |

**Note on count discrepancy**: The grouped warning output from prompt-38's final run shows individual PytestWarning lines per affected test function. The exact count per file depends on how many `async def test_*` methods each file contains — prompt-38's baseline of "15 in web_server.py alone" was recorded BEFORE Plan 38 Step 3 ran, and Plan 38 Step 3 didn't touch `test_web_server.py`, so the 15 should still be present. The actual count may vary slightly based on which methods are sync vs async; Devin should verify by running the per-file warning count himself at Step 2 verification time.

These 4 files were called out in the **session 2 handoff's warnings analysis** as part of category 3, but Plan 38's author only enumerated 8 files based on a partial grep. The session 2 handoff text was correct; Plan 38's enumeration was incomplete.

### B. 1 DeprecationWarning: invalid escape sequence `\J`

Source identifier: `<unknown>:1`. This is unusual — it means Python's parser is tokenizing a string from somewhere other than a direct `.py` file source line.

Most likely candidates:
1. A `.py` file's docstring containing `C:\Jarvis\...` (we already fixed `NEWFILE_TEMPLATE.py` but there may be others)
2. A `.cfg`, `.ini`, or `.toml` file processed by `configparser`/`tomllib` containing a Windows path with `\J`
3. A dynamically-evaluated string (`eval()` or `exec()`) containing `\Jarvis`
4. A pytest configuration file (`pytest.ini`, `pyproject.toml`, `setup.cfg`) with `\J` in a docstring or path

Devin's claim that this is from `pyvenv.cfg` is plausible (pyvenv.cfg does contain `home = C:\Users\King\...` style paths) but `<unknown>:1` is not the typical source identifier for pyvenv.cfg warnings — those usually say `pyvenv.cfg:1`. We need to verify.

### C. 4 cat 2 warnings — unclosed subprocess transports (NOT httpx.AsyncClient)

**CRITICAL — read prompt-38 CHANGELOG line 7116 and 7124 before starting this step.** Prompt-38 Step 6 already investigated this category and reached a specific conclusion that this step must build on, not re-litigate:

> "Plan specified httpx.AsyncClient, but actual warnings are from subprocess transports (asyncio.create_subprocess_exec). 6 warnings reduced to 4 after cleanup attempts."
>
> "Remaining warnings are Windows-specific asyncio transport cleanup issues that occur when event loop closes before subprocess transports are cleaned. This is a pytest-asyncio/Windows interaction issue, not a code bug. Tests still pass."

Source files (confirmed by prompt-38 Step 6 investigation):
- `tests/skills/test_docker_skill.py`
- `tests/skills/test_web_scraper.py`

**Mechanism**: Both files invoke `asyncio.create_subprocess_exec()` (docker skill calls `docker` CLI; web_scraper may use a subprocess for headless rendering or similar). When the pytest-asyncio event loop closes at test teardown, the subprocess transports haven't been cleaned up yet, triggering `PytestUnraisableExceptionWarning` and `ResourceWarning: unclosed transport`.

**This is NOT a code bug.** It's a pytest-asyncio/Windows interaction. The fix is at the test-fixture level, not the production-code level.

### D. 1 FutureWarning — Gemini SDK deprecation

```
C:\Jarvis\adapters\gemini.py:12: FutureWarning:
https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md
```

Plan 38 Step 7 deferred this to "Phase 9" — wrong target. **Prompt-38 CHANGELOG line 7138 confirms**: `SKIPPED per memory instruction: "FutureWarning in adapters/gemini.py — do not touch until Phase 9."` So Devin was following a memory instruction that uses "Phase 9" as the deferral name. This plan either migrates it (if under 20-line guard) or formally defers to **Plan 38.7** with the inline `# noqa: Plan 38.7` pattern, replacing the vague "Phase 9" reference with a concrete plan ticket.

## What to change

### Step 1 — Drift check + baseline evidence

**Command sequence** (paste all output literally into CHANGELOG as Step 1 evidence):

```powershell
# Drift check
git diff --stat prompt-38..HEAD -- tests/ adapters/gemini.py system/NEWFILE_TEMPLATE.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md

# Baseline test counts (must match prompt-38 final state)
python -m pytest tests/ -q --tb=short 2>&1 | Select-Object -Last 3

# Warning breakdown
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "Warning|warning|Deprecat" | Group-Object | Sort-Object Count -Descending | Format-Table Count, Name -AutoSize
```

**STOP if baseline is not 1080 passed / 29 skipped / 1 failed / 26 warnings.** Investigate drift before proceeding.

**Paste into CHANGELOG** (literal — required by Rule 19):
```
#### Step 1 — Baseline evidence

Baseline test counts:
<literal last-3-lines of pytest>

Warning breakdown:
<literal group-by output>

Drift check:
<literal git diff --stat output>
```

### Step 2 — Fix 4 missed test files (finish Plan 38 Step 3)

**Files** (verified from grouped warning output):
- `tests/test_web_server.py` (11 warnings)
- `tests/test_adapter_fallback.py` (2 warnings)
- `tests/test_model_evaluator.py` (2 warnings)
- `tests/test_verbosity.py` (1 warning)

**Change per file**: Remove the module-level `pytestmark = pytest.mark.asyncio` line (or class-level `pytestmark`), and add `@pytest.mark.asyncio` decorator to each individual `async def test_*` method.

```python
# Before (problematic):
pytestmark = pytest.mark.asyncio

class TestFoo:
    async def test_a(self): ...
    def test_b(self): ...  # sync method — generates PytestWarning
    async def test_c(self): ...

# After (fixed):
class TestFoo:
    @pytest.mark.asyncio
    async def test_a(self): ...
    def test_b(self): ...  # sync method — no warning
    @pytest.mark.asyncio
    async def test_c(self): ...
```

**Verify per file** (paste literal output into CHANGELOG per Rule 19):

```powershell
# Test each file individually — all tests still pass
python -m pytest tests/test_web_server.py -q --tb=short
python -m pytest tests/test_adapter_fallback.py -q --tb=short
python -m pytest tests/test_model_evaluator.py -q --tb=short
python -m pytest tests/test_verbosity.py -q --tb=short

# Verify PytestWarning count for these files is now zero
python -m pytest tests/test_web_server.py tests/test_adapter_fallback.py tests/test_model_evaluator.py tests/test_verbosity.py -q --tb=no 2>&1 | Select-String "PytestWarning: The test"
```

Last command must return **zero matches**.

**Expected warning count change**: ~17 PytestWarnings eliminated (per-file counts may vary slightly; verify at Step 2). New total: 26 → ~9 warnings.

### Step 3 — Hunt the real `\J` escape source

**The `<unknown>:1` source identifier is unusual** — it means Python is parsing a string from somewhere other than a direct `.py` source line. Track it down properly.

**Search commands** (run all three, paste output into CHANGELOG):

```powershell
# Search 1: All .py files containing \J in string literals or docstrings
Get-ChildItem -Path C:\Jarvis -Filter "*.py" -Recurse -File -Exclude "*.pyc" |
  Where-Object { $_.FullName -notmatch "\\.venv\\|\\__pycache__\\" } |
  ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match '\\J') {
      Write-Host "FOUND: $($_.FullName)"
      $matches = [regex]::Matches($content, '\\J[^\r\n]*')
      $matches | ForEach-Object { Write-Host "  Line: $($_.Value)" }
    }
  }

# Search 2: Config files (.cfg, .ini, .toml, .yaml, .yml)
Get-ChildItem -Path C:\Jarvis -Include "*.cfg","*.ini","*.toml","*.yaml","*.yml" -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch "\\.venv\\|\\__pycache__\\" } |
  ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match '\\J') {
      Write-Host "CONFIG: $($_.FullName)"
      $matches = [regex]::Matches($content, '\\J[^\r\n]*')
      $matches | ForEach-Object { Write-Host "  Line: $($_.Value)" }
    }
  }

# Search 3: pytest config + setup files specifically
@("pytest.ini", "setup.cfg", "pyproject.toml", "tox.ini", "conftest.py") | ForEach-Object {
  $path = "C:\Jarvis\$_"
  if (Test-Path $path) {
    $content = Get-Content $path -Raw
    if ($content -match '\\J') {
      Write-Host "ROOT CONFIG: $path"
      $matches = [regex]::Matches($content, '\\J[^\r\n]*')
      $matches | ForEach-Object { Write-Host "  Line: $($_.Value)" }
    }
  }
}

# Search 4: conftest.py files at any depth
Get-ChildItem -Path C:\Jarvis -Filter "conftest.py" -Recurse -File -ErrorAction SilentlyContinue |
  ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match '\\J') {
      Write-Host "CONFTEST: $($_.FullName)"
      $matches = [regex]::Matches($content, '\\J[^\r\n]*')
      $matches | ForEach-Object { Write-Host "  Line: $($_.Value)" }
    }
  }

# Search 5: Markdown files (sometimes parsed by sphinx/doctest)
Get-ChildItem -Path C:\Jarvis -Filter "*.md" -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch "\\.venv\\|\\node_modules\\" } |
  ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match '```python.*?\\J') {
      Write-Host "MARKDOWN: $($_.FullName)"
    }
  }
```

**Based on search results:**

- If a `.py` file is found: add `r""` prefix to the offending string literal (same fix as Plan 38 Step 4)
- If a config file is found: change `\J` to `/` or `\\` in the config
- If a `conftest.py` is found: fix the docstring or string literal
- If no source is found: the warning may genuinely be from `pyvenv.cfg` or another environment file. In that case, **add a `filterwarnings` entry to `pyproject.toml` or `pytest.ini`** that ignores the specific warning with a comment referencing Plan 38.5:
  ```toml
  [tool.pytest.ini_options]
  filterwarnings = [
    # Plan 38.5: <unknown>:1 invalid escape sequence '\J' — source not locatable in repo;
    # likely from pyvenv.cfg or environment. Suppress with ticket reference.
    "ignore:invalid escape sequence:DeprecationWarning",
  ]
  ```
  This is a **legitimate suppression with a ticket reference**, not silent noise.

**Verify** (paste literal output into CHANGELOG):

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "invalid escape sequence"
```

Must return **zero matches**.

**Expected warning count change**: 1 warning eliminated (or suppressed with Plan-38.5 reference). New total: 9 → 8 warnings.

### Step 4 — Fix remaining 4 cat 2 warnings (subprocess transport cleanup)

**READ FIRST**: Prompt-38 CHANGELOG line 7116 and 7124 (quoted in section C above). Plan 38 Step 6 already established that:
1. The warnings are from `asyncio.create_subprocess_exec()`, NOT from `httpx.AsyncClient` mocks
2. Source files are `tests/skills/test_docker_skill.py` and `tests/skills/test_web_scraper.py`
3. The remaining 4 warnings are a pytest-asyncio/Windows interaction, not a code bug

**Do NOT repeat Plan 38 Step 6's failed approach.** Plan 38 Step 6 tried to fix this by improving `httpx.AsyncClient` mock patterns — that didn't work because the actual source is subprocess transports. This step tries a different approach: explicit subprocess cleanup at fixture teardown.

**Step 4a — Verify the source is still subprocess transports** (paste literal output into CHANGELOG):

```powershell
# Confirm prompt-38's finding still holds — these tests should still trigger the warnings
python -m pytest tests/skills/test_docker_skill.py tests/skills/test_web_scraper.py -v --tb=no -W default 2>&1 | Select-String "PytestUnraisableException|unclosed transport|create_subprocess"
```

If output shows subprocess-transport warnings, proceed to Step 4b. If output shows something different (e.g., httpx warnings), STOP — the warning source has changed since prompt-38 and the rest of this step needs re-evaluation.

**Step 4b — Add explicit subprocess cleanup fixture to both files**:

Add this fixture (autouse=True) to `tests/skills/test_docker_skill.py` and `tests/skills/test_web_scraper.py`:

```python
import asyncio
import gc

@pytest.fixture(autouse=True)
def cleanup_subprocess_transports():
    """Force-close any lingering subprocess transports after each test.
    
    Workaround for pytest-asyncio/Windows interaction where event loop closes
    before subprocess transports (asyncio.create_subprocess_exec) are cleaned up.
    Per Plan 38.5 Step 4 — not a code bug, a test-fixture cleanup gap.
    """
    yield
    # Force garbage collection to trigger transport cleanup
    gc.collect()
    # Close any remaining event loops
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            # Run pending tasks to allow transports to close
            loop.run_until_complete(asyncio.sleep(0.1))
    except RuntimeError:
        # Event loop already closed — nothing to do
        pass
```

**Step 4c — Alternative: `filterwarnings` suppression with ticket reference**

If Step 4b doesn't eliminate all 4 warnings (this is a pytest-asyncio/Windows interaction, not a guaranteed fix), apply a targeted `filterwarnings` suppression in `pyproject.toml` (or `pytest.ini`):

```toml
[tool.pytest.ini_options]
filterwarnings = [
    # Plan 38.5 Step 4c: subprocess transport cleanup warnings on Windows.
    # Source: tests/skills/test_docker_skill.py and tests/skills/test_web_scraper.py
    # use asyncio.create_subprocess_exec; pytest-asyncio event loop closes before
    # subprocess transports clean up. Per prompt-38 CHANGELOG line 7124, this is a
    # pytest-asyncio/Windows interaction, not a code bug. Suppression is the
    # accepted workaround pending upstream pytest-asyncio fix.
    "ignore::pytest.PytestUnraisableExceptionWarning",
    "ignore:unclosed transport:ResourceWarning",
]
```

This is a **legitimate suppression with ticket reference and root-cause documentation** — not silent noise. The comment explains the source, the alternative explored (Step 4b), and why suppression is the accepted workaround.

**Verify per file** (paste literal output into CHANGELOG):

```powershell
# Test the affected files still pass
python -m pytest tests/skills/test_docker_skill.py tests/skills/test_web_scraper.py -v --tb=short

# Verify cat 2 warnings eliminated (or suppressed with ticket reference)
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "PytestUnraisableException|unclosed transport"
```

Last command must return **zero matches** (either genuinely fixed by Step 4b, or suppressed by Step 4c's `filterwarnings` with the Plan-38.5 comment).

**Expected warning count change**: 4 cat 2 warnings eliminated or suppressed. New total: 8 → 4 warnings.

### Step 5 — Gemini SDK migration (deferred from Plan 38 Step 7)

**File**: `adapters/gemini.py`

**Reference**: https://ai.google.dev/gemini-api/docs/sdks

**Key API changes** (from Plan 38 Step 7, expanded):
- `import google.generativeai as genai` → `from google import genai`
- `genai.configure(api_key=...)` → `client = genai.Client(api_key=...)` (client must be held as instance state, not module-level)
- `genai.GenerativeModel(...)` → `client.models.generate_content(...)` (different call shape — model is a parameter, not a class)
- `genai.types.GenerationConfig(...)` → `genai.types.GenerateContentConfig(...)`
- **Async pattern**: if the adapter uses `await` for generation (likely, given the codebase is async-first), the new SDK exposes async via `client.aio.models.generate_content(...)` — NOT `client.models.generate_content(...)`
- **Streaming**: if the adapter uses `generate_content(..., stream=True)`, the new SDK has a different streaming iterator shape — verify the consumer code handles the new shape
- **`genai.types` namespace**: significantly restructured; any other type imports from `genai.types` need to be checked individually

**Line-count guard — STOP condition for THIS step specifically**: After making the changes, run:

```powershell
git diff --stat adapters/gemini.py
```

If the production-code diff (excluding comments and blank lines) exceeds **20 lines changed**, STOP. The migration is larger than in-scope for this plan — defer to Plan 38.7. Apply the deferral as follows:

1. Revert the partial migration: `git checkout adapters/gemini.py`
2. Add an inline suppression with a ticket reference at the import line:
   ```python
   import google.generativeai as genai  # noqa: Plan 38.7: migrate to google.genai
   ```
   (Use `# noqa` with a Plan-N reference — legitimate temporary suppression. Warning is hidden but ticket is visible and auditable. NOT silent noise.)
3. Add "Plan 38.7 — Gemini SDK migration" to the plan queue in `SOVEREIGN_AI_HANDOFF.md`'s deferred-actions list.
4. Document in CHANGELOG: "Step 5 deferred to Plan 38.7 — migration diff exceeded 20-line guard. Inline `# noqa: Plan 38.7` suppression added with ticket reference."
5. Adjust this plan's Gate 3 expected warning count: 1 warning NOT eliminated (suppressed, not fixed).

**Verify (if migration proceeded in-scope)**:

```powershell
# Test still skips gracefully (no API key) OR passes (if API key set)
python -m pytest tests/test_gemini_adapter.py -v --tb=short

# Verify warning eliminated
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "google.generativeai|gemini.py:12"
```

Last command must return **zero matches**.

**Expected warning count change**: 1 warning eliminated (if migrated) OR 1 warning suppressed with Plan-38.7 reference (if deferred). New total: 4 → 3 warnings (if migrated) or 4 → 4 warnings (if deferred, but 1 is now auditable suppression not noise).

### Step 6 — Update handoff + CHANGELOG

**File**: `SOVEREIGN_AI_HANDOFF.md`

**Changes**:
1. Update "Last updated" line to reference prompt-38.5
2. Update test baseline to the Gate 8 final count (expected: ~3 warnings if Gemini migrated, ~4 if deferred)
3. Update "What works right now" prose count if it references a specific warning count
4. Add note in "Recently fixed" section about Plan 38.5's warning fixes
5. If Step 5 deferred Gemini: add "Plan 38.7 — Gemini SDK migration" to deferred-actions list

**File**: `CHANGELOG.md`

Append (per Rule 16 append-only):
- Step 1 baseline evidence (literal pytest output)
- Step 2 evidence (per-file pytest output + zero-match PytestWarning verification)
- Step 3 evidence (search command outputs + fix applied + zero-match escape-sequence verification)
- Step 4 evidence (per-file pytest output + zero-match cat 2 verification)
- Step 5 evidence (either migration diff stat + pytest output, OR deferral documentation with `# noqa` evidence)
- Final test counts (baseline 26 warnings → final ~3-4 warnings)

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-38..HEAD -- tests/ adapters/gemini.py system/NEWFILE_TEMPLATE.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
```

**Expected**: For `tests/`, `adapters/gemini.py`, `system/NEWFILE_TEMPLATE.py` — empty output (no drift since prompt-38).

**Allowed (not a STOP condition)**: Non-empty output for `SOVEREIGN_AI_HANDOFF.md` and `CHANGELOG.md` ONLY. The closing-step template tags the code commit (`git tag prompt-NN`) BEFORE the docs commit (`docs: prompt-NN changelog and handoff update`), so the version of these two files at the prompt-38 tag is the pre-docs-update version. Any non-empty diff for these two files should be reviewed to confirm it's the standard docs-commit content ("Last updated" line, test baseline update, plan queue update) — not unrelated drift. If the diff contains unrelated content (new sections, modified historical entries, file changes outside the standard docs pattern), STOP.

**Review procedure for non-empty HANDOFF/CHANGELOG diff**:
```powershell
git diff prompt-38..HEAD -- SOVEREIGN_AI_HANDOFF.md | Select-String "^[+-]" | Select-String -NotMatch "^[+-]{3}"
git diff prompt-38..HEAD -- CHANGELOG.md | Select-String "^[+-]" | Select-String -NotMatch "^[+-]{3}" | Select-Object -First 30
```

The HANDOFF diff should show only `Last updated`, test baseline, and similar metadata line changes. The CHANGELOG diff should show only appended prompt-38.5 entries (lines starting with `+`, no lines starting with `-` except line-ending normalization). Any `-` content lines (real deletions from history) — STOP, that's an edit, not an append (Rule 16 violation).

### Gate 2 — Step 1 baseline evidence in CHANGELOG

```powershell
Select-String -Path CHANGELOG.md -Pattern "Step 1 — Baseline evidence"
```

**Expected**: 1 match.

### Gate 3 — Warning count reduced to ≤4

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 1
```

**Expected**: line contains `XX warnings` where XX ≤ 4.

**Acceptable range**:
- 3 warnings: Gemini migrated (Plan 38.5 fully succeeded)
- 4 warnings: Gemini deferred to Plan 38.7 (1 warning suppressed with ticket, not noise)

Anything else: STOP. Investigate.

### Gate 4 — 17 PytestWarnings eliminated (Step 2)

```powershell
# Use the proven grep string from Plan 38 Step 3 (verified to work against this codebase)
python -m pytest tests/test_web_server.py tests/test_adapter_fallback.py tests/test_model_evaluator.py tests/test_verbosity.py -q --tb=no 2>&1 | Select-String "marked with @pytest.mark.asyncio but not async"
```

**Expected**: zero matches.

**Fallback grep** (if the above doesn't match because the warning category has shifted):
```powershell
python -m pytest tests/test_web_server.py tests/test_adapter_fallback.py tests/test_model_evaluator.py tests/test_verbosity.py -q --tb=no -W default 2>&1 | Select-String "PytestWarning"
```

**Expected**: zero matches.

**Note on grep string choice**: Plan 38 Step 3 used `"marked with @pytest.mark.asyncio but not async"` and verified it works. Plan 38.5 originally specified `"PytestWarning: The test"` as the grep string but that exact phrase hasn't been verified against this codebase's warning output. Use the proven Plan 38 string first; fall back to broader `"PytestWarning"` only if the first returns nothing (which would itself be a positive signal).

### Gate 5 — `\J` escape warning eliminated or suppressed with ticket (Step 3)

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "invalid escape sequence"
```

**Expected**: zero matches (either genuinely fixed or suppressed via `filterwarnings` with Plan-38.5 comment).

### Gate 6 — Cat 2 warnings eliminated (Step 4)

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "PytestUnraisableException|unclosed transport"
```

**Expected**: zero matches.

### Gate 7 — Gemini migration (Step 5)

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "google.generativeai|gemini.py:12"
```

**Expected**: zero matches (either migrated, or suppressed with `# noqa: Plan 38.7` inline).

### Gate 8 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short
```

**Expected**:
- Passed: 1080 (same as prompt-38 — no test count change)
- Skipped: 29 (same as prompt-38 — all legitimate)
- Failed: 1 (pre-existing flaky `test_lm_studio_adapter.py::test_health_check_without_server`)
- Warnings: ≤4 (down from 26)

**Acceptable ranges**:
- Passed: {1080} (no variation expected)
- Skipped: {29} (no variation expected)
- Warnings: {3, 4}

Anything outside: STOP. Investigate.

## STOP conditions

- **If Step 1 baseline is not 1080/29/1/26** — drift since prompt-38. Investigate.
- **If Step 2 (4 missed files) cannot remove all 17 PytestWarnings** — investigate which test methods still have the issue. May need to check for class-level `pytestmark` (not just module-level).
- **If Step 3 (`\J` hunt) cannot locate the source after all 5 searches** — apply the `filterwarnings` suppression with Plan-38.5 comment. This is the legitimate fallback.
- **If Step 4 (cat 2) cannot eliminate all 4 remaining warnings** — apply Step 4c's `filterwarnings` suppression with Plan-38.5 comment. Per prompt-38 CHANGELOG line 7124, this is a pytest-asyncio/Windows interaction, not a code bug — suppression with documented root cause is the accepted workaround. Do NOT attempt to fix via httpx.AsyncClient mock changes (Plan 38 Step 6 already disproved that hypothesis).
- **If Step 5 (Gemini migration) production-code diff exceeds 20 lines** — defer to Plan 38.7 per the procedure described in Step 5.
- **If Gate 8 shows >4 warnings or test count changed** — investigate which Step didn't achieve its expected reduction.
- **If any file outside the in-scope list needs editing** — STOP. Report which file and why.

## Out of scope

- **Plan 38.6** — Manual TUI verification for prompt-37.6.1 Gates 5/6 (separate plan, parallel to this one)
- **Plan 38.7** — Only created if Step 5 defers Gemini migration. Otherwise does not exist.
- **Broad-except audit** — Plan 39+
- **ruff triage** — Plan 43
- **mypy triage** — Plan 44
- **trajectory_exporter redesign** — Plan 45

## Closing steps

**Execute these in order. Do not mark a step done until it's actually done.**

1. `git add` the in-scope files: modified test files, `adapters/gemini.py` (if migrated) or `pyproject.toml`/`pytest.ini` (if `filterwarnings` suppression added), `SOVEREIGN_AI_HANDOFF.md`, `CHANGELOG.md`
2. `git commit -m "fix: prompt-38.5 — finish warnings cleanup (missed PytestWarning files, \\J hunt, cat 2 remainder, Gemini migration)"`
   - **Conditional — Step 5 deferred?** If Step 5 deferred Gemini migration to Plan 38.7, amend the commit message to: `"fix: prompt-38.5 — finish warnings cleanup (missed PytestWarning files, \\J hunt, cat 2 remainder, Gemini migration deferred to Plan 38.7) [partial: gemini-migration-pending]"`
3. `git tag prompt-38.5`
4. `git show prompt-38.5 --stat` — verify file list
5. **Post-tag verification**: `git rev-parse prompt-38.5` — confirm hash matches the commit
6. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: per-file detail with line counts
   - **Implementation Notes**: which warnings were fixed, which were suppressed with ticket references, what the `\J` source actually was
   - **Testing Results**: baseline (26 warnings from 38) → final (≤4 warnings)
   - **Verification Gate Output**: literal output of each gate
   - **Deferred actions** (if Step 5 deferred): note Plan 38.7 is queued for Gemini migration
7. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" line to reference prompt-38.5
   - Update test baseline to Gate 8 final count
   - Update warning count in "What works right now" if mentioned
   - If Step 5 deferred: add "Plan 38.7 — Gemini SDK migration" to deferred-actions list
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-38.5 changelog and handoff update"`
10. `git push origin master && git push origin prompt-38.5`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-38.5` — verify the tag exists on the remote. **Do not skip this step.** (This is the gate that was missed in prompt-38 — verify it actually runs.)

## After Plan 38.5 lands

Warning count is now ≤4 (down from 63 at start of Plan 38, down from 26 at start of Plan 38.5). Test suite is clean enough that new warnings will stand out immediately in code review.

The horizontal cleanup queue can now proceed:

- **Plan 38.6** — Manual TUI verification for prompt-37.6.1 Gates 5/6 (Rule 19 remediation, parallel to this plan)
- **Plan 38.7** (only if Step 5 deferred Gemini migration) — google.generativeai → google.genai SDK migration
- **Plan 39** — Broad-except audit, part 2 (system/) — Plan 38.5 (was Plan 38.5 in old numbering) was broad-except core/, but that was renumbered. Verify handoff's plan queue before starting.
- **Plan 40** — Broad-except audit, part 3 (skills/)
- **Plan 41** — InputSanitiser wiring
- **Plan 42** — InputSanitiser redesign
- **Plan 43** — ruff triage
- **Plan 44** — mypy triage
- **Plan 45+** — graphify integration cluster, proper MemoryBackend.delete(), trajectory_exporter functional redesign (will eliminate the 6 remaining trajectory_exporter skips)

Plans 39+ can land in any order. The warnings cleanup is done (or formally deferred with tickets).
