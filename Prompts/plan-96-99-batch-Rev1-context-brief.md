# Batch Plans 96–99 — Round Table Review Brief
## Batch 4: Plans 96–99 | Rev1 (Post-Plan-95-Scan)

---

## Part 1: Roles/Rules

Your job is to find issues in this plan set, not rewrite it. Assume this plan set will fail in 6 months — identify the most plausible reasons. Each issue must include a concrete failure scenario and evidence from the codebase or plan files. Criticize my reasoning, not my conclusions. You may respond "Clean pass" if the plan set is sound.

Ban: style comments, formatting preferences, speculative future features, performance optimizations without measured impact, re-raising issues already resolved in prior batches without new evidence.

---

## Part 2: Context

### What this batch covers

Four plans completing the UI remediation roadmap — exposing backend capabilities that have no UI surface yet:

- **Plan 96** (Memory Backend + UI — HIGH): Complete multi-backend memory architecture. Backend: MemoryBackend protocol, SQLite FTS5 + Kuzu Graph, MemoryRouterV2 (intent-based routing), 4 API endpoints. Frontend: 3 panels (MemoryMapPanel with SVG graph, MemorySearchPanel with backend attribution badges, MemoryConfigPanel with tier toggles). Combined backend+frontend in one plan. Reference: `docs/Memory-Backend-Modules-UI-Integration-Reference.md`.
- **Plan 97** (Debate & Expert Panel UI — HIGH): Expose PEMADS debate system (Plans 87–88) via Web UI. Backend: debate list/detail/verdict endpoints, expert list endpoint. Frontend: DebatePanel with expert list, debate history, judge verdict display.
- **Plan 98** (Security & Sandbox Visibility — HIGH): Expose sandbox + trust registry via Web UI. Backend: sandbox status/logs, trust registry CRUD, sanitiser status. Frontend: SandboxPanel (container list + logs), TrustRegistryPanel (add/revoke trust).
- **Plan 99** (Observability & Trace Viewer — MEDIUM): Expose trace store + session manager via Web UI. Backend: trace query with filters, session CRUD. Frontend: TraceViewerPanel (search/filter), SessionManagerPanel (create/delete).

### Key dependencies

- Plan 97 depends on Plan 96 (memory infrastructure patterns established)
- Plan 98 depends on Plan 97 (UI panel patterns established)
- Plan 99 depends on Plan 98 (UI panel patterns established)
- All plans depend on `prompt-95` (scan complete, all baselines held, all governance fixed)

### Post-scan state (Plan 95 completed 2026-06-27)

**Baselines**: 1476 Python tests (70 skipped) + 52 Vitest (7 skipped) + 8 Playwright (deferred). Coverage 82%. Ruff 0. Mypy 0. Vulture 40. All held.
**Governance**: jarvis-close has C9 (concrete templates) + C16 (Git Bash cleanup). AI_HANDOFF says "Git Bash on Windows". jarvis-open uses `test -f`. All `.txt` files moved to `txt/` folder.
**Known deferred**: Playwright E2E has web server startup issue (not blocking). 7 Vitest tests skipped (WorkerCreator, WorkerEditor, ModelsPanel components — will be implemented when UI panels land).
**Git Bash**: All commands use Unix syntax. No PowerShell.

### Cross-plan dependency map

| Plan | Depends on | What it provides for next plan |
|------|------------|-------------------------------|
| 96 | prompt-95 | Memory backend infrastructure, API router pattern, memoryMapStore |
| 97 | prompt-96 | API router pattern (debates), debateStore, DebatePanel component |
| 98 | prompt-97 | API router pattern (sandbox/trust), panel patterns for status displays |
| 99 | prompt-98 | API router pattern (traces/sessions), panel patterns for list+detail views |

### Sequencing risks

- **If Plan 96 Kuzu fails to install on Windows**: KuzuBackend disabled, FTS5 still works. Memory Map panel shows empty graph. Not a STOP — documented in plan.
- **If Plan 97 PEMADS not configured**: Endpoints return 503 (expected). Panel shows "No experts registered" / "No debates yet". Not a STOP.
- **If Plan 98 Docker not available**: Sandbox status returns `available: false`. Panel shows fallback message. Not a STOP.
- **If Plan 99 trace emitter not configured**: Endpoints return 503 (expected). Panel shows "No trace events." Not a STOP.

### Author's reasoning (attack this, not the conclusion)

**Decision 1: Combined backend+frontend in Plan 96 (not split).**
My reasoning: The memory backend protocol, backends, and router are tightly coupled to the API endpoints and frontend panels. The frontend needs to know the exact API response shapes, which depend on the backend protocol. Splitting would require defining API contracts twice. The tradeoff: Plan 96 is large (~1240 lines) but eliminates inter-plan dependency.

**Decision 2: All 4 plans are read-only UI over existing backend modules.**
My reasoning: Plans 87–89 built PEMADS (debate pool, expert panel, judge, gate). Plan 73 built SandboxExecutor. Plan 76 built ApprovalTrustRegistry. Plan 71 built InputSanitiser. Plan 67 built TraceEmitter. Plan 68 built SessionManager. These all work — they just have no UI. Plans 96–99 only add API routers + frontend panels. No backend logic changes. The tradeoff: if any backend module's API doesn't match what the plan assumes, the S0.5 pre-verification catches it.

**Decision 3: SVG graph instead of D3.js or react-force-graph for Memory Map.**
My reasoning: Adding a graph library dependency (D3.js ~200KB, react-force-graph ~500KB) for a single panel is overkill. SVG with a simple circle layout works for <200 nodes. The tradeoff: no force simulation, nodes are placed in a circle. Not as pretty but functional and zero-dependency. Can upgrade to D3.js in a future plan if the graph is hard to read.

**Decision 4: Each plan creates its own API router file (api/debates.py, api/sandbox.py, etc.).**
My reasoning: Following the pattern established in Plans 91–94 (api/models.py, api/workers.py, api/adapters.py). Each router is self-contained, has its own test file, and can be included/excluded independently. The tradeoff: more files, but each is small and focused.

### Confidence by plan

| Plan | Confidence | Risk if wrong |
|------|------------|---------------|
| Plan 96 (Memory Backend + UI) | 75% | Medium — Kuzu install on Windows unverified, MemoryRouterV2 is new architecture |
| Plan 97 (Debate & Expert Panel UI) | 85% | Low — backend exists (Plans 87-88), just adding API + UI |
| Plan 98 (Security & Sandbox Visibility) | 80% | Low — backend exists, Docker may not be available on Windows |
| Plan 99 (Observability & Trace Viewer) | 85% | Low — backend exists, trace emitter may not be configured |

**Attack Plan 96 hardest** — it has the most new code (backend protocol + 2 backends + router + 3 panels).

### Open questions

1. **Kuzu on Windows**: Does `pip install kuzu` work on Windows? The plan has a STOP condition if it fails, but if Kuzu is fundamentally incompatible with Windows, the entire graph backend is dead. Is there a fallback graph DB that works on Windows?

2. **MemoryRouterV2 vs existing core/memory_router.py**: The plan creates `memory/memory_router_v2.py` to avoid conflict with the existing `core/memory_router.py`. Is this the right pattern, or should the existing router be extended? Will having two routers confuse Devin?

3. **DebatePool filesystem access**: Plan 97's `list_debates` endpoint scans the `debate_pools/` directory. Is this directory guaranteed to exist? If no debates have been run, the endpoint returns an empty list — is that acceptable?

4. **Trust registry access path**: Plan 98 accesses `orchestrator.approval_gate.trust_registry`. Is `trust_registry` a public attribute on `ApprovalGate`? If it's private, the plan says to add a public getter — but modifying `core/approval_gate.py` may be out of scope.

5. **TraceEmitter.get_events()**: Plan 99 calls `orchestrator._emitter.get_events(limit)`. Is `_emitter` accessible? Is `get_events()` the correct method name? Does it return objects with `component`, `event_type`, `level`, `message` attributes?

6. **SessionManager.query_sessions()**: Plan 99 calls `orchestrator.session_manager.query_sessions()`. Does this method exist? What does it return — a list of `SessionSummary` objects? Does `SessionSummary` have `session_id`, `created`, `summary` fields?

---

## Part 3: Answer Format

Respond with:

1. **Verdict**: "Clean pass" OR "Issues found"
2. **If issues found, categorize**:
   - **CRITICAL**: Data loss, security vulnerability, irreversible damage. Blocks execution — no overrides.
   - **HIGH**: Devin STOP condition, test failure, broken build, Windows incompatibility. Blocks unless overruled with user sign-off.
   - **MEDIUM**: Degraded functionality, poor UX, tech debt. Should address; document if accepted.
   - **LOW**: Style, naming, speculative, perf without measured impact. Prompt Creator discretion.
3. **For each issue**: concrete failure scenario + suggested fix + cite specific plan lines
4. **Cross-plan dependency check**: Verify execution order (96→97→98→99) is correct
5. **Backend API verification**: For each S0.5 pre-verification item, flag if the assumed signature is wrong
6. **Other concerns** — open field for anything not covered above

Permitted: "Clean pass" if Rev1 is sound. Do not invent issues to fill space.
