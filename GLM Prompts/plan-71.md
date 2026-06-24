# Plan 71 (Rev5) — Critical Hygiene + Tooling Integration + Workflow Updates

> **Rev5 changes from Rev4**: Adds find-and-replace anchors to S14.1-S14.3 (clearer edit instructions for Devin), adds S14.5 step 4 (functional test of new workflow commands — catches typos that syntax check misses), adds trend note to Coverage baseline row in S14.4 ("should not drop >5% per module in future plans"). No scope changes — still 22 files. Addresses Claude's Rev4 issues 2, 4, 5 (issues 1 and 3 acknowledged as already resolved).

> **Rev4 changes from Rev3**: Removes AGENTS.md rule additions (OR29/OR30/OR31) — they contradicted Rev1's approved C9 ("No new AGENTS.md rules"). Tooling is now enforced by the workflow doc updates themselves (S14.1-S14.3 tell Devin when to run detect-secrets/vulture/pre-commit), not by new rules. Also adds Python 3.12 upgrade rationale (S13) and explicit test count impact analysis (S16). In-scope file count: 22 (was 23 in Rev3).

> **Rev3 changes from Rev2**: Adds workflow document updates (S14) — Devin must update `jarvis-open.md`, `jarvis-verify.md`, `jarvis-close.md`, and `PLANS.md` baseline rows so the new tooling (detect-secrets, pre-commit, vulture whitelist, coverage) is actually invoked by the standard workflows. Without these updates, the tooling files are added but never referenced — a specification gap identified during Rev2 review. Existing S14 (verification) renumbered to S15; existing S15 (baseline reconciliation) renumbered to S16.

> **Rev2 changes from Rev1**: Integrates tooling layer (detect-secrets, pre-commit, pytest-cov, CI fixes, vulture whitelist) on top of the original code-hygiene work (AR18 cleanup, datetime, API validation, dead code, AR18 compliance test). Code-hygiene sections S1-S8 are unchanged from Rev1 (Claude-approved). New sections S9-S13 add the tooling layer. S15-S16 expand verification to cover tooling.

> **Claude review of Rev1**: APPROVED. All 5 criteria PASS, all 6 risks acceptable, all 5 context-brief questions answered (confirming the proposed approach). Rev2/Rev3/Rev4/Rev5 add scope not in Rev1's review — if the user wants, Rev5 can be sent back to Claude for re-review (Rev2+ needs no context brief per handoff).

## Opening (S0)

S0.1. **Run `/jarvis-open`** — verify `prompt-70` tag on origin, confirm working copy clean and on master. If workflow missing or fails, STOP and report.

S0.2. **Read AGENTS.md in full.** No new AGENTS.md rules this prompt. Apply all existing rules (AR1-AR18, OR1-OR28). Cite rules by number per OR23.

S0.3. **Scope declaration** — Pre-declare scope per OR15. Will edit:

   **Production code (AR18 + datetime + API validation + dead code)**:
   - `system/resource_manager.py` — AR18 cleanup (~57 violations) + 6 bare `datetime.now()` fixes
   - `skills/notes/notes_skill.py` — AR18 cleanup (~55 violations)
   - `core/approval_gate.py` — AR18 cleanup (~38 violations)
   - `skills/calendar/calendar_skill.py` — AR18 cleanup (~35 violations)
   - `skills/reminder/reminder_skill.py` — AR18 cleanup (~29 violations)
   - `system/model_acquisition.py` — AR18 cleanup (~22 violations) + API key validation (lines 55, 674, 676, 678) + dead code fixes (lines 224, 350)
   - `skills/email/email_skill.py` — AR18 cleanup (~19 violations)
   - `system/model_registry.py` — AR18 cleanup (~18 violations) + 2 bare `datetime.now()` fixes
   - `system/profiler.py` — 1 bare `datetime.now()` fix
   - `cli/command_history.py` — 2 bare `datetime.now()` fixes
   - `memory/obsidian.py` — 1 bare `datetime.now()` fix

   **Tests**:
   - `tests/test_ar18_compliance.py` — NEW: AR18 regression-prevention test

   **Tooling / config (NEW in Rev2)**:
   - `.pre-commit-config.yaml` — NEW: pre-commit hooks config (ruff, detect-secrets, standard hooks)
   - `.secrets.baseline` — NEW: detect-secrets baseline (existing strings marked as OK)
   - `pytest.ini` — edit: add `--cov` config (informational, not gated)
   - `requirements-dev.txt` — NEW: dev dependencies (detect-secrets, pre-commit, pytest-cov, vulture)
   - `.github/workflows/ci.yml` — edit: Python 3.11→3.12, expand mypy scope to full repo, add detect-secrets job, add coverage job, flip vulture `continue-on-error: false` with whitelist
   - `vulture-whitelist.txt` — NEW: whitelist for 23 existing vulture findings (prevents CI failure while catching new dead code)

   **Workflow + governance docs (NEW in Rev3 — required so tooling is actually invoked)**:
   - `.windsurf/workflows/jarvis-open.md` — edit: add Step 3 (verify pre-commit hooks installed) + Step 4 (verify .secrets.baseline exists)
   - `.windsurf/workflows/jarvis-verify.md` — edit: add Step 5 (detect-secrets scan on touched files) + Step 6 (vulture check with whitelist)
   - `.windsurf/workflows/jarvis-close.md` — edit: add C2.5 (detect-secrets baseline check before commit) + C2.7 (vulture whitelist check before commit) + C2.8 (pre-commit run on staged files) + expand C8 (CHANGELOG includes coverage percentages) + expand C10 (PLANS.md updates detect-secrets + coverage baseline rows)
   - `PLANS.md` — edit: add 2 new baseline rows (detect-secrets + coverage) to Static Analysis Baseline table — NOTE: PLANS.md is also updated at closing per standard workflow; the baseline rows added here are the in-scope edit, the closing update is the queue shift

   **NOT added in Rev4 (removed from Rev3)**: AGENTS.md OR29/OR30/OR31 — these contradicted Rev1's approved C9 ("No new AGENTS.md rules"). Tooling is enforced by the workflow doc updates (S14.1-S14.3), not by new rules. If failure patterns emerge in future plans, capture as landmines and graduate to rules then.

   **Will NOT edit**: `core/` files other than `core/approval_gate.py`, all `adapters/`, all `workers/`, all `web/` (note: `/health` smoke test already exists in `tests/test_web_server.py:33` — no new smoke test needed), all `gateways/`, all `orchestrator/`, all `evals/`, all `memory/` files except `memory/obsidian.py`, all `cli/` files except `cli/command_history.py`, all `scripts/`, all `tests/` files other than the new compliance test, all `skills/` files other than the four listed above, `AI_HANDOFF.md` (no process change — tooling is operational, not process), `CHANGELOG.md` (updated at closing per standard workflow), `LANDMINES.md` (updated at closing only if new failure pattern), `CONTEXT.md` (no vocabulary change).

   **Deferred to Plan 72+**:
   - ~150+ remaining AR18 violations in lower-density files
   - 17 empty `__init__.py` files
   - 6 resource leaks in `skills/calendar/` + `skills/screenshot/`
   - 6 assert-in-production statements
   - `pip-audit` `continue-on-error: false` flip (19 CVEs exist; diskcache CVE-2025-69872 has no fix version — needs `--ignore-vuln` strategy + diskcache replacement decision first)
   - `pytest-xdist` parallel test execution (changes test timing model, needs dedicated validation)
   - `safety`, `interrogate`, `radon`, `hypothesis` (informational metrics, Plan 74+)

## Plan Body (S1-S16)

### S1 — Baseline Test Count Check

Before any edits, run the full test suite to confirm baseline:
```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```
**Expected**: 1253 passed, 67 skipped (per PLANS.md Plan 70 baseline).
**If actual ≠ expected by more than ±5**: STOP — apply OR17 baseline reconciliation before proceeding. Report to user.

---

## Part A — Code Hygiene (S2-S8, unchanged from Rev1)

### S2 — AR18 Cleanup Strategy

AR18: "No broad `except Exception: pass` without inline comment + WARNING trace."

For each `except Exception:` block in scope, apply ONE of these patterns based on context:

**Pattern A — Bare `pass` or return-without-action** (most common):
```python
except Exception as e:
    # <one-line why this is swallowed: e.g., "trace persistence is fire-and-forget; never block caller">
    logger.warning("AR18: <operation> failed: %s", e, exc_info=True)
```

**Pattern B — Already logs but missing inline comment**:
```python
except Exception as e:
    # <one-line why this is swallowed>
    logger.warning(...)  # existing log call preserved
```

**Pattern C — Re-raise context (NOT swallowed)**:
If the `except` block re-raises or converts to a domain exception, the inline comment alone suffices (no WARNING trace needed — the caller will see the exception):
```python
except Exception as e:
    # <one-line why this is caught + re-raised as domain error>
    raise DomainError(...) from e
```

**Constraint**: Do NOT change runtime behavior. Do NOT add new dependencies. If a file already imports `logging`, reuse its existing `logger`. If a file does not have a logger, add `import logging; logger = logging.getLogger(__name__)` at the top (after existing imports).

**AR18 inline comment rules**:
- Explain WHY the exception is swallowed (not WHAT was caught — the `as e` already shows that)
- Reference the caller's expectation: "fire-and-forget", "best-effort", "non-blocking", "fallback to default", etc.
- One line. No multi-line comments.

### S3 — AR18 Cleanup: Batch 1 (system/ files)

Edit each file in turn. After EACH file, run `/jarvis-verify`:
1. Syntax check: `python -c "import ast; ast.parse(open('<file>.py').read())"`
2. Diff check: `git diff --stat <file>`
3. Targeted tests: `python -m pytest tests/test_<name>.py -v | Select-Object -Last 5`
4. Ruff: `ruff check <file>`
5. Mypy: `mypy <file> --ignore-missing-imports`

**File order** (by violation count, highest first):
1. `system/resource_manager.py` (~57 AR18 violations + 6 datetime.now() fixes per S5)
2. `system/model_acquisition.py` (~22 AR18 violations + API key validation per S6 + dead code per S7)
3. `system/model_registry.py` (~18 AR18 violations + 2 datetime.now() fixes per S5)

**Targeted test files**:
- `tests/test_resource_manager.py` (if exists; if not, run full `tests/` and verify no regressions)
- `tests/test_model_acquisition.py` (if exists)
- `tests/test_model_registry.py` (if exists)

If a targeted test file does not exist, run the full test suite after this batch:
```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```
Expected: 1253 passed, 67 skipped. If count dropped, a fix changed runtime behavior — revert and re-apply more carefully.

### S4 — AR18 Cleanup: Batch 2 (core/ + skills/ files)

Same per-file verification as S3.

**File order**:
1. `core/approval_gate.py` (~38 AR18 violations)
2. `skills/notes/notes_skill.py` (~55 AR18 violations)
3. `skills/calendar/calendar_skill.py` (~35 AR18 violations)
4. `skills/reminder/reminder_skill.py` (~29 AR18 violations)
5. `skills/email/email_skill.py` (~19 AR18 violations)

**Targeted test files**:
- `tests/test_approval_gate.py`
- `tests/test_notes_skill.py` (or similar)
- `tests/test_calendar_skill.py`
- `tests/test_reminder_skill.py`
- `tests/test_email_skill.py`

If a targeted test file does not exist, fall back to full `tests/` run.

### S5 — Bare `datetime.now()` Cleanup (OR20 compliance)

For each remaining `datetime.now()` call without `timezone.utc`:

**File**: `system/resource_manager.py` (6 instances) — already touched in S3, fix alongside AR18 work.
**File**: `system/model_registry.py` (2 instances) — already touched in S3, fix alongside AR18 work.
**File**: `system/profiler.py` (1 instance)
**File**: `cli/command_history.py` (2 instances)
**File**: `memory/obsidian.py` (1 instance)

**Replacement pattern** (per OR20):
```python
# Before
datetime.now()
datetime.now(tz=timezone.utc)  # half-fixed, missing import

# After
from datetime import datetime, timezone  # ensure timezone is imported
datetime.now(timezone.utc)
```

**Constraints**:
- Ensure `timezone` is imported in each file (most already import it via Plan 58).
- If `default_factory=datetime.utcnow` is found anywhere, replace with `default_factory=lambda: datetime.now(timezone.utc)` (per OR20).
- Do NOT change the variable name, return type, or call site.

After all 12 fixes, run `/jarvis-verify` on each touched file. For files already touched in S3/S4, the verification runs once at the end of that batch.

### S6 — API Key Validation in `system/model_acquisition.py`

**File**: `system/model_acquisition.py` (already in scope from S3)

**Line 55**: `self.hf_token = os.environ.get("HF_TOKEN")`

**Fix**: Add validation in `__init__` (or wherever `self.hf_token` is consumed). Pattern:
```python
self.hf_token = os.environ.get("HF_TOKEN")
if not self.hf_token:
    logger.warning(
        "HF_TOKEN not set — HuggingFace model acquisition will be skipped. "
        "Set HF_TOKEN environment variable to enable."
    )
```
**Rationale**: Soft warning (not hard fail) — model acquisition is best-effort; some users won't have HF_TOKEN. Matches existing pattern in `cli/adapter_factory.py` (which raises ValueError for required keys, but HF_TOKEN is optional).

**Lines 674-678** (`_validate_api_model`):
```python
api_key = os.environ.get("ANTHROPIC_API_KEY")
# ... (similar for OPENAI_API_KEY, GOOGLE_API_KEY)
```

**Fix**: Raise clear `ValueError` if the API key is missing for the requested provider:
```python
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError(
        "ANTHROPIC_API_KEY environment variable not set. "
        "Set it to use Anthropic API models."
    )
```
**Rationale**: Hard fail for API models — calling code expects a working client. Matches `cli/adapter_factory.py` pattern. Apply the same pattern for OPENAI_API_KEY and GOOGLE_API_KEY.

**Constraint**: Do NOT change the function signature, return type, or happy-path behavior. Only add validation branches for the missing-key case.

**Verification**: Run targeted tests for `system/model_acquisition.py`. If a test asserts that missing keys are silently ignored, that test must be UPDATED in scope (since the contract is changing). Document any test changes in CHANGELOG.

### S7 — Dead Code Fix in `system/model_acquisition.py`

**File**: `system/model_acquisition.py` (already in scope from S3/S6)

**Line 224** (approximate — verify with grep):
```python
min(1.0, (likes / 1000.0) + (downloads / 100000.0))
```
**Issue**: Expression evaluated but result discarded.

**Fix**: Either assign to a variable OR remove. Inspect surrounding code:
- If the result is intended to be a popularity score, assign: `popularity_score = min(1.0, ...)`
- If the line is leftover debug code, delete it.

**Decision rule**: If a downstream consumer references the result, assign. Otherwise delete. Cite the inspection finding in the commit message.

**Line 350** (approximate):
```python
sum(s.total_mb for s in system_profile.storage)
```
**Issue**: Same — expression evaluated but result discarded.

**Fix**: Same decision rule as line 224.

**Constraint**: Do NOT introduce new variables without verifying they're consumed downstream. If uncertain, prefer deletion over assignment (silent dead code is worse than no code).

### S8 — AR18 Compliance Test (Regression Prevention)

**New file**: `tests/test_ar18_compliance.py` (~80 lines)

**Purpose**: Structural test that fails if any `except Exception:` block in production code lacks an inline comment. Does NOT verify semantic correctness — only that the comment exists.

**Test implementation**:
```python
"""AR18 compliance test — ensures `except Exception:` blocks have inline comments.

This is a STRUCTURAL test, not a semantic one. It verifies that AR18's
"inline comment" requirement is satisfied. Semantic correctness (whether
the comment explains WHY) is reviewed manually.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Files exempt from AR18 compliance (e.g., test mocks that intentionally swallow)
EXEMPT_PATHS: set[str] = {
    "tests/",  # tests may swallow in fixtures
    "scripts/verify_tui_e2e.py",  # debug script
}

# Directories to scan
SCAN_DIRS = ["core", "system", "memory", "skills", "adapters", "workers", "cli", "web", "gateways", "orchestrator"]


def _has_inline_comment(source_line: str) -> bool:
    """True if the line has a '#' comment after the except clause."""
    if ":" not in source_line:
        return False
    after_colon = source_line.split(":", 1)[1]
    return "#" in after_colon


def _find_ar18_violations() -> list[tuple[str, int]]:
    """Walk the codebase and find `except Exception:` blocks without inline comments."""
    violations: list[tuple[str, int]] = []
    repo_root = Path(__file__).parent.parent

    for scan_dir in SCAN_DIRS:
        dir_path = repo_root / scan_dir
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            rel_path = str(py_file.relative_to(repo_root)).replace("\\", "/")
            if any(rel_path.startswith(exempt) for exempt in EXEMPT_PATHS):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    lines = f.readlines()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(lines, start=1):
                if re.search(r"^\s*except\s+Exception(\s+as\s+\w+)?\s*:", line):
                    if not _has_inline_comment(line):
                        violations.append((rel_path, i))
    return violations


@pytest.mark.xfail(
    strict=True,
    reason="Plan 71 fixes 8 worst-offender files; remaining ~150 violations deferred to Plan 72+",
)
def test_no_ar18_violations_in_production_code() -> None:
    """AR18: every `except Exception:` block must have an inline comment.

    If this test fails, add an inline `# <reason>` comment to each cited `except Exception:` line
    explaining WHY the exception is swallowed. See AGENTS.md AR18 and LANDMINES.md for context.
    """
    violations = _find_ar18_violations()
    if violations:
        formatted = "\n".join(f"  {path}:{line}" for path, line in violations[:20])
        suffix = f"\n  ... and {len(violations) - 20} more" if len(violations) > 20 else ""
        pytest.fail(
            f"AR18 violations found ({len(violations)} total):\n{formatted}{suffix}\n\n"
            "Fix: add an inline `# <reason>` comment to each `except Exception:` line."
        )
```

**Verification**:
1. After S3-S7 complete, run `python -m pytest tests/test_ar18_compliance.py -v`
2. **Expected**: Test XPASSES (xfail) — it will find all remaining AR18 violations across the codebase (the ~150 deferred to Plan 72 + any in files NOT touched by Plan 71).
3. **If test PASSES (not xfail)**: Plan 71 overfixed (zero violations remain). The `strict=True` flag turns this into a FAILURE — update the marker to remove `xfail` or tighten the reason.

**Constraint**: The test file MUST import cleanly. Run `python -c "import ast; ast.parse(open('tests/test_ar18_compliance.py').read())"` to verify syntax before running pytest.

---

## Part B — Tooling Integration (S9-S13, NEW in Rev2)

### S9 — detect-secrets Baseline

**Purpose**: Catch hardcoded API keys, tokens, AWS credentials before they reach git history. Bandit catches some, but `detect-secrets` is purpose-built with a baseline pattern.

**Step 1**: Install detect-secrets (add to `requirements.txt` or create `requirements-dev.txt`):
```powershell
pip install detect-secrets
```

**Step 2**: Generate baseline (marks existing strings as acceptable):
```powershell
detect-secrets scan > .secrets.baseline
```
Review `.secrets.baseline` — if it flags real secrets, STOP and report (per OR16 — scope expansion). If it flags only false positives (variable names like `api_key`, string literals in test fixtures), proceed.

**Step 3**: Verify baseline works:
```powershell
detect-secrets scan --baseline .secrets.baseline
```
Expected: exit code 0 (no new secrets found beyond baseline).

**Step 4**: Add `.secrets.baseline` to git (committed, so all contributors share the same baseline).

**Constraint**: Do NOT add `detect-secrets` to `requirements.txt` production deps. Create `requirements-dev.txt` if it doesn't exist, with a comment: `# Development dependencies — install with: pip install -r requirements-dev.txt`.

### S10 — pre-commit Configuration

**Purpose**: Run ruff + detect-secrets + standard hooks on every commit, before push. Catches issues at commit-time instead of waiting for CI.

**Step 1**: Install pre-commit (add to `requirements-dev.txt`):
```powershell
pip install pre-commit
```

**Step 2**: Create `.pre-commit-config.yaml`:
```yaml
# Pre-commit hooks for Sovereign AI
# Install: pre-commit install
# Run manually: pre-commit run --all-files
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0  # pin to a specific version
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: check-merge-conflict
      - id: debug-statements
```

**Step 3**: Install hooks locally:
```powershell
pre-commit install
```

**Step 4**: Verify hooks run (test on a deliberate trailing-whitespace change):
```powershell
# Create a test file with trailing whitespace
echo "test   " > /tmp/test-precommit.txt
# Add and commit — hook should catch it
git add /tmp/test-precommit.txt  # will fail with trailing whitespace error
```
Clean up the test file after verification.

**Constraint**: Do NOT run `pre-commit run --all-files` as part of this plan — it may flag pre-existing issues in files outside scope (OR16). The hooks are installed for FUTURE commits only. Document this in CHANGELOG.

### S11 — pytest-cov Integration

**Purpose**: Track test coverage. Informational only — does NOT gate CI. Shows which files have zero tests.

**Step 1**: Install pytest-cov (add to `requirements-dev.txt`):
```powershell
pip install pytest-cov
```

**Step 2**: Edit `pytest.ini` — add coverage config (append to existing `[pytest]` section):
```ini
[pytest]
# ... existing config ...

# Coverage (informational — does not gate CI)
# Run with: python -m pytest tests/ --cov=core --cov=system --cov=memory --cov=adapters --cov=skills --cov-report=term-missing
# To generate HTML report: add --cov-report=html
addopts =
    --cov=core
    --cov=system
    --cov=memory
    --cov=adapters
    --cov=skills
    --cov-report=term-missing
    --cov-report=
    --no-cov-on-fail
```

**Note**: The `--cov-report=` (empty) line suppresses the default XML report. The `--no-cov-on-fail` flag skips coverage when tests fail (faster feedback).

**Step 3**: Verify coverage runs:
```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 20
```
Expected: test output now includes a coverage table at the end. Tests still pass (coverage is informational).

**Step 4**: Record baseline coverage number in CHANGELOG (e.g., "Coverage: core 85%, system 72%, memory 90%, adapters 68%, skills 45%"). This is the starting point for future improvement tracking.

**Constraint**: Do NOT add `--cov-fail-under=N` — that would gate CI on coverage, which is premature. Coverage is informational only for now.

### S12 — Smoke Test Verification (Existing, No New File)

**Purpose**: Verify the `jarvis serve` FastAPI server starts and the `/health` endpoint responds.

**Discovery**: The smoke test already exists at `tests/test_web_server.py:33`:
```python
def test_health_returns_200_without_auth(self):
    """Test that GET /health returns 200 without auth token."""
    response = self.client.get("/health")
    # ... asserts 200 status
```

**Action**: No new test file needed. Instead, ensure this test is included in the full test suite run at S1 and S15. If `tests/test_web_server.py` is currently skipped or excluded, investigate why (per OR16 — do NOT fix unilaterally; report to user).

**Verification**: After all S2-S11 edits, run:
```powershell
python -m pytest tests/test_web_server.py::TestWebServer::test_health_returns_200_without_auth -v
```
Expected: PASS. If FAIL, the tooling changes (S9-S11) broke the web server — investigate and fix.

### S13 — CI Fixes (`.github/workflows/ci.yml`)

**Purpose**: Align CI with project standards (Python 3.12, full-repo mypy, vulture gating).

**Python 3.12 upgrade rationale** (addresses Rev3 review gap): AGENTS.md targets Python 3.12 as the project's runtime. CI was pinned to 3.11 — a mismatch that means CI tests against a different Python version than production runs. Kimi's scan flagged this. Python 3.12 is already installed locally (Devin runs on Windows with Python 3.12 per AGENTS.md), so the CI upgrade aligns CI with the actual development environment. No code changes required — Plan 67 already achieved full-repo mypy clean on Python 3.12. Risk: minimal; 3.12 is backward-compatible with 3.11 for all dependencies in `requirements.txt`.

**Fix 1 — Python version 3.11 → 3.12** (all 4 jobs: `test`, `security`, `dependency-audit`, `dead-code`):
```yaml
# Before
- name: Set up Python 3.11
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'

# After
- name: Set up Python 3.12
  uses: actions/setup-python@v5
  with:
    python-version: '3.12'
```
**Rationale**: AGENTS.md targets Python 3.12; CI was mismatched. Kimi's scan flagged this.

**Fix 2 — Expand mypy scope to full repo** (in `test` job):
```yaml
# Before
- name: Run mypy type checking
  run: mypy core/ adapters/ workers/ system/ cli/ memory/ --ignore-missing-imports

# After
- name: Run mypy type checking (full repo)
  run: mypy . --ignore-missing-imports
```
**Rationale**: Plan 67 achieved full-repo mypy clean (0 errors, 256 source files). CI was only checking 6 of 13 directories. Kimi's scan flagged the missing dirs: `skills/`, `tests/`, `scripts/`, `evals/`, `orchestrator/`, `gateways/`, `web/`.

**Fix 3 — Vulture whitelist + flip `continue-on-error: false`** (in `dead-code` job):

Step 3a: Create `vulture-whitelist.txt` with the 23 existing findings (run locally to capture exact format):
```powershell
vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache > vulture-whitelist.txt
```
Review the file — it should contain the 23 findings listed in PLANS.md Plan 70 baseline:
```
core/event_trigger.py:85: unused variable 'last_check_time' (100% confidence)
core/schemas.py:135: unused variable 'cls' (100% confidence)
core/schemas.py:174: unused variable 'cls' (100% confidence)
core/schemas.py:197: unused variable 'cls' (100% confidence)
core/schemas.py:517: unused variable 'cls' (100% confidence)
tests/test_anthropic_adapter.py:36: unused variable 'mock_anthropic_client' (100% confidence)
tests/test_cohere_adapter.py:42: unused variable 'mock_cohere_client' (100% confidence)
tests/test_deepseek_adapter.py:40: unused variable 'mock_deepseek_client' (100% confidence)
tests/test_eval_harness.py:186: unused variable 'g' (100% confidence)
tests/test_gemini_adapter.py:37: unused variable 'mock_genai_client' (100% confidence)
tests/test_groq_adapter.py:37: unused variable 'mock_groq_client' (100% confidence)
tests/test_huggingface_adapter.py:40: unused variable 'mock_hf_client' (100% confidence)
tests/test_mistral_adapter.py:40: unused variable 'mock_mistral_client' (100% confidence)
tests/test_openai_adapter.py:37: unused variable 'mock_openai_client' (100% confidence)
tests/test_security.py:285: unused variable 'req' (100% confidence)
tests/test_security.py:313: unused variable 'req' (100% confidence)
tests/test_security.py:344: unused variable 'req' (100% confidence)
tests/test_security.py:380: unused variable 'req' (100% confidence)
tests/test_serve.py:70: unused variable 'auth' (100% confidence)
tests/test_task_state_machine.py:355: unused variable 'raw_output' (100% confidence)
tests/test_task_state_machine.py:425: unused variable 'raw_output' (100% confidence)
tests/test_task_state_machine.py:499: unused variable 'raw_output' (100% confidence)
tests/test_together_adapter.py:40: unused variable 'mock_together_client' (100% confidence)
```

Step 3b: Edit `.github/workflows/ci.yml` `dead-code` job:
```yaml
# Before
- name: Run vulture (min-confidence 80)
  run: vulture . --min-confidence 80
  continue-on-error: true

# After
- name: Install vulture
  run: pip install vulture
- name: Run vulture (min-confidence 80, whitelist existing findings)
  run: vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache vulture-whitelist.txt
  continue-on-error: false
```
**Rationale**: The 23 existing findings are whitelisted (accepted baseline). New dead code will fail CI. This catches regression while not blocking on pre-existing debt.

**Fix 4 — Add detect-secrets job** (new job in CI):
```yaml
secrets-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - name: Install detect-secrets
      run: pip install detect-secrets
    - name: Run detect-secrets (baseline check)
      run: detect-secrets scan --baseline .secrets.baseline
      continue-on-error: false
```

**Fix 5 — Add coverage job** (informational, new job in CI):
```yaml
coverage:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    - name: Run tests with coverage
      run: python -m pytest tests/ --cov=core --cov=system --cov=memory --cov=adapters --cov=skills --cov-report=term-missing
      continue-on-error: true  # informational only — does not gate
```

**NOT changed** (deferred to Plan 72):
- `pip-audit` job `continue-on-error: true` — stays true. 19 CVEs exist; diskcache CVE-2025-69872 has no fix version. Flipping now breaks CI. Needs `--ignore-vuln` strategy + diskcache replacement decision first.

**Constraint**: Do NOT remove the existing `# TODO: change to false after Plan 56` comments — update them to `# TODO: change to false after Plan 72 (diskcache replacement + --ignore-vuln strategy)`.

---

## Part C — Workflow Document Updates (S14, NEW in Rev3)

### S14 — Update Workflow + Governance Docs to Invoke New Tooling

**Purpose**: The tooling added in S9-S13 (detect-secrets, pre-commit, vulture whitelist, coverage) is useless if the standard workflows don't reference it. This section updates the 3 jarvis workflow files + AGENTS.md + PLANS.md so the tooling is actually invoked at every plan opening, every file edit verification, and every plan closing.

**Constraint (OR7)**: All edits to `.windsurf/workflows/*.md`, `AGENTS.md`, and `PLANS.md` MUST use the Edit tool with exact `old_str`/`new_str` pairs. NEVER PowerShell `-replace`, `ForEach-Object`, or `Set-Content` (Source: L3).

**Constraint (OR26)**: Governance doc edits (AGENTS.md, PLANS.md) discovered at `/jarvis-open` must be a separate commit and tag. Since Plan 71 declares these edits in-scope at S0.3, they are NOT "discovered at open" — they are part of the plan body and go in the `prompt-71` tag. However, if Devin finds ADDITIONAL governance doc edits needed during execution (beyond what S14 specifies), those must be a separate `docs-cleanup-71` commit per OR26.

**Note on AGENTS.md**: Rev3 proposed adding OR29/OR30/OR31 to AGENTS.md. Rev4 removes this — it contradicted Rev1's approved C9 ("No new AGENTS.md rules"). The workflow doc updates in S14.1-S14.3 are sufficient to enforce tooling usage. If failure patterns emerge in future plans (e.g., Devin skips pre-commit install, baseline drifts), capture as landmines at C11 and graduate to rules in a future plan.

#### S14.1 — Update `.windsurf/workflows/jarvis-open.md`

Add Step 3 and Step 4 after the existing Step 2 (and before the "Expected result" section).

**Find-and-replace anchor** (use Edit tool per OR7):

Find:
```markdown
## Expected result

Tag verified, working copy clean. Only then proceed to the plan's own S0.3
```

Replace with:
```markdown
## Step 3: Verify pre-commit hooks are installed (NEW — Plan 71)
```powershell
pre-commit install --check 2>&1
```
If output says "hooks are not installed", run `pre-commit install` and re-verify.
If `pre-commit` command not found, STOP — dev deps not installed. Run `pip install -r requirements-dev.txt` and re-verify.

## Step 4: Verify .secrets.baseline exists (NEW — Plan 71)
```powershell
Test-Path .secrets.baseline
```
If False, STOP — baseline file missing. Either clone fresh or restore from git: `git checkout origin/master -- .secrets.baseline`.

## Expected result

Tag verified, working copy clean. Pre-commit hooks verified active. .secrets.baseline present. Only then proceed to the plan's own S0.3
```

#### S14.2 — Update `.windsurf/workflows/jarvis-verify.md`

Add Step 5 and Step 6 after the existing Step 4 (Ruff check).

**Find-and-replace anchor** (use Edit tool per OR7):

Find:
```markdown
## Expected result

All syntax checks pass, diff shows only intended files, targeted tests pass (check PLANS.md for current baseline). If any step fails, STOP and fix before moving to the next file or the closing sequence.
```

Replace with:
```markdown
## Step 5: detect-secrets scan on touched files (NEW — Plan 71)
```powershell
detect-secrets scan --baseline .secrets.baseline
```
If exit code != 0, a new secret-like string was introduced. Either:
- If false positive (e.g., test fixture with dummy API key string): update baseline with `detect-secrets scan > .secrets.baseline` and commit the change.
- If real secret: REMOVE from source immediately. Consider rotating the secret if it was committed.

## Step 6: Vulture check on touched files with whitelist (NEW — Plan 71)
```powershell
vulture <files_touched> --min-confidence 80 vulture-whitelist.txt
```
If new findings appear (not in whitelist), either:
- Fix the dead code (preferred), OR
- Add to `vulture-whitelist.txt` with an inline comment in the source file explaining why it's whitelisted (e.g., `# vulture-whitelist: required by ABC interface`).

## Expected result

All syntax checks pass, diff shows only intended files, targeted tests pass (check PLANS.md for current baseline). detect-secrets baseline check passes. Vulture whitelist check passes (no new dead code). If any step fails, STOP and fix before moving to the next file or the closing sequence.
```

#### S14.3 — Update `.windsurf/workflows/jarvis-close.md`

Three edits to this file. Use Edit tool per OR7 with the find-and-replace anchors below.

**Edit 1 — Insert C2.5, C2.7, C2.8 after C2 and before C3**

Find:
```markdown
## Step 3: File-scoped mypy on touched files
```

Replace with:
```markdown
## Step 2.5: detect-secrets baseline check (NEW — Plan 71)
```powershell
detect-secrets scan --baseline .secrets.baseline
```
If exit code != 0, STOP — a new secret was introduced. Either update baseline (if false positive) or remove the secret. Do not commit until this passes.

## Step 2.7: Vulture whitelist check (NEW — Plan 71)
```powershell
vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache vulture-whitelist.txt
```
If new findings appear (not in whitelist), STOP — either fix the dead code or add to whitelist with inline comment. Do not commit until this passes.

## Step 2.8: Pre-commit run on staged files (NEW — Plan 71)
```powershell
pre-commit run --files <staged_files>
```
If any hook fails, STOP — fix the issue before committing. Pre-commit hooks are the last gate before `git commit`.

## Step 3: File-scoped mypy on touched files
```

**Edit 2 — Expand C8 (CHANGELOG) Results section**

Find:
```markdown
**Results**:
- Tests: <count> passed, <count> skipped
- Ruff: <before> → <after>
- Tag: prompt-{N} verified on origin
```

Replace with:
```markdown
**Results**:
- Tests: <count> passed, <count> skipped
- Ruff: <before> → <after>
- Coverage: core <X>%, system <Y>%, memory <Z>%, adapters <A>%, skills <B>%
- Tag: prompt-{N} verified on origin
```

**Edit 3 — Expand C10 (PLANS.md updates)**

Find the C10 section's list of 6 update areas (a through f). After item (c) (Static analysis baseline), no change needed — the 2 new baseline rows (detect-secrets + Coverage) are added by S14.4 of this plan, so C10 only needs to fill in the Coverage percentages at closing. Add a note to C10:

Find:
```markdown
- **(c) Static analysis baseline**: update the 5-tool table if any tool count changed. Include source (Plan {N} S{step}) and delta notes.
```

Replace with:
```markdown
- **(c) Static analysis baseline**: update the 5-tool table if any tool count changed. Include source (Plan {N} S{step}) and delta notes. Also fill in Coverage row percentages (added at Plan 71 S14.4 as TBD) with actual values from S16.
```

#### S14.4 — Update `PLANS.md` — Add 2 New Baseline Rows

In the "Static Analysis Baseline" table, add two new rows after the Vulture row:

```markdown
| **detect-secrets** | 0 new secrets (baseline file: `.secrets.baseline`) | Plan 71 S9 | Baseline file committed at Plan 71. Verify with `detect-secrets scan --baseline .secrets.baseline`. Update baseline when new false positives are intentionally added. |
| **Coverage** | core / system / memory / adapters / skills percentages | Plan 71 S16 | Informational only — does NOT gate CI. Baseline captured at Plan 71; tracked for trend analysis. Trend: should not drop >5% per module in future plans — document any drops in reconciliation notes. Percentages filled in at S16 after full test suite run with coverage. |
```

Note: The Coverage row's percentages are TBD until S16 runs the full suite with `--cov`. Devin fills in the actual numbers at S16, then updates PLANS.md at C10 (closing step 10) with the real values.

**Constraint**: Do NOT update the "Completed Prompts" table or "Next 5 Prompts Queue" in S14.5 — those are updated at C10 (closing step 10) per the standard workflow. S14.5 only adds the 2 baseline rows.

#### S14.5 — Verify Workflow Updates

After all 4 workflow/governance doc edits, verify:

1. **YAML/markdown syntax** — open each file and confirm it renders correctly. For workflow files, the YAML front matter (between `---` markers) must be valid:
   ```powershell
   python -c "import yaml; yaml.safe_load(open('.windsurf/workflows/jarvis-open.md').split('---')[2])"
   python -c "import yaml; yaml.safe_load(open('.windsurf/workflows/jarvis-verify.md').split('---')[2])"
   python -c "import yaml; yaml.safe_load(open('.windsurf/workflows/jarvis-close.md').split('---')[2])"
   ```

2. **Baseline table integrity** — verify the PLANS.md Static Analysis Baseline table has 8 rows (6 existing + 2 new):
   ```powershell
   Select-String -Path PLANS.md -Pattern "^\| \*\*" | Measure-Object
   ```
   Expected: count = 8.

3. **AGENTS.md unchanged** — verify AGENTS.md was NOT edited (Rev4 removes the OR29-31 additions from Rev3):
   ```powershell
   git diff AGENTS.md
   ```
   Expected: empty output (no changes).

4. **Functional test of new workflow commands** (NEW in Rev5 — catches typos that syntax check misses). Run each new command added in S14.1-S14.3 in isolation to verify they execute without error:
   ```powershell
   # S14.1 commands
   pre-commit install --check
   Test-Path .secrets.baseline

   # S14.2 commands
   detect-secrets scan --baseline .secrets.baseline
   vulture tests/test_ar18_compliance.py --min-confidence 80 vulture-whitelist.txt

   # S14.3 commands (pre-commit run on a test file)
   pre-commit run --files tests/test_ar18_compliance.py
   ```
   If any command fails with "command not found" or a syntax error, STOP — fix the workflow doc before proceeding. A typo in a PowerShell command (e.g., `pre-comit` instead of `pre-commit`) would pass the YAML syntax check but fail at actual execution. This step catches that early.

---

## Part D — Verification (S15-S16)

### S15 — File-Scoped Verification (Fail Fast)

After all file edits complete, run consolidated verification:

**Step 1 — Syntax check** on all touched production files + test files:
```powershell
foreach ($f in @(
    "system/resource_manager.py",
    "skills/notes/notes_skill.py",
    "core/approval_gate.py",
    "skills/calendar/calendar_skill.py",
    "skills/reminder/reminder_skill.py",
    "system/model_acquisition.py",
    "skills/email/email_skill.py",
    "system/model_registry.py",
    "system/profiler.py",
    "cli/command_history.py",
    "memory/obsidian.py",
    "tests/test_ar18_compliance.py"
)) {
    python -c "import ast; ast.parse(open('$f').read())"
    if (!$?) { Write-Host "SYNTAX ERROR in $f — STOP"; exit 1 }
}
```

**Step 2 — YAML lint** on config files:
```powershell
python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

**Step 3 — Ruff** on all touched Python files:
```powershell
ruff check system/resource_manager.py skills/notes/notes_skill.py core/approval_gate.py skills/calendar/calendar_skill.py skills/reminder/reminder_skill.py system/model_acquisition.py skills/email/email_skill.py system/model_registry.py system/profiler.py cli/command_history.py memory/obsidian.py tests/test_ar18_compliance.py
```
Expected: 0 errors.

**Step 4 — Mypy** on all touched Python files (per OR2, file-scoped — NOT `mypy .`):
```powershell
mypy system/resource_manager.py skills/notes/notes_skill.py core/approval_gate.py skills/calendar/calendar_skill.py skills/reminder/reminder_skill.py system/model_acquisition.py skills/email/email_skill.py system/model_registry.py system/profiler.py cli/command_history.py memory/obsidian.py tests/test_ar18_compliance.py --ignore-missing-imports
```
Expected: 0 errors (baseline held — Plan 70 had full-repo mypy clean).

**Step 5 — detect-secrets baseline check**:
```powershell
detect-secrets scan --baseline .secrets.baseline
```
Expected: exit code 0 (no new secrets).

**Step 6 — vulture whitelist verification**:
```powershell
vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache vulture-whitelist.txt
```
Expected: exit code 0 (all findings whitelisted). If new findings appear, they're from Plan 71's code changes — fix before closing.

**Step 7 — Targeted tests**:
```powershell
python -m pytest tests/test_ar18_compliance.py tests/test_resource_manager.py tests/test_model_acquisition.py tests/test_model_registry.py tests/test_approval_gate.py tests/test_notes_skill.py tests/test_calendar_skill.py tests/test_reminder_skill.py tests/test_email_skill.py tests/test_web_server.py -v
```
(Skip any test files that don't exist; the AR18 compliance test and `test_web_server.py` are mandatory.)

If a targeted test file does not exist, fall back to running the corresponding skill/system test directory.

### S16 — Baseline Reconciliation

Run full test suite with coverage:
```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 20
```

**Expected**: ~1254 passed (1253 + 1 new AR18 compliance test, xfail), 67 skipped, 1 xfailed.

**Test count impact analysis** (addresses Rev3 review concern):
- `pytest.ini` `--cov` config: does NOT add tests. Coverage is a reporting layer over the existing test suite — it instruments the same tests, doesn't create new ones.
- `requirements-dev.txt`: dev dependencies only (detect-secrets, pre-commit, pytest-cov, vulture). None of these packages contribute test fixtures or test discovery plugins. They're CLI tools.
- CI coverage job: runs the same `python -m pytest tests/` command with `--cov` flag. Does NOT affect local test count.
- `.pre-commit-config.yaml`: runs hooks at commit time, not test time. Does NOT affect test count.
- `.secrets.baseline` / `vulture-whitelist.txt`: data files, not test code.
- Conclusion: tooling changes do NOT add or remove tests. The +1 test count comes solely from the new `tests/test_ar18_compliance.py` (S8). The 1254 assumption holds.

**Tolerance**: ±5 tests per PLANS.md.

**If actual count differs by >5 from expected**:
- STOP — apply OR17 baseline reconciliation.
- Update PLANS.md baseline with actual count + reason.
- Note in CHANGELOG.

**If ruff or mypy errors appear outside edited files**: STOP and report per OR16. Do not fix unilaterally.

**Coverage baseline**: Record the coverage percentages in CHANGELOG (e.g., "Coverage: core X%, system Y%, memory Z%, adapters A%, skills B%"). This is the starting point for future tracking — do NOT add a `--cov-fail-under` gate.

## Closing

**Run `/jarvis-close`** — handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md (if new pattern), rule proposal (C9), docs commit, push, and post-push verification. If workflow missing or fails, STOP and report.

**Closing checklist (target outcomes)**:
- [ ] Tests: ~1254 passed, 67 skipped, 1 xfailed (AR18 compliance) — within ±5 tolerance
- [ ] Ruff: 0 errors on all touched files
- [ ] Mypy: 0 errors on all touched files (file-scoped, per OR2)
- [ ] detect-secrets: baseline check passes (no new secrets)
- [ ] Vulture: whitelist check passes (no new dead code)
- [ ] Coverage: percentages recorded in CHANGELOG (informational)
- [ ] pre-commit hooks: installed locally (`.pre-commit-config.yaml` committed)
- [ ] CI: Python 3.12, full-repo mypy, vulture gated with whitelist, detect-secrets job added, coverage job added
- [ ] Tag `prompt-71` created and pushed
- [ ] CHANGELOG entry appended with: file list, violation counts fixed, datetime/API/dead-code fixes, tooling additions, coverage baseline
- [ ] PLANS.md updates:
  - Completed prompts table: Plan 71 row added
  - Test baseline: updated if count changed
  - Static analysis baseline: Vulture may stay at 23 (whitelisted); Bandit unchanged; add detect-secrets row (baseline: 0 new secrets)
  - Queue shift: Plan 72 promoted to active, new open slot added at bottom
  - Status sections: no change (no feature moved between sections — tooling is infra, not a feature)
  - Reconciliation notes: explain test count delta (if any), vulture whitelist strategy, detect-secrets baseline, coverage baseline
- [ ] LANDMINES.md: No new failure patterns expected (mechanical cleanup + tooling addition). If a new pattern emerged (e.g., "AR18 cleanup broke a test by changing exception flow", or "pre-commit hook blocked a legitimate commit"), capture as L11.
- [ ] C9: No new AGENTS.md rules. Justification: existing AR18 rule is correct; the 425 violations are pre-existing debt, not a new failure pattern. The compliance test in S8 is the structural safeguard — no new rule needed. Tooling additions (detect-secrets, pre-commit, vulture whitelist) are enforced by the workflow doc updates in S14.1-S14.3, not by AGENTS.md rules — adding rules prematurely (before any failure pattern is observed) violates the landmine-to-rule graduation process. If failure patterns emerge in future plans, capture as landmines at C11 and graduate to rules then.

**In-scope files for the `prompt-71` tag** (per OR26, governance docs declared in-scope at S0.3 go in the `prompt-71` tag; governance docs discovered during execution go in a separate `docs-cleanup-71` commit):

*Production code (11 files)*:
- `system/resource_manager.py`
- `skills/notes/notes_skill.py`
- `core/approval_gate.py`
- `skills/calendar/calendar_skill.py`
- `skills/reminder/reminder_skill.py`
- `system/model_acquisition.py`
- `skills/email/email_skill.py`
- `system/model_registry.py`
- `system/profiler.py`
- `cli/command_history.py`
- `memory/obsidian.py`

*Tests (1 file)*:
- `tests/test_ar18_compliance.py` (NEW)

*Tooling / config (6 files)*:
- `.pre-commit-config.yaml` (NEW)
- `.secrets.baseline` (NEW)
- `vulture-whitelist.txt` (NEW)
- `requirements-dev.txt` (NEW)
- `pytest.ini` (edit)
- `.github/workflows/ci.yml` (edit)

*Workflow + governance docs (4 files, NEW in Rev3; AGENTS.md removed in Rev4)*:
- `.windsurf/workflows/jarvis-open.md` (edit — add Steps 3 & 4)
- `.windsurf/workflows/jarvis-verify.md` (edit — add Steps 5 & 6)
- `.windsurf/workflows/jarvis-close.md` (edit — add C2.5, C2.7, C2.8; expand C8 & C10)
- `PLANS.md` (edit — add 2 baseline rows to Static Analysis table; closing C10 update handles the rest)

*Total: 22 files*

**Out-of-scope but tracked** (deferred to Plan 72+):
- ~150+ remaining AR18 violations in lower-density files
- 17 empty `__init__.py` files
- 6 resource leaks in `skills/calendar/` + `skills/screenshot/`
- 6 assert-in-production statements
- `pip-audit` `continue-on-error: false` flip (needs diskcache replacement + `--ignore-vuln` strategy)
- `pytest-xdist` parallel test execution (needs dedicated validation)
- `safety`, `interrogate`, `radon`, `hypothesis` (informational metrics, Plan 74+)
