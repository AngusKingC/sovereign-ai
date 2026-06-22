# Plan 48: Fix B608 SQL injection in postgres backend, suppress false-positive B104 binds, and add bandit + pip-audit + vulture to CI

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise. Update the
> status row in `plans/README.md` when done.
>
> Drift check (run first):
> `git diff --stat prompt-47..HEAD -- memory/postgres.py cli/serve.py web/reference.py .github/workflows/ci.yml requirements.txt`
> Also run (read-only drift on files Plan 44/45/46/47 touched):
> `git diff --stat prompt-47..HEAD -- core/input_sanitiser.py system/trajectory_exporter.py core/memory_router.py cli/command_history.py core/session.py core/schemas.py core/approval_gate.py workers/echo_worker.py web/server.py web/middleware/auth_middleware.py gateways/telegram/gateway.py adapters/gemini.py gateways/__init__.py`
> If any in-scope file changed since prompt-47, compare Current state
> excerpts against live code; on mismatch, STOP. If `cli/serve.py`
> changed, confirm the `input_sanitiser` kwarg is still passed to
> `Orchestrator(...)` — if not, STOP (Plan 44 wiring was reverted). If
> `web/server.py` or `web/middleware/auth_middleware.py` changed,
> confirm Plan 47's E402 fix (logger after imports) is intact — if
> not, STOP. If `gateways/__init__.py` was deleted, STOP (Plan 47 was
> reverted).

## Status
- Priority: P1
- Effort: M
- Risk: MED
- Depends on: prompt-47 (E402 + missing `gateways/__init__.py` + flagged unused imports complete)
- Planned at: commit prompt-47 (c74d42a), 2026-06-20
- Revision: REV1 (2026-06-20) — initial draft based on 2026-06-20 full repo scan. Originally drafted as Plan 52 but renumbered to Plan 48 per execution-order convention (security issues take priority over the original Plan 48 ApprovalGate scope, which is now Plan 49).
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 review findings 1-3 (CI YAML missing `--exclude tests/`; `# nosec B608` made unconditional in Step 1.1; Step 5.1/C4 arithmetic corrected 24→22).
- Revision: REV3 (2026-06-20) — incorporates S2/S3 STOP fire. Original scan ran on Linux with partial requirements.txt install (scan env timed out on full install), so pip-audit baseline of 6 CVEs was wrong — Devin's Windows env with full deps shows 55 CVEs across 14 packages. Fix: stop hardcoding baseline counts; CAPTURE actual count at plan-start (Step 0.4/0.5/0.6) and verify no regression at plan-end (Step 5.1/C4). Bandit baseline command also updated with stdout fallback if JSON output fails. Step 3 scope expanded from "diskcache only" to "document all CVE-bearing packages, defer fixes to Plan 56".
- Revision: REV4 (2026-06-20) — incorporates second S2 STOP fire. Devin's Windows env reported 820 medium+ findings vs the expected 26. Root cause: `bandit -r .` scans `.venv/`/`venv/`/`env/` directories (thousands of third-party Python files with their own security findings). Original scan ran on a clean clone with no in-repo venv, so it didn't hit this. Fix: add `--exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache` to ALL bandit commands in the plan (Step 0.4, Step 1.1 verification, Step 2.3 verification, Step 4.1 CI YAML, Step 4.3, Step 5.1, Gate 1, C4). Also add a `.bandit` config file as a more permanent solution. This is a methodology fix — bandit must NEVER scan virtual env directories.
- Revision: REV5 (2026-06-20) — incorporates Claude round-4 review findings 1-2. Finding 1: Step 0.4 sanity-check grep pattern `\.venv\\|venv\\|env\\` was too broad (matched `environment/`, `envs/`, any path containing "env"). Tightened to `site-packages` which unambiguously indicates venv scanning. Finding 2: exclude list missing `.tox`, `.eggs`, `.pytest_cache` — `.tox` would reproduce the 820-finding problem if the project uses tox. Expanded exclude list to `.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache` in all 6 bandit `-r .` command locations.

## Why this matters

The 2026-06-20 full repo scan (the first scan to run bandit + pip-audit + vulture) found 3 categories of issues that ruff + mypy do not catch:

1. **2× B608 SQL injection** in `memory/postgres.py:121, 237`. Both use f-strings to interpolate `{self.table_name}` into SQL queries. While the actual values ($1, $2, $3) are correctly parameterized, the table name itself is interpolated. `self.table_name` comes from constructor arg `table_name: str = "memory_entries"` (line 32) — currently only Sovereign itself sets it, but if a future feature exposes it to user input (e.g., multi-tenant memory), this becomes a real injection vector. The fix is to validate `table_name` against a strict whitelist (alphanumeric + underscore only) at construction time.

2. **2× B104 hardcoded bind to 0.0.0.0** — `cli/serve.py:16` and `web/reference.py:209`. **Both are FALSE POSITIVES**: `cli/serve.py:16` is the default of a `--host` typer Option (user can override via CLI flag); `web/reference.py:209` is a `__main__` block in a reference/demo file. The correct fix is `# nosec B104` with a rationale comment, NOT a code change.

3. **6 dependency CVEs** — diskcache 5.6.3 (CVE-2025-69872, no fix available) + 5× pip 25.0.1 (fix: upgrade to 26.1.2). The pip CVEs are environmental (venv-only); diskcache needs investigation.

Additionally, the scan found that **the existing CI workflow (`.github/workflows/ci.yml`) only runs ruff + mypy + pytest**. Bandit, pip-audit, and vulture are not in CI — meaning these issues will recur. Plan 48 adds all 3 to CI as separate jobs so they run on every push/PR.

**Why P1**: SQL injection is the highest-severity finding in the scan. Even though the current code path doesn't expose `table_name` to user input, the pattern is wrong and should be fixed before any future feature reuses it. Adding bandit to CI prevents the next SQL injection from being merged.

## Current state

**Files in scope (Plan 48 may edit only these — 4 editable + 1 CI file):**
- `memory/postgres.py` — B608 SQL injection at lines 121 (SELECT) and 237 (INSERT). Also has 4 other f-string SQL interpolations for `table_name` at lines 54, 65, 66 (CREATE TABLE/INDEX) — those are DDL, not DML, and bandit doesn't flag them, but the same validation should apply.
- `cli/serve.py` — B104 false positive at line 16. Suppression only (no code change). Plan 44 added `input_sanitiser` kwarg here; Plan 46 prefixed 4 unused vars with `_`; verify both intact.
- `web/reference.py` — B104 false positive at line 209. Suppression only.
- `.github/workflows/ci.yml` — existing CI runs ruff + mypy + pytest. Add 3 new jobs: bandit, pip-audit, vulture.
- `requirements.txt` — investigate diskcache usage; if unused, remove. If used, document CVE-2025-69872 deferral.

**Step 0 — verify current state (do this before any edits; paste all output to CHANGELOG entry "Step 0"):**

0.1. `git rev-parse HEAD` — capture commit SHA at plan-start. Expected: `c74d42a` (prompt-47) or a descendant. Paste to CHANGELOG.

0.2. `git ls-remote --tags origin | findstr prompt-47` — confirm prompt-47 tag is on origin. If absent, STOP (prior prompt's tag-push gate was skipped per landmine L5).

0.3. `pip install bandit pip-audit vulture` — ensure all 3 tools are installed. Paste install output tail to CHANGELOG.

0.4. `bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache -f json -o bandit/bandit-baseline.json` — capture baseline. **REV4/REV5**: the `--exclude` flag is MANDATORY — without it, bandit scans `.venv/`/`venv/`/`.tox/` directories and reports hundreds of findings from third-party code (Devin's first REV3 execution got 820 findings vs the expected 26 because of this). The excluded paths are (REV5 expanded): `.venv`, `venv`, `env` (virtual env directories); `.git` (git internals); `node_modules` (JS deps, if any); `__pycache__` (Python bytecode cache); `build`, `dist` (build artifacts); `.tox` (tox environments — same problem as `.venv`); `.eggs` (setuptools egg directory); `.pytest_cache` (pytest cache, no `.py` files but noise). **If the JSON file is empty or the command fails** (S2 STOP fire root cause on first execution), fall back to: `bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache` (stdout only, no JSON) and count the `>> Issue:` lines manually. Paste the FULL stdout output to CHANGELOG. **Do NOT hardcode an expected count** — capture the ACTUAL count at plan-start and use it as the baseline. With the `--exclude` flag, the baseline should be ~26 medium+ findings (22 B108 in tests + 2 B608 in memory/postgres.py + 2 B104 in cli/serve.py and web/reference.py). If the actual count differs from 26, that's OK — PASTE THE ACTUAL COUNT and use it as the baseline. STOP S2 now fires only if the count can't be captured at all (both JSON and stdout fail), OR if the B608/B104 findings are missing (those are the in-scope fixes — if they're not present, the plan has nothing to do).

  **Bandit baseline capture procedure** (REV3, updated REV4 with `--exclude`):
  1. Run `bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache -f json -o bandit/bandit-baseline.json 2>&1 | Tee-Object -FilePath bandit/bandit-baseline.log`
  2. Check if `bandit/bandit-baseline.json` is non-empty: `if ((Get-Item bandit/bandit-baseline.json).Length -gt 0) { $baseline = (Get-Content bandit/bandit-baseline.json | ConvertFrom-Json).results.Count } else { Write-Host 'JSON empty, falling back to stdout'; $baseline = (Select-String -Path bandit/bandit-baseline.log -Pattern '>> Issue:').Count }`
  3. Paste `$baseline` (the actual count) to CHANGELOG.
  4. Also paste the per-category breakdown: `Select-String -Path bandit/bandit-baseline.log -Pattern 'Issue: \[B' | ForEach-Object { if ($_ -match '\[B(\d+)\]') { $matches[1] } } | Group-Object | Format-Table Count, Name -AutoSize`
  5. **Sanity check (REV4, tightened REV5)**: if `$baseline` is greater than 100, STOP and verify the `--exclude` flag is working. Run `bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "site-packages"` — if any output matches, the exclude isn't working (third-party packages are being scanned, which means a venv dir isn't being excluded). The `site-packages` pattern (REV5) unambiguously indicates venv scanning — the prior `\.venv\\|venv\\|env\\` pattern was too broad (matched `environment/`, `envs/`, any path containing "env"). Investigate before proceeding. The expected count with proper excludes is ~26, not 820.
  6. Verify the B608 findings in `memory/postgres.py` are present: `Select-String -Path bandit/bandit-baseline.log -Pattern 'B608.*postgres'` (expected ≥2 matches). If 0, STOP — the SQL injection that Plan 48 fixes is not present; the plan has nothing to do.
  7. Verify the B104 findings in `cli/serve.py` and `web/reference.py` are present: `Select-String -Path bandit/bandit-baseline.log -Pattern 'B104.*serve\.py|B104.*reference\.py'` (expected ≥2 matches). If 0, STOP — the false-positive binds that Plan 48 suppresses are not present.

0.5. `pip-audit` — capture baseline. **REV3**: Do NOT expect a specific count — the original scan's "6 CVEs" was wrong (scan env had partial requirements.txt). Capture the ACTUAL count at plan-start and use it as the baseline. Paste the FULL output to CHANGELOG, including the per-package breakdown. **Expected packages** (based on Devin's first execution): aiohttp, chromadb, cryptography, diskcache, idna, pillow, pygments, pypdf, pytest, python-dotenv, python-multipart, setuptools, starlette, urllib3 (14 packages, ~55 CVEs on Windows — actual count may vary by platform). STOP S3 fires only if pip-audit itself fails to run (can't capture baseline), NOT if the count differs from a hardcoded number. The captured count becomes the baseline for Gate 5 verification.

0.6. `vulture . --min-confidence 80` — capture baseline. **REV3**: If the command times out or is interrupted (S2 STOP fire root cause on first execution), run with a timeout or reduce scope: `vulture core/ adapters/ workers/ system/ cli/ memory/ skills/ web/ gateways/ --min-confidence 80`. Capture the ACTUAL count and paste to CHANGELOG. Plan 48 does NOT fix vulture findings — this baseline is for CI gate calibration only. The count should be ~47 (per scan) but may vary. STOP does NOT fire on count mismatch — only if vulture can't run at all.

0.7. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — capture baseline test count. Must match prompt-47 baseline (1167 passed, 55 skipped, 0 failed, 0 warnings). If it does not match, STOP.

0.8. `Select-String -Path memory/postgres.py -Pattern "table_name"` — paste all matches to CHANGELOG. Confirm: `self.table_name` is used in f-string SQL at lines 54, 65, 66 (DDL), 121 (SELECT), 237 (INSERT). Note the constructor at line 32 (`table_name: str = "memory_entries"`).

0.9. `Select-String -Path cli/serve.py -Pattern "input_sanitiser"` — confirm Plan 44's InputSanitiser wiring is intact. Expected: at least 1 match. If 0, STOP.

0.10. `Select-String -Path cli/serve.py -Pattern "_worker_persistence|_output_evaluator|_trace_optimiser|_worker_factory"` — confirm Plan 46's F841 fix (prefix with `_`) is intact. Expected: 4 matches. If fewer, STOP — Plan 46 was reverted.

0.11. `Get-Content memory/postgres.py | Select-Object -First 40` — paste lines 1-40 to CHANGELOG. Confirm: constructor `__init__` accepts `table_name: str = "memory_entries"` around line 32, assigns to `self.table_name` at line 37.

0.12. `Get-Content memory/postgres.py | Select-Object -Skip 115 -First 20` — paste lines 116-135 to CHANGELOG. Confirm: line 121 has `FROM {self.table_name}` in an f-string SQL SELECT.

0.13. `Get-Content memory/postgres.py | Select-Object -Skip 230 -First 20` — paste lines 231-250 to CHANGELOG. Confirm: line 237 has `INSERT INTO {self.table_name}` in an f-string SQL INSERT.

0.14. `Get-Content cli/serve.py | Select-Object -First 25` — paste lines 1-25 to CHANGELOG. Confirm: line 16 has `host: str = typer.Option("0.0.0.0", "--host", "-h", ...)` — this is a configurable default, NOT a hardcoded bind. Note for `# nosec B104` rationale.

0.15. `Get-Content web/reference.py | Select-Object -Skip 200 -First 20` — paste lines 201-220 to CHANGELOG. Confirm: line 209 has `uvicorn.run(..., host="0.0.0.0", port=8000)` inside `if __name__ == "__main__":` — this is a demo/reference file, not production code. Note for `# nosec B104` rationale.

0.16. `Get-Content .github/workflows/ci.yml` — paste full file to CHANGELOG. Confirm: 1 job (`test`) running ruff + mypy + pytest. Plan 48 will add 3 new jobs.

0.17. `Select-String -Path requirements.txt -Pattern "diskcache"` — check if diskcache is a direct dependency. If match: investigate usage with `grep -r "diskcache" --include="*.py" .` and paste output. If no match: diskcache is transitive — note for pip-audit CI calibration.

If any of these do not match the description above, STOP — the plan was written against stale state.

**Repo conventions (Architecture Rules, handoff lines 437-460):**
- `memory/` may import from `core/` only (Rule 3). `memory/postgres.py` currently imports from `core/` — verify no new violations.
- All I/O operations are async (Rule 13). Plan 48's table_name validation is sync (constructor) — OK.
- No broad `except Exception: pass` without inline comment + WARNING trace (Rule 17). Plan 48's new code must preserve this.
- All public functions have return type annotations (Rule 9).

## What to change

### Step 1 — Fix B608 SQL injection in `memory/postgres.py`

**Root cause**: `self.table_name` is interpolated via f-string into SQL at 5 locations (lines 54, 65, 66, 121, 237). Bandit flags 2 of them (the DML queries at 121 and 237). The fix is to validate `table_name` at construction time against a strict whitelist, so the interpolated value is guaranteed safe.

1.1. **Add table_name validation to `__init__`**: in `memory/postgres.py`, after `self.table_name = table_name` (line 37), add a validation check:
```python
import re
_TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")

# In __init__, after self.table_name = table_name:
if not _TABLE_NAME_PATTERN.match(self.table_name):
    raise ValueError(
        f"Invalid table_name: {self.table_name!r}. "
        "Must match ^[a-zA-Z_][a-zA-Z0-9_]{0,62}$ (SQL identifier rules)."
    )
```

This matches PostgreSQL's identifier rules (start with letter/underscore, then alphanumeric/underscore, max 63 chars). Any `table_name` not matching this pattern raises `ValueError` at construction — the f-string interpolation at lines 54/65/66/121/237 is then guaranteed safe because the value cannot contain SQL metacharacters.

**Verification**:
```
python -c "from memory.postgres import PostgresBackend; PostgresBackend(table_name='valid_name'); print('valid OK')"
```
Expected: `valid OK`. Paste literal output to CHANGELOG.
```
python -c "from memory.postgres import PostgresBackend; 
try:
    PostgresBackend(table_name='evil; DROP TABLE users; --')
    print('FAIL: should have raised')
except ValueError as e:
    print(f'OK: raised ValueError: {e}')"
```
Expected: `OK: raised ValueError: Invalid table_name...`. Paste literal output to CHANGELOG. If `FAIL: should have raised`, STOP — validation not working.

**Mandatory `# nosec B608` suppression** (Claude review Finding 2 — bandit pattern-matches f-string syntax, not runtime values, so it WILL still flag B608 even after validation; the suppression is always required alongside validation, not conditional):
- Add `# nosec B608 — table_name validated against ^[a-zA-Z_][a-zA-Z0-9_]{0,62}$ in __init__` to line 121 (SELECT) and line 237 (INSERT).
- Then run bandit to confirm 0 findings (below).

```
bandit memory/postgres.py -ll
```
Expected: 0 medium+ findings (was 2 B608 before). Paste literal output to CHANGELOG. **If bandit still shows B608 findings after the `# nosec B608` suppression**, STOP — bandit is not recognizing the suppression; investigate (S8).

1.2. **Add `import re` at top of file** if not already present. Place after existing imports.

1.3. **Broad-except compliance (Rule 17)**: if `__init__`'s validation raises `ValueError`, that's a constructor failure — let it propagate, do NOT catch. No new `except Exception` blocks added.

1.4. **Verification (full file)**:
```
ruff check memory/postgres.py
```
Expected: 0 errors. Paste literal output to CHANGELOG.
```
mypy memory/postgres.py --ignore-missing-imports
```
Expected: 0 NEW errors (pre-existing errors unchanged — enumerate if any). Paste literal output to CHANGELOG.
```
python -m pytest tests/test_postgres_backend.py -v
```
Expected: all tests pass. Paste `Select-Object -Last 5` to CHANGELOG. **If a test uses an invalid `table_name` and now fails on the validation**, the test was wrong — update it to use a valid name OR update the test to expect `ValueError`. Do NOT skip the test (landmine L3).

### Step 2 — Suppress B104 false positives in `cli/serve.py` and `web/reference.py`

2.1. **`cli/serve.py:16`**: add `# nosec B104` with rationale. The line currently reads:
```python
host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
```
Change to:
```python
host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),  # nosec B104 — configurable default, user can override via --host
```

2.2. **`web/reference.py:209`**: add `# nosec B104` with rationale. The line currently reads:
```python
uvicorn.run(web_gui.get_app(), host="0.0.0.0", port=8000)
```
Change to:
```python
uvicorn.run(web_gui.get_app(), host="0.0.0.0", port=8000)  # nosec B104 — reference/demo file, not production code
```

2.3. **Verification**:
```
bandit cli/serve.py web/reference.py -ll
```
Expected: 0 medium+ findings (was 2 B104 before). Paste literal output to CHANGELOG.
```
Select-String -Path cli/serve.py -Pattern "input_sanitiser"
```
Expected: at least 1 match (Plan 44 wiring intact). Paste literal output. If 0, STOP — Step 2.1 inadvertently reverted Plan 44 wiring.
```
Select-String -Path cli/serve.py -Pattern "_worker_persistence|_output_evaluator|_trace_optimiser|_worker_factory"
```
Expected: 4 matches (Plan 46 F841 fix intact). Paste literal output. If fewer, STOP.

### Step 3 — Document all CVE-bearing packages (REV3: expanded from diskcache-only)

**REV3 scope change**: the original Plan 48 Step 3 only investigated diskcache. The S3 STOP fire revealed 55 CVEs across 14 packages (aiohttp, chromadb, cryptography, diskcache, idna, pillow, pygments, pypdf, pytest, python-dotenv, python-multipart, setuptools, starlette, urllib3). Plan 48 does NOT fix any of these CVEs — that's Plan 56's job. Plan 48 only DOCUMENTS them so Plan 56 has a complete worklist.

3.1. From Step 0.5's pip-audit output, compile the full list of CVE-bearing packages. Paste the list to CHANGELOG in this format:
  ```
  Package | Version | CVE IDs | Fix Versions
  --------|---------|---------|------------
  aiohttp | <ver> | <CVEs> | <fix>
  ...
  ```

3.2. For each package, determine if it's a direct dependency (in `requirements.txt`) or transitive. `pip show <package>` will show which package depends on it. Paste the direct-vs-transitive classification to CHANGELOG.

3.3. **Do NOT fix any CVEs in Plan 48**. All fixes are deferred to Plan 56 (dependency updates + diskcache migration). Plan 48's job is documentation only — so Plan 56 has a complete worklist and the CI pip-audit job (Step 4) has a known baseline to track against.

3.4. **diskcache-specific note**: if diskcache is directly used (check `grep -r "diskcache" --include="*.py" .`), document the usage location in CHANGELOG. Plan 56 will either replace diskcache or wait for an upstream fix for CVE-2025-69872 (no fix available as of 2026-06-20).

3.5. **Verification**:
```
pip-audit
```
Expected: SAME count as Step 0.5's baseline (Plan 48 doesn't fix CVEs). Paste literal output to CHANGELOG. If the count INCREASED, STOP — a new CVE was disclosed during Plan 48 execution; document it. If the count DECREASED, that's unexpected (Plan 48 didn't fix anything) — investigate (maybe a package was auto-upgraded).

### Step 4 — Add bandit + pip-audit + vulture to CI

4.1. **Edit `.github/workflows/ci.yml`** — add 3 new jobs after the existing `test` job:

```yaml
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install bandit
        run: pip install bandit
      - name: Run bandit (medium+ severity)
        run: bandit -r . -ll --exclude tests/,.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache
        # B108 findings in tests/ are deferred to Plan 53 — exclude tests/ for now
        # Remove the --exclude tests/ when Plan 53 fixes B108
        continue-on-error: false

  dependency-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install pip-audit
        run: pip install pip-audit
      - name: Install project deps
        run: pip install -r requirements.txt
      - name: Run pip-audit
        run: pip-audit --strict
        # Will fail until diskcache CVE is fixed and pip is upgraded in CI image
        continue-on-error: true  # TODO: change to false after Plan 56 (deps) lands

  dead-code:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install vulture
        run: pip install vulture
      - name: Run vulture (min-confidence 80)
        run: vulture . --min-confidence 80
        # Will fail — 47 findings exist. TODO: change to fail-build after Plan 57 (dead code cleanup) lands
        continue-on-error: true
```

**Design decisions**:
- `security` job runs bandit at medium+ severity. **Fails build on new findings.** Excludes `tests/` directory (B108 findings in tests are deferred to Plan 53 — `bandit -r . -ll --exclude tests/,.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache`). Wait — actually the existing `bandit -r . -ll` includes tests and finds 22 B108 in tests. Either (a) exclude tests/ in the CI command, or (b) fix B108 in Plan 53 first. Plan 48 uses option (a): `bandit -r . -ll --exclude tests/,.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache` so the security job passes immediately. Plan 53 will fix B108, then a follow-up removes the `--exclude tests/`.
- `dependency-audit` job runs pip-audit. **`continue-on-error: true`** because CVEs currently exist (Step 0.5 baseline count, expected ~55 across 14 packages). Plan 56 (dependency updates) will fix these, then change to `continue-on-error: false`.
- `dead-code` job runs vulture at min-confidence 80. **`continue-on-error: true`** because 47 findings exist. A future Plan 57 (dead code cleanup) will fix these, then change to `continue-on-error: false`.

4.2. **Verification**:
```
Get-Content .github/workflows/ci.yml
```
Expected: file contains 4 jobs: `test`, `security`, `dependency-audit`, `dead-code`. Paste literal output to CHANGELOG.
```
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
```
Expected: `YAML OK`. Paste literal output. If syntax error, STOP — fix before committing.

4.3. **Local dry-run of the 3 new CI jobs**:
```
bandit -r . -ll --exclude tests/,.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache
```
Expected: 0 medium+ findings (after Steps 1 and 2). Paste literal output to CHANGELOG. If findings remain, STOP — Step 1 or 2 was incomplete.
```
pip-audit
```
Expected: SAME count as Step 0.5's baseline (Plan 48 doesn't fix CVEs — REV3: actual count is ~55 CVEs across 14 packages, captured at plan-start). Paste literal output.
```
vulture . --min-confidence 80
```
Expected: SAME count as Step 0.6's baseline (Plan 48 doesn't fix dead code — REV3: actual count is ~47, captured at plan-start). Paste count to CHANGELOG.

### Step 5 — Verify no regressions

5.1. **Verification** (REV3 — uses captured baselines, not hardcoded counts):
```
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache
```
Expected: (Step 0.4 baseline count) minus 2 B608 (fixed in Step 1) minus 2 B104 (suppressed in Step 2) = (baseline - 4). The B108 in tests remain unchanged. **Paste the actual count and verify it equals (Step 0.4 baseline - 4).** If the count is not (baseline - 4), STOP — investigate (either a fix didn't work, or new findings were introduced).

```
pip-audit
```
Expected: SAME count as Step 0.5 baseline (Plan 48 doesn't fix CVEs). Paste literal output. If count increased, STOP — new CVE disclosed; document. If count decreased, investigate.

```
python -m pytest tests/ -q --tb=no | Select-Object -Last 3
```
Expected: 1167 passed, 55 skipped, 0 failed, 0 warnings (unchanged from prompt-47 baseline). Paste literal output. If a test fails due to Step 1.1's `table_name` validation, the test was using an invalid name — fix the test (don't skip). If any other test fails, STOP.

```
ruff check memory/postgres.py cli/serve.py web/reference.py
```
Expected: 0 errors. Paste literal output to CHANGELOG.

```
mypy memory/postgres.py cli/serve.py web/reference.py --ignore-missing-imports
```
Expected: 0 NEW errors introduced. Pre-existing errors unchanged. Paste literal output.

## Verification gates (run in order, all must pass)

1. `bandit -r . -ll --exclude tests/,.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache` — expected: 0 medium+ findings. Paste literal output. (Tests excluded because B108 in tests is deferred to Plan 53.)
2. `bandit memory/postgres.py -ll` — expected: 0 findings (was 2 B608). Paste literal output.
3. `bandit cli/serve.py web/reference.py -ll` — expected: 0 findings (was 2 B104). Paste literal output.
4. `python -c "from memory.postgres import PostgresBackend; PostgresBackend(table_name='valid_name'); print('valid OK')"` — expected: `valid OK`. Paste literal output.
5. `python -c "from memory.postgres import PostgresBackend; import sys; 
try:
    PostgresBackend(table_name='evil; DROP TABLE users; --')
    print('FAIL'); sys.exit(1)
except ValueError:
    print('OK: ValueError raised')"` — expected: `OK: ValueError raised`. Paste literal output.
6. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: 1167 passed, 55 skipped, 0 failed, 0 warnings. Paste literal output.
7. `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"` — expected: `YAML OK`. Paste literal output.
8. Manual smoke (any shell — landmine L11):
   ```
   python -c "from cli.serve import serve; from memory.postgres import PostgresBackend; print('Plan 44 wiring:', 'input_sanitiser' in open('cli/serve.py').read()); print('Plan 46 F841 fix:', '_worker_persistence' in open('cli/serve.py').read()); print('Plan 47 E402 fix:', open('web/server.py').read().find('logging.getLogger') > open('web/server.py').read().find('import fastapi'))"
   ```
   Expected: `Plan 44 wiring: True`, `Plan 46 F841 fix: True`, `Plan 47 E402 fix: True`. Paste literal output. If any is `False`, STOP — prior plan's work was reverted.

## STOP conditions

- **S0**: If Step 0.1 reveals `HEAD` is not a descendant of `prompt-47` tag, STOP (prompt-47 was not actually merged).
- **S1**: If Step 0.2 shows `prompt-47` tag is absent from origin, STOP (landmine L5).
- **S2**: If Step 0.4 fails to capture ANY bandit baseline (both JSON and stdout fallback fail), OR if the B608 findings in `memory/postgres.py` are not present (the SQL injection that Plan 48 fixes is gone — plan has nothing to do), OR if the B104 findings in `cli/serve.py`/`web/reference.py` are not present (the false-positive binds to suppress are gone), STOP. **REV3**: S2 does NOT fire on count mismatch — the original "26 medium+" was based on an incomplete scan env. The actual count is captured at plan-start and used as the baseline.
- **S3**: If Step 0.5 fails to run pip-audit at all (can't capture baseline), STOP. **REV3**: S3 does NOT fire on count mismatch — the original "6 CVEs" was based on a partial requirements.txt install in the scan env. The actual count (55 CVEs across 14 packages on Devin's Windows env) is captured at plan-start and used as the baseline. Plan 48 does NOT fix CVEs — it only adds pip-audit to CI with `continue-on-error: true`.
- **S4**: If Step 0.7 reveals the test baseline is NOT 1167 passed / 55 skipped / 0 failed, STOP — baseline drift.
- **S5**: If Step 0.9 reveals `cli/serve.py` has 0 matches for `input_sanitiser`, STOP — Plan 44 wiring was reverted.
- **S6**: If Step 0.10 reveals `cli/serve.py` has fewer than 4 matches for the `_worker_*` prefixed variables, STOP — Plan 46 F841 fix was reverted.
- **S7**: If Step 1.1's validation test (`PostgresBackend(table_name='evil; DROP TABLE users; --')`) does NOT raise `ValueError`, STOP — validation not working.
- **S8**: If Step 1.1's `bandit memory/postgres.py -ll` still shows B608 findings AFTER adding `# nosec B608` with rationale (mandatory per REV2 — bandit pattern-matches f-string syntax, not runtime values, so the suppression is always required alongside validation), STOP — bandit is not recognizing the suppression; investigate.
- **S9**: If Step 1.4's pytest reveals a test was using an invalid `table_name` and now fails on validation, the test was wrong — fix it (don't skip). If fixing the test requires >50 lines, STOP (S12).
- **S10**: If Step 2.3's verification reveals `cli/serve.py` has 0 matches for `input_sanitiser` OR fewer than 4 `_worker_*` matches, STOP — Step 2 reverted prior plans' work.
- **S11**: If Step 3.2 reveals diskcache IS directly used AND migration is non-trivial (>50 lines), STOP — document the CVE deferral in CHANGELOG and proceed without replacing diskcache. Do NOT silently leave the CVE unfixed without documentation.
- **S12**: If the fix requires >50 lines of new code in any single step, STOP — the plan was underscoped. File a follow-up plan.
- **S13**: If a file outside the in-scope list needs editing, STOP — out-of-scope. The 4 editable in-scope files + 1 CI file are listed in "Current state" above.
- **S14**: If Gate 6 shows MORE failures than the prompt-47 baseline (1167 passed, 55 skipped, 0 failed) — i.e., any new failure, OR skip count rises above 55 — STOP. A regression was introduced. Do not tag.
- **S15**: If any verification gate is marked PASSED without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S16**: If any closing step (C1-C10 below) is marked DONE without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S17**: If C5 (`git show prompt-48 --stat`) reveals a file outside the in-scope list (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md`), STOP — delete the tag with `git tag -d prompt-48`, unstage the out-of-scope file, and re-tag. Do not push the bad tag.
- **S18**: If C10 (`git push origin prompt-48`) succeeds locally but `git ls-remote --tags origin | findstr prompt-48` returns empty, STOP — the tag did not reach origin (landmine L5). Retry the push. If retry fails, report to user; do not mark Plan 48 complete.

## Closing steps (mandatory, every prompt)

These run AFTER all verification gates (Gates 1-8) pass. Each step requires literal output pasted to CHANGELOG (landmine L2 / Rule 19). Do not batch.

**C1** — Run full test suite:
```
python -m pytest tests/ -v
```
Confirm: zero new failures vs prompt-47 baseline (1167 passed, 55 skipped, 0 failed). Plan 48 should not change the test count. Paste `Select-Object -Last 5` literal output to CHANGELOG.

**C2** — Ruff check on all touched files:
```
ruff check memory/postgres.py cli/serve.py web/reference.py
```
Expected: 0 errors. Paste literal output to CHANGELOG.

**C3** — Mypy on all touched Python files:
```
mypy memory/postgres.py cli/serve.py web/reference.py --ignore-missing-imports
```
Expected: 0 NEW errors introduced by Plan 48. Paste literal output. Pre-existing errors must be enumerated.

**C4** — Bandit final check (REV3 — uses captured baseline):
```
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache
```
Expected: (Step 0.4 baseline count) minus 2 B608 (fixed) minus 2 B104 (suppressed) = (baseline - 4). Paste count + breakdown to CHANGELOG. Verify the count equals (Step 0.4 baseline - 4). If not, STOP — investigate. The B108 in tests remain unchanged (deferred to Plan 53).

**C5** — Commit and tag:
```
git add .
git commit -m "checkpoint: prompt-48"
git tag prompt-48
```
Verify:
```
git log -1 --oneline
git tag --list prompt-48
```
Expected: `prompt-48` appears in both outputs. Paste literal output to CHANGELOG.

**C6** — Verify file list in the tag:
```
git show prompt-48 --stat
```
Expected: file list contains ONLY these 5 files (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md` which are added in C7/C8 — they should NOT appear here because the docs commit is C9):
- `memory/postgres.py`
- `cli/serve.py`
- `web/reference.py`
- `.github/workflows/ci.yml`
- `requirements.txt` (only if Step 3.2 modified it)

If an unexpected file appears, run `git tag -d prompt-48`, `git reset HEAD~1`, clean, re-commit, re-tag. Do NOT push the bad tag. Paste literal output of `git show prompt-48 --stat` to CHANGELOG.

**C7** — Update `CHANGELOG.md` (append-only). **Per-step CHANGELOG entries required** — do not batch. Each entry must include:
- **Date/time**: `YYYY-MM-DD HH:MM` per handoff line 191.
- **Step reference**: "Plan 48 Step 0", "Plan 48 Step 1.1", etc.
- **What was done**: concrete actions.
- **What failed (if anything)**: mid-prompt failures and how resolved.
- **Files Modified**: per-file detail.
- **Testing Results**: baseline → final, with exact command.
- **Verification Gate Output**: literal output of each gate (Gates 1-8 + Closing steps C1-C4).

Use the CHANGELOG append procedure below.

**C8** — Update `SOVEREIGN_AI_HANDOFF.md`:
- Move Plan 48 from "Next 5 prompts" to "Completed prompts" table: `| 48 | Security: B608 SQL injection + B104 suppression + CI bandit/pip-audit/vulture | 1167 | <one-line result summary> |`.
- Update "Static analysis baseline" line — add: "Bandit: (Step 0.4 baseline - 4) medium+ findings (B108 in tests deferred to Plan 53; B608 + B104 fixed/suppressed by Plan 48). pip-audit: (Step 0.5 baseline count) CVEs across (Step 0.5 package count) packages (deferred to Plan 56). Vulture: (Step 0.6 baseline count) high-confidence findings (deferred to Plan 57)." **REV3**: use the ACTUAL captured counts from Step 0.4/0.5/0.6, not hardcoded numbers.
- Update "Architecture rules" section — add Rule 20: "`table_name` parameter in `memory/postgres.py` MUST be validated against `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$` at construction time. f-string interpolation of `table_name` into SQL is permitted ONLY because of this validation. Any new SQL-interpolated identifier must follow the same pattern."
- **Refill the "Next 5 prompts" queue**: Plan 49 (ApprovalGate API drift + ApprovalRequest fields, P1), Plan 50 (MockMemoryRouter inheritance, P2), Plan 51 (adapter type fixes + del e, P2), Plan 52 (F4 wiring, P2), Plan 53 (test suite health + B108, P2).
- Update the "Last updated" header to `2026-06-20 — post prompt-48, handoff amended by GLM session 10`.

**C9** — Update `global_rules.md` IF a new recurring mistake pattern or landmine was identified. Candidate for this prompt: "Security tools (bandit, pip-audit, vulture) must run in CI — ruff + mypy alone miss SQL injection patterns, dependency CVEs, and dead code." If no new pattern, skip with documented reason.

**C10** — Commit docs:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md global_rules.md
git commit -m "docs: prompt-48 changelog and handoff update"
```
If `global_rules.md` was not modified in C9, omit it. Verify with `git log -1 --oneline` and `git show HEAD --stat`. Paste literal output to CHANGELOG.

**C11** — Push to origin:
```
git push origin master
git push origin prompt-48
```
**Tag-push gate (landmine L5 — non-negotiable)**: after pushing, verify:
```
git ls-remote --tags origin | findstr prompt-48
```
Expected: a line containing `prompt-48`. If empty, retry the push. If retry fails, report to user; do NOT mark Plan 48 complete in the CHANGELOG until the tag is verified on origin. Paste literal output to CHANGELOG.

### CHANGELOG append procedure (PowerShell, because file locks)

Per handoff lines 269-273 (updated prompt-48.1). Use these exact PowerShell idioms — do not substitute.

- **Line count**: `[System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count`. NEVER use `Get-Content | Measure-Object` — it truncates large files.
- **Append method (L15 — temp-file pattern for entries >20 lines)**: write the entry to a temp file first, then append. This avoids PowerShell here-string parsing issues (`"@` must be at column 1 with zero leading whitespace; auto-indent hangs forever) AND `Add-Content` file-lock deadlocks on large CHANGELOG files.
- **Append method (for entries ≤20 lines)**: `Add-Content -Path r"C:\Jarvis\CHANGELOG.md" -Value @"..."@` is acceptable IF the closing `"@` is at column 1. The temp-file pattern is always safer — use it if in doubt.
- **NEVER paste into the editor** for entries >20 lines — file locks + auto-indent can corrupt the here-string. For entries ≤20 lines, pasting into the editor + verifying line count is an acceptable fallback if `Add-Content` fails.
- **Before appending**: record current line count with `[System.IO.File]::ReadAllLines(...).Count`.
- **After appending**: verify new count exceeds previous, verify last 5 lines with `Get-Content ... | Select-Object -Last 5`.
- **Close the file in the IDE before running `Add-Content`** — file locks will cause silent truncation.

**Standard temp-file append pattern (use for ALL entries >20 lines)**:
```powershell
# 1. Write the entry to a temp file (here-string is safe here — Out-File handles it)
$entry = @"
## 2026-06-20 HH:MM — Plan NN Step N

**What was done**: <concrete actions>

**Files Modified**:
- <file>: <changes>

**What failed**: <none / failures and resolution>

**Testing Results**: <baseline → final, with command>

**Verification Gate Output**:
``<literal output>``
"@

$entry | Out-File -FilePath C:\Jarvis\scan\changelog-entry.md -Encoding utf8

# 2. Close the IDE if CHANGELOG.md is open, then append
$before = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\changelog-entry.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md"
$after = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
Write-Host "Before: $before, After: $after"
Get-Content r"C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5

# 3. Clean up temp file
Remove-Item C:\Jarvis\scan\changelog-entry.md
```

**Critical**: the closing `"@` in step 1 MUST be at column 1 (no leading whitespace). If using VS Code, disable auto-indent for PowerShell files or paste with Ctrl+Shift+V (paste without formatting). If the here-string still hangs, write the entry to the temp file using the editor directly (not PowerShell) and skip step 1.

## Out of scope

The following are explicitly out of scope for Plan 48. Each requires its own plan. Do not bundle — bundling is scope creep (landmine L12).

- **B108 hardcoded /tmp in tests** (22 findings) — Plan 53 (test suite health). The CI bandit job uses `--exclude tests/` to defer these.
- **5 pip CVEs** — environmental (venv-only). Upgrade pip in your dev venv separately. CI uses GitHub's setup-python which provides a recent pip; the CVEs are local-dev-only.
- **diskcache CVE-2025-69872** — if Step 3.2 reveals diskcache is directly used AND migration is non-trivial, document the deferral in CHANGELOG. A future Plan 56 will replace diskcache or wait for an upstream fix.
- **47 vulture dead-code findings** — Plan 57 (dead code cleanup). The CI vulture job uses `continue-on-error: true` to defer.
- **ApprovalGate API drift** (84+28 mypy errors) — Plan 49.
- **MockMemoryRouter inheritance** (107 mypy errors) — Plan 50.
- **Adapter type fixes** (27 mypy errors) — Plan 51.
- **F4 wiring fix** — Plan 52.
- **F401 bulk cleanup** (247 remaining) — Plan 54.
- **Marine stack** — Plan 55 (deferred until after audit cleanup).
- **Dependency updates + diskcache migration** — Plan 56.
- **Dead code cleanup** (47 vulture findings) — Plan 57.
- **Any change to InputSanitiser's public API or Plan 44/45/46/47's work** — verify-only. Plan 48's drift check confirms prior plans' work is intact.

**Note on Next 5 queue refill**: When Plan 48 completes, the "Next 5 prompts" queue: Plan 49 (ApprovalGate API drift, P1), Plan 50 (MockMemoryRouter inheritance, P2), Plan 51 (adapter type fixes + del e, P2), Plan 52 (F4 wiring, P2), Plan 53 (test suite health + B108, P2). Plans 54 (F401 bulk), 55 (marine stack), 56 (dependency updates), 57 (dead code) are next-priority deferred.

## For Claude review (Devin: do not execute)

1. **Step 1.1 regex pattern sufficiency**: the validation regex is `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$`. This matches PostgreSQL's unquoted identifier rules (start with letter/underscore, then alphanumeric/underscore, max 63 chars). Is this sufficient, or should it also reject SQL reserved words (e.g., `SELECT`, `FROM`, `DROP`)? PostgreSQL allows reserved words as table names if quoted, but f-string interpolation produces unquoted identifiers — so a `table_name="SELECT"` would produce `FROM SELECT` which is a syntax error, not an injection. Acceptable risk, or add reserved-word check?

2. **Step 1.1 `# nosec B608` fallback**: the plan says "If bandit still flags B608 after validation, add `# nosec B608` with rationale." Bandit pattern-matches f-string syntax, not runtime values — so it WILL still flag B608 even with validation. The `# nosec B608` is therefore mandatory, not conditional. Should the plan just dictate `# nosec B608` upfront (with rationale comment) rather than making Devin discover this in verification?

3. **Step 4.1 CI `continue-on-error` strategy**: the `dependency-audit` and `dead-code` jobs use `continue-on-error: true` with TODO comments to change to `false` after Plan 56/57 land. Is this the right pattern, or should Plan 48 leave them as `continue-on-error: false` and let CI fail until Plan 56/57 fix the underlying issues? Tradeoff: `true` means CI passes now but the jobs are advisory; `false` means CI fails now and forces Plan 56/57 to land before any other PR can merge.

4. **Step 4.1 bandit `--exclude tests/`**: the security job excludes `tests/` to defer the 22 B108 findings to Plan 53. Is this the right call, or should Plan 48 fix the 22 B108 findings now (they're trivial — replace `tempfile.gettempdir()` with `tempfile.mkdtemp()`)? Tradeoff: fixing now makes the security job comprehensive; deferring keeps Plan 48 focused on the real security issue (SQL injection).

5. **Step 1.4 test update policy**: if a test in `tests/test_postgres_backend.py` uses an invalid `table_name` (e.g., `test-table-with-dashes` or `table; DROP`), Step 1.1's validation will break it. The plan says "fix the test (don't skip)". Is this clear enough, or should the plan specify the exact replacement pattern (e.g., "replace invalid names with `valid_test_table` or `test_table_123`")?
