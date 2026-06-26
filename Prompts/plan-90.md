# Plan 90 — 5-Plan Milestone Scan + Bug Fixes + UI Gap Foundation

**Tag**: `prompt-90` | **Depends on**: `prompt-89`

---

## Scope

Whole-repo scan after Batch 2 (Plans 86–89). No new features. Fixes only. This plan:
1. Fixes bugs found in Plans 86–89 execution logs
2. Runs standard scan (baselines, static analysis, full test suite)
3. Stubs out the most critical missing API endpoints identified in the UI/UX Gap Analysis (Model Registry, Worker Factory) as foundation for Plans 91–94
4. Reconciles PLANS.md state

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-89` tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.
S0.3. No new AGENTS.md rules this prompt. (Scan prompts propose rules via C9 only if new landmine patterns are found.)

---

## S1. Fix Plan 89 SyntaxError in web/server.py (HIGH — execution bug)

**Problem**: Plan 89's Telegram polling shutdown handler has a Python SyntaxError: `global _telegram_poll_task` is declared AFTER the variable is assigned in the function. Python requires `global` declarations to come before any use of the variable in that scope.

**Evidence**: Plan 89 execution log, lines 1744–1746:
```
File "C:\Jarvis\web\server.py", line 80
E       global _telegram_poll_task
E       ^^^^^^^^^^^^^^^^^^^^^^^^^^
E   SyntaxError: name '_telegram_poll_task' is assigned to before global declaration
```

**Step 1**: Read `web/server.py` and locate the `_telegram_poll_task` global declaration in the shutdown handler.

**Step 2**: Fix by moving the `global _telegram_poll_task` declaration to the FIRST line of the shutdown function (before any reference to the variable):
```python
@app.on_event("shutdown")
async def stop_telegram_polling():
    global _telegram_poll_task  # MUST be first line
    if _telegram_poll_task and not _telegram_poll_task.done():
        _telegram_poll_task.cancel()
        try:
            await _telegram_poll_task
        except asyncio.CancelledError:
            pass
        logger.info("Telegram polling task cancelled")
```

**Step 3**: Also verify the startup handler has `global _telegram_poll_task` as its first line.

**Step 4**: Verify the fix:
```powershell
python -c "from web.server import create_app; print('Import OK')"
```
Expected: `Import OK` with no SyntaxError.

---

## S2. Fix Plan 89 test fixture ValidationError (HIGH — execution bug)

**Problem**: `tests/test_multi_channel_approval_gate.py` has test fixtures that create `ApprovalRequest` objects missing required fields (`task_id`, `action_type`, `action_description`). Pydantic raises ValidationError.

**Evidence**: Plan 89 execution log, lines 719–728:
```
pydantic_core._pydantic_core.ValidationError: 3 validation errors for ApprovalRequest
E       task_id
E         Field required [type=missing, input_value={'request_id': 'test-123'...}, input_type=dict]
E       action_type
E         Field required
```

**Step 1**: Read `tests/test_multi_channel_approval_gate.py` and find the `sample_approval_request` fixture.

**Step 2**: Add the missing required fields to the fixture:
```python
@pytest.fixture
def sample_approval_request():
    """Sample ApprovalRequest."""
    return ApprovalRequest(
        request_id="test-123",
        task_id="task-456",           # ADD — was missing
        session_id="session-789",      # ADD if missing
        action_type=ApprovalActionType.SYSTEM_CONFIG,  # ADD — was missing
        action_description="Test approval request",     # ADD — was missing
        action_parameters={},
        risk_level="medium",
        reason_for_approval="Test reason",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
    )
```

**Step 3**: Verify the fix:
```powershell
python -m pytest tests/test_multi_channel_approval_gate.py -vvv
```
Expected: All tests pass with no ValidationError.

---

## S3. Verify Plan 86 xterm.js SSR fix (MEDIUM — verify existing fix)

**Problem**: Plan 86 had a Next.js prerender error: `ReferenceError: self is not defined` — xterm.js uses `self` which isn't available during SSR. Devin fixed this with dynamic import.

**Step 1**: Read `src/components/panels/TerminalPanel.tsx` and verify it uses `next/dynamic` with `ssr: false`:
```typescript
const TerminalPanel = dynamic(() => import("./TerminalPanelImpl"), { ssr: false });
```
OR verify the xterm.js import is inside a `useEffect` (client-side only).

**Step 2**: If the fix is not present or incomplete, apply the dynamic import pattern:
```typescript
// In page.tsx or ShellClient.tsx, use dynamic import with ssr: false
import dynamic from "next/dynamic";
const TerminalPanel = dynamic(() => import("@/components/panels/TerminalPanel"), { ssr: false });
```

**Step 3**: Verify the build:
```powershell
cd src && npm run build
```
Expected: Build succeeds with no prerender errors.

---

## S4. Verify Plan 88 ImportError fix (MEDIUM — verify existing fix)

**Problem**: Plan 88 had `ImportError: cannot import name 'Solution' from 'memory.debate_pool'` — the test tried to import `Solution` but the class is actually `ExpertSolution`.

**Step 1**: Read `tests/test_pemads_judge.py` and verify the import:
```python
from memory.debate_pool import DebatePool, ExpertSolution, JudgeScore  # NOT 'Solution'
```

**Step 2**: If the wrong import name is still present, fix it to `ExpertSolution`.

**Step 3**: Verify:
```powershell
python -m pytest tests/test_pemads_judge.py -vvv
```
Expected: All tests pass with no ImportError.

---

## S5. Full static analysis scan

Run all static analysis tools and verify against PLANS.md baselines:

```powershell
# Ruff (full repo)
ruff check . 2>&1 | Select-Object -Last 5
# Expected: 0 errors

# Mypy (core/ system/)
mypy core/ system/ --ignore-missing-imports 2>&1 | Select-Object -Last 5
# Expected: 0 errors

# Bandit
bandit -r . -x .venv,venv,node_modules,.git 2>&1 | Select-Object -Last 10
# Expected: baseline (check PLANS.md for current count)

# pip-audit
pip-audit 2>&1 | Select-Object -Last 10
# Expected: baseline CVEs (upstream only)

# Vulture
python -c "
import subprocess, sys
result = subprocess.run(['vulture', '.', '--min-confidence', '80', '--exclude', '.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache'], capture_output=True, text=True)
findings = [l for l in result.stdout.splitlines() if 'confidence' in l]
print(f'Total findings: {len(findings)}')
with open('vulture-whitelist.txt', encoding='utf-8') as f:
    whitelist = set(l.strip() for l in f if l.strip())
new_findings = [f for f in findings if f not in whitelist]
if new_findings:
    print(f'NEW findings: {len(new_findings)}')
    for f in new_findings:
        print(f'  {f}')
    sys.exit(1)
print(f'All {len(findings)} findings are whitelisted.')
"
# Expected: 40 findings (baseline), all whitelisted

# detect-secrets
detect-secrets scan --baseline .secrets.baseline
# Expected: exit code 0 (no new secrets)
```

**For each tool**: If count differs from PLANS.md baseline, document the delta in PLANS.md reconciliation notes with cause and justification. Fix any new findings that are not already documented as accepted suppressions.

---

## S6. Full test suite

Run all test suites with full verbose output:

```powershell
# Python tests
python -m pytest tests/ -vvv
# Expected: 1451 passed, 67 skipped (baseline, before S7 stub tests)

# Vitest
cd src; npm test
# Expected: 46 tests passed (baseline)

# Playwright E2E
cd src; npx playwright test
# Expected: 8 tests passed (baseline)

# TypeScript build
cd src; npx tsc --noEmit
# Expected: 0 errors

# Next.js build (verify no prerender errors)
cd src; npm run build
# Expected: Build succeeds with no "self is not defined" or other SSR errors

# Coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
# Expected: 82% (baseline, -5% tolerance = 77% minimum)
```

**STOP condition**: If any test fails non-trivially, STOP and report. Do not suppress test failures.

---

## S7. Stub critical missing API endpoints (UI Gap Analysis foundation)

**Context**: The UI/UX Gap Analysis identified that the backend has ~30 subsystems but the Web UI only exposes ~8. The most critical gaps are Model/Adapter Management and Worker Creation. This step stubs out the missing API endpoints as a foundation for Plans 91–94 (which will build the UI).

**Step 1**: Create `api/models.py` — FastAPI router for model registry endpoints:
```python
"""API router for model registry endpoints.
Stubs created in Plan 90 scan. Full implementation in Plan 91-92.
"""
from fastapi import APIRouter, HTTPException
from typing import Any

router = APIRouter(prefix="/api/models", tags=["models"])

@router.get("")
async def list_models() -> list[dict[str, Any]]:
    """List all registered models. Stub — returns empty list.
    TODO: Wire to system.model_registry.ModelRegistry.list_all() in Plan 91.
    """
    return []

@router.get("/{model_id}")
async def get_model(model_id: str) -> dict[str, Any]:
    """Get model details by ID. Stub — returns 404.
    TODO: Wire to system.model_registry.ModelRegistry.get() in Plan 91.
    """
    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found (stub)")

@router.get("/search")
async def search_models(query: str = "") -> list[dict[str, Any]]:
    """Search HuggingFace/Ollama catalogues. Stub — returns empty list.
    TODO: Wire to system.model_acquisition in Plan 91.
    """
    return []
```

**Step 2**: Create `api/workers.py` — FastAPI router for worker CRUD endpoints:
```python
"""API router for worker CRUD endpoints.
Stubs created in Plan 90 scan. Full implementation in Plan 93-94.
"""
from fastapi import APIRouter, HTTPException
from typing import Any

router = APIRouter(prefix="/api/workers", tags=["workers"])

@router.post("/create")
async def create_worker(description: str) -> dict[str, Any]:
    """Create a worker from natural language description. Stub — returns 501.
    TODO: Wire to core.worker_factory.WorkerFactory.create_worker() in Plan 93.
    """
    raise HTTPException(status_code=501, detail="Worker creation not yet implemented (stub)")

@router.put("/{worker_id}")
async def update_worker(worker_id: str, config: dict) -> dict[str, Any]:
    """Update worker configuration. Stub — returns 501.
    TODO: Wire to core.worker_factory in Plan 94.
    """
    raise HTTPException(status_code=501, detail="Worker update not yet implemented (stub)")

@router.delete("/{worker_id}")
async def delete_worker(worker_id: str) -> dict[str, Any]:
    """Delete/deregister a worker. Stub — returns 501.
    TODO: Wire to core.worker_factory.WorkerFactory.deregister_worker() in Plan 94.
    """
    raise HTTPException(status_code=501, detail="Worker deletion not yet implemented (stub)")
```

**Step 3**: Create `api/__init__.py` (if it doesn't exist):
```python
"""API routers package."""
```

**Step 4**: Wire routers into `web/server.py`:
```python
# In create_app(), after existing routes:
from api.models import router as models_router
from api.workers import router as workers_router

app.include_router(models_router)
app.include_router(workers_router)
```

**Step 5**: Add backend tests for the stub endpoints:
```python
# tests/test_api_stubs.py
def test_list_models_stub(client_no_auth):
    res = client_no_auth.get("/api/models")
    assert res.status_code == 200
    assert res.json() == []

def test_get_model_stub_404(client_no_auth):
    res = client_no_auth.get("/api/models/nonexistent")
    assert res.status_code == 404

def test_create_worker_stub_501(client_no_auth):
    res = client_no_auth.post("/api/workers/create?description=test")
    assert res.status_code == 501

def test_update_worker_stub_501(client_no_auth):
    res = client_no_auth.put("/api/workers/test-id", json={})
    assert res.status_code == 501

def test_delete_worker_stub_501(client_no_auth):
    res = client_no_auth.delete("/api/workers/test-id")
    assert res.status_code == 501
```

**Step 6**: Verify:
```powershell
python -m pytest tests/test_api_stubs.py -vvv
```
Expected: All 5 tests pass.

---

## S8. Scan LANDMINES.md for missing rules

**Step 1**: Read LANDMINES.md in full.

**Step 2**: For each landmine, check if a corresponding AR/OR rule exists in AGENTS.md.

**Step 3**: If any landmine has no corresponding rule, propose via C9 with "Source: landmine L{n}".

**Step 4**: If no new landmine patterns were found during Plans 86–89 or this scan, note "No new landmine patterns" in C9.

---

## S9. Scan CHANGELOG.md

**Step 1**: Verify Plans 86, 87, 88, 89 all have CHANGELOG entries:
```powershell
Select-String -Path CHANGELOG.md -Pattern "prompt-8[6-9]"
```
Expected: 4 matches.

**Step 2**: If any plan is missing a CHANGELOG entry, add it retroactively using the execution logs.

---

## S10. Scan PLANS.md for consistency

**Step 1**: Verify completed prompts table has rows for Plans 86, 87, 88, 89, and 90 (this scan).

**Step 2**: Verify test baseline reflects actual counts from S6 + S7:
- Python: 1451 + 5 new stub tests = 1456
- Vitest: 46
- Playwright: 8

**Step 3**: Verify static analysis baselines reflect actual counts from S5.

**Step 4**: Update Next 5 Prompts Queue. Per the UI/UX Gap Analysis remediation roadmap:
- Plan 91: Model & Adapter Management (Phase 1a) — Model Registry API + Model Browser Panel + Adapter Selector
- Plan 92: Model & Adapter Management (Phase 1b) — Model Downloader + Fallback Chain Editor + Hardware Check
- Plan 93: Worker Management (Phase 2) — Worker Factory API + Worker Creator UI + Worker Detail View
- Plan 94: Cost & Resource Controls (Phase 3) — Cost Policy API + Resource Monitor + Alert Config
- Plan 95: Scan prompt (5-plan milestone)

**Step 5**: Update PLANS.md "Last updated" line to reference this scan.

---

## S11. Scan docstrings for stale references

**Step 1**: Search for references to removed/renamed modules:
```powershell
# Check for stale 'Solution' references (should be 'ExpertSolution')
Select-String -Path *.py -Pattern "from memory.debate_pool import.*Solution[^s]" -Recurse | Select-Object -First 10

# Check for references to TerminalPlaceholder (deleted in Plan 86)
Select-String -Path *.tsx -Pattern "TerminalPlaceholder" -Recurse | Select-Object -First 10
```

**Step 2**: Fix any stale references found.

---

## What NOT to do

- Do not add new UI features (that's Plans 91–94).
- Do not implement the stub endpoints fully (just stubs with 501/404/empty responses).
- Do not refactor working code unless it violates an existing AR/OR rule.
- Do not touch test fixtures beyond fixing failures caused by the above.
- Do not suppress mypy errors with `# type: ignore` unless documented.
- Do not skip Playwright E2E tests — they must pass.

---

## STOP condition

If any scan reveals a structural problem requiring design decisions (not mechanical fixes), STOP and report. Do not guess. Examples:
- The SyntaxError fix requires restructuring the entire web/server.py
- A test failure reveals a fundamental architecture issue
- Coverage drops >5% from baseline without clear cause

---

## Files WILL create
- `api/__init__.py` (if not exists)
- `api/models.py` (stub endpoints)
- `api/workers.py` (stub endpoints)
- `tests/test_api_stubs.py` (5 tests for stub endpoints)

## Files WILL edit
- `web/server.py` (fix SyntaxError in shutdown handler, include new routers)
- `tests/test_multi_channel_approval_gate.py` (fix ApprovalRequest fixture missing fields)
- `PLANS.md` (update baselines, queue shift to Plans 91–95)
- `CHANGELOG.md` (add Plan 90 entry at closing)
- `vulture-whitelist.txt` (update if new findings)
- `src/components/panels/TerminalPanel.tsx` (verify/fix SSR dynamic import — if needed)

## Files will NOT edit
- `core/` logic modules (no new features)
- `system/` internals
- `adapters/`
- `workers/`
- `memory/` internals
- `skills/`
- `src/` frontend components (no new UI — that's Plans 91–94)

---

## Closing

Run `/jarvis-close`. Tag `prompt-90`. CHANGELOG entry for Plan 90. Update PLANS.md (completed row, baseline reconciliation, queue shift to Plans 91–95 per UI/UX Gap Analysis roadmap).
