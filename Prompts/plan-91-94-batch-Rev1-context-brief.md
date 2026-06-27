# Batch Plans 91–94 — Round Table Review Brief
## Batch 3: Plans 91–94 | Rev1 (UI Remediation — Phases 1–3)

---

## Part 1: Roles/Rules

Your job is to find issues in this plan set, not rewrite it. Assume this plan set will fail in 6 months — identify the most plausible reasons. Each issue must include a concrete failure scenario and evidence from the codebase or plan files. Criticize my reasoning, not my conclusions. You may respond "Clean pass" if the plan set is sound.

Ban: style comments, formatting preferences, speculative future features, performance optimizations without measured impact, re-raising issues already resolved in prior batches without new evidence.

---

## Part 2: Context

### What this batch covers

Four plans delivering UI remediation for the most critical gaps identified in `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md`:

- **Plan 91** (Model & Adapter Management — Phase 1a, CRITICAL): Wire `api/models.py` stubs to `system/model_registry.py`. Create `modelStore.ts`, `ModelsPanel.tsx`. Make StatusBar model slug clickable (remove "Coming in Plan 89" tooltip). Add `VIEWS.MODELS`.
- **Plan 92** (Model Downloader + Fallback Chain — Phase 1b, CRITICAL): Wire download endpoints to `system/model_acquisition.py`. Add fallback chain endpoints (`api/adapters.py`). Create `ModelDownloader.tsx` modal, Fallback Chain Editor in SettingsDrawer.
- **Plan 93** (Worker Creation & Configuration — Phase 2, CRITICAL): Wire `api/workers.py` stubs to `core/worker_factory.py`. Create `WorkerCreator.tsx`, `WorkerEditor.tsx`. Make WorkersPanel cards clickable to open editor.
- **Plan 94** (Cost & Resource Controls — Phase 3, HIGH): Add `PUT /api/costs/policy` and `GET /api/resources/monitor`. Un-mock SettingsDrawer Cost Policy tab. Create `ResourceMonitorPanel.tsx` with live charts.

### Key dependencies

- Plan 92 depends on Plan 91 (ModelsPanel exists to host the Download button)
- Plan 93 depends on Plan 92 (UI patterns established — modal, store extension)
- Plan 94 depends on Plan 93 (UI patterns established — un-mocking, new panel)
- All plans depend on `prompt-90` (scan complete, stubs created, baselines held)

### Post-scan state (Plan 90 completed 2026-06-26)

**Baselines held**: 1457 Python tests + 46 Vitest + 8 Playwright, coverage 82%, mypy 0, vulture 40, ruff 0.
**Stubs created in Plan 90**: `api/models.py` (3 endpoints), `api/workers.py` (3 endpoints), `tests/test_api_stubs.py` (5 tests).
**Gap analysis committed**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` is the authoritative source for this batch's scope.

### Cross-plan dependency map

| Plan | Depends on | What it provides for next plan |
|------|------------|-------------------------------|
| 91 | prompt-90 | ModelsPanel, modelStore, api/models.py wired, StatusBar model selector |
| 92 | prompt-91 | ModelDownloader modal, api/adapters.py, Fallback Chain Editor |
| 93 | prompt-92 | WorkerCreator, WorkerEditor, api/workers.py wired, workerStore extended |
| 94 | prompt-93 | ResourceMonitorPanel, un-mocked SettingsDrawer, cost policy API |

### Sequencing risks

- **If Plan 91 executes before Plan 90 completes**: `api/models.py` stubs won't exist — Plan 91's "wire stubs" step fails. Mitigated by `Depends on: prompt-90`.
- **If Plan 92 executes before Plan 91**: ModelsPanel won't exist to host the Download button. The ModelDownloader modal would be orphaned. Mitigated by `Depends on: prompt-91`.
- **If Plan 93 executes before Plan 92**: Worker UI patterns (modal, store extension) from Plan 92 aren't established. Plan 93 would still work but may diverge in pattern. Mitigated by `Depends on: prompt-92`.
- **If Plan 94 executes before Plan 93**: Un-mocking pattern from Plan 93 isn't established. Plan 94's SettingsDrawer changes would still work but may diverge. Mitigated by `Depends on: prompt-93`.

### Author's reasoning (attack this, not the conclusion)

**Decision 1: Wire stubs rather than create new endpoints.**
My reasoning: Plan 90 created `api/models.py` and `api/workers.py` as stubs with 501/404 responses and 5 tests. Plans 91 and 93 replace the stubs with real implementations. This is cleaner than creating new files — the test scaffolding and router wiring already exist. The tradeoff: the stub tests in `tests/test_api_stubs.py` need updating (they currently assert 501/404, but after wiring they'll get real responses).

**Decision 2: Plans 91–93 use optional injection for new orchestrator dependencies.**
My reasoning: The orchestrator already has `approval_gate`, `worker_circuit_breaker`, `model_tier_router` as optional injections. Adding `model_registry`, `model_acquisition`, `worker_factory`, `system_profiler` follows the same pattern. The tradeoff: if any of these aren't configured at runtime, the API returns 503. This is acceptable — it surfaces configuration gaps immediately rather than failing silently.

**Decision 3: Plan 94 only un-mocks the Cost Policy tab.**
My reasoning: The SettingsDrawer has 4 tabs (Cost Policy, Circuit Breaker, Sandbox, Auth). Un-mocking all 4 in one plan would be too large. Cost Policy is the highest-impact (users can't configure budgets). Circuit Breaker, Sandbox, and Auth remain mocked for future plans. The tradeoff: the SettingsDrawer will have a mix of real and mocked fields, which could confuse users. The `data-mocked` attributes remain on the un-mocked tabs to signal this.

**Decision 4: Plan 92's download is async with polling.**
My reasoning: Model downloads can take 10+ minutes (large models). A synchronous endpoint would timeout. The flow is: POST /download returns download_id immediately, client polls GET /download/{id}/status every 2s. The tradeoff: `ModelAcquisition` needs a `get_download_status()` method that doesn't exist yet — Plan 92 adds it. If the download fails silently (background task crashes), the client polls forever. Mitigation: the status dict includes a `status: "failed"` state.

**Decision 5: Plan 93's WorkerEditor uses sliders for 0.0–1.0 floats.**
My reasoning: DynamicWorkerProfile has 6 float fields in [0.0, 1.0] range (complexity_min/max, preferred_complexity, depth_preference, verbosity, etc.). Sliders are the natural UI for bounded floats. The tradeoff: sliders are imprecise — users can't enter exact values like 0.75. Mitigation: the slider shows the current value to 2 decimal places, and users can fine-tune by dragging.

### Author's confidence by plan

| Plan | Confidence | Risk if wrong |
|------|------------|---------------|
| Plan 91 (Model & Adapter Management) | 85% | Low — wiring stubs to existing ModelRegistry API |
| Plan 92 (Model Downloader + Fallback) | 70% | Medium — ModelAcquisition.request_download() signature unverified, async download status tracking is new |
| Plan 93 (Worker Creation) | 80% | Low — WorkerFactory API is well-documented |
| Plan 94 (Cost & Resource Controls) | 75% | Medium — CostTracker._policy is private attribute, SystemProfiler.refresh() signature unverified |

**Attack Plans 92 and 94 hardest** — they have the most unverified assumptions about backend API signatures.

### Open questions

1. **ModelAcquisition.request_download() signature**: Does it accept `(model_id, quantisation, registry)` or a different parameter set? The plan assumes it returns a download_id string, but the actual return type may be a DownloadResult object. If so, the async wrapper needs adjustment.

2. **cli/adapter_factory.py API**: Does `create_adapter(name)` exist as a standalone function, or is it a class method? Does `ADAPTER_TYPES` exist as a dict/list of available adapter names? Plan 92's fallback chain endpoint depends on both.

3. **CostTracker._policy access**: The plan directly accesses `_policy` (private attribute) to read current policy and calls `update_policy()` to set it. Should `get_policy()` be added as a public method instead? Accessing private attributes is a code smell.

4. **SystemProfiler.refresh() return type**: Does it return a `SystemProfile` object with `.cpu.percent`, `.ram.percent`, `.gpu.percent` fields? Or does it return a dict? Plan 94's endpoint assumes object attribute access.

5. **WorkerFactory.list_workers() return type**: Does it return `WorkerProfile` objects or `DynamicWorkerProfile` objects? Plan 93's response converter assumes `DynamicWorkerProfile` (which has the extended fields like `complexity_min`).

6. **ModelRegistry initialization**: Is `registry.initialize(system_profile)` called at app startup? If not, `list_all()` returns 0 models and Plan 91's STOP condition triggers. Where should initialization happen — in `web/server.py` startup or in the orchestrator constructor?

7. **Approval gate for downloads**: The gap analysis (§9) suggests requiring approval for downloads >1GB. Plan 92 doesn't implement this — should it? Or defer to a future plan?

8. **ResourceMonitorPanel polling cadence**: 5s interval for resource monitoring. Is this too aggressive? Could cause unnecessary load. The gap analysis (§9) mentions "Use SSE for push updates, not polling; sample every 5s" — should this use SSE instead of polling?

---

## Part 3: Answer Format

Respond with:

1. **Verdict**: "Clean pass" OR "Issues found"
2. **If issues found, categorize**:
   - **CRITICAL**: Data loss, security vulnerability, or irreversible system damage. Blocks clean pass — no overrides.
   - **HIGH**: Devin STOP condition, test failure, broken build, Windows incompatibility. Blocks clean pass unless overruled with user sign-off.
   - **MEDIUM**: Degraded functionality, poor UX, tech debt. Should address; document if accepted.
   - **LOW**: Style, naming, speculative, perf without measured impact. Prompt Creator discretion.
3. **For each issue**: concrete failure scenario + suggested fix + cite specific plan lines
4. **Cross-plan dependency check**: Verify execution order (91→92→93→94) is correct and no circular dependencies exist
5. **Backend API verification**: For each unverified signature (open questions 1–6), flag if the plan's assumption is wrong and what the correct signature should be
6. **Other concerns** — open field for anything not covered above

Permitted: "Clean pass" if Rev1 is sound. Do not invent issues to fill space.
