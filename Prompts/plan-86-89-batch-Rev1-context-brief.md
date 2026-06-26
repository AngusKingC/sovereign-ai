# Batch Plans 86–89 — Round Table Review Brief
## Batch 2: Plans 86–89 | Rev1 (Post-Plan-85-Scan)

---

## Part 1: Roles/Rules

Your job is to find issues in this plan set, not rewrite it. Assume this plan set will fail in 6 months — identify the most plausible reasons. Each issue must include a concrete failure scenario and evidence from the codebase. Criticize my reasoning, not my conclusions. You may respond "No issues found" if the plan set is sound.

Ban: style comments, formatting preferences, speculative future features, performance optimizations without measured impact, re-raising issues already resolved in prior batches without new evidence.

---

## Part 2: Context

### What this batch covers

Four plans delivering PEMADS Phase 2–3, the real xterm.js terminal, and multi-channel approvals:

- **Plan 86** (Terminal + System Panels + Subagent UI): Replaces TerminalPlaceholder with real xterm.js terminal backed by `/ws/pty` WebSocket PTY endpoint. Adds SystemStatsPanel, SubagentPanel. Extends subagentStore. Adds `useWebSocket` hook (separate from `useSSE` — PTY is bidirectional).
- **Plan 87** (PEMADS Phase 2: Expert Panel Manager + VRAM): Builds `ExpertPanelManager` (manages expert worker pool for debates) and `VRAMManager` (standalone wrapper around `system.resource_manager.ResourceManager`). Integrates with existing `WorkerCircuitBreaker`, `ModelTierRouter`, `DebatePool`, `TaskClassifier`. Wires into Orchestrator via Optional injection.
- **Plan 88** (PEMADS Phase 3: Judge + Implementation Gate): Builds `PEMADSJudge` (evaluates debate quality using `TestingBatterySkill`, selects winner) and `ImplementationGate` (gates on quality threshold per TaskType + approval for medium-quality). Wires into Orchestrator after Plan 87's debate trigger.
- **Plan 89** (Multi-Channel Approvals): Builds `MultiChannelApprovalGate` (wraps `ApprovalGate`, fans out to Web + Telegram + Email). Builds `EmailGateway`. Implements `load_scopes` Postgres query (TODO from Plan 81). Frontend: Always Approve, batch actions, expiry countdown, channel indicator, toasts.

### Key dependencies

- Plan 87 depends on Plan 86 (SubagentPanel UI exists for expert panel monitoring)
- Plan 88 depends on Plan 87 (ExpertPanelManager produces debates for Judge to evaluate)
- Plan 89 depends on Plan 88 (ImplementationGate produces approval requests that multi-channel gate fans out)
- All plans depend on `prompt-85` (scan completed, baselines held)

### Post-scan state (Plan 85 completed 2026-06-26)

**Baselines held**: 1418 Python tests + 46 Vitest + 8 Playwright E2E, coverage 83%, mypy 0 errors, vulture 40 findings, ruff 0.

**Critical change**: Plan 85 **removed `resource_manager` from `MultiWorkerDispatcher`** entirely (was unused, caused 14 test failures due to missing attribute). The `ResourceManager` in `system/resource_manager.py` still exists and is fully built (1229 lines). Plan 87's `VRAMManager` is now a **standalone component** that wraps `ResourceManager` directly — it does NOT wrap `MultiWorkerDispatcher`.

### Author's reasoning (attack this, not the conclusion)

**Decision 1: VRAMManager as standalone wrapper, not MultiWorkerDispatcher extension.**
My reasoning: Plan 85 removed `resource_manager` from `MultiWorkerDispatcher` because it was unused and caused test failures. Rather than re-add it to `MultiWorkerDispatcher` (which would re-introduce the test failures), I'm building `VRAMManager` as a standalone component that `ExpertPanelManager` calls directly. This keeps `MultiWorkerDispatcher` clean (as Plan 85 left it) while giving PEMADS experts the VRAM management they need. The tradeoff: VRAM is now managed at the debate level (load all experts before debate, release all after), not per-worker-dispatch.

**Decision 2: ExpertPanelManager uses WorkerBase.execute() for solutions and critiques, not a new protocol.**
My reasoning: The existing `WorkerBase.run()` pipeline (MEMORY_QUERY → PROMPT_BUILT → LLM_CALLED → OUTPUT_FINAL) is well-tested and enforces tracing. Building a new PEMADS-specific protocol would duplicate this. The tradeoff: expert solutions are returned as `WorkerOutput` (string-like), not structured code. The Judge (Plan 88) will need to handle string-to-file conversion for TestingBatterySkill.

**Decision 3: ImplementationGate has 3 thresholds (auto-approve ≥90%, human approval 75-90%, reject <75%).**
My reasoning: This gives a smooth gradient — high-quality debates auto-implement (fast), medium-quality debates get human review (safe), low-quality debates auto-reject (no wasted implementation effort). The tradeoff: the 90% and 75% thresholds are arbitrary and may need tuning after real usage. I've made them class constants so they're easy to adjust.

**Decision 4: PTY endpoint uses `os.fork()` + `pty.openpty()` (Unix-only). Windows uses `pywinpty`.**
My reasoning: The PTY implementation must be platform-specific because there's no cross-platform PTY library in Python's stdlib. Detecting `sys.platform == "win32"` and branching to `pywinpty` is the standard pattern. The tradeoff: the Windows implementation is untested in this plan (Devin runs on Windows but the test suite runs on whichever platform the tests execute on). If `pywinpty` is not installed, the PTY endpoint will fail on Windows.

**Decision 5: MultiChannelApprovalGate wraps ApprovalGate rather than replacing it.**
My reasoning: `ApprovalGate` is heavily integrated (1166 lines, wired to orchestrator escalation path, Postgres persistence, trust registry). Replacing it would be a massive refactor. Wrapping it preserves all existing behavior while adding fan-out. The tradeoff: there are now two ways to request approval (direct `ApprovalGate.request_approval` and `MultiChannelApprovalGate.request_approval`). The orchestrator checks for `multi_channel_approval_gate` first, falls back to `approval_gate`.

### Confidence levels

| Decision | Confidence | Risk if wrong |
|----------|------------|---------------|
| VRAMManager standalone | 85% | Low — mirrors existing wrapper patterns |
| WorkerBase.execute for experts | 75% | Medium — string output may not suit TestingBattery |
| 3-threshold gate | 80% | Low — thresholds are class constants, easy to tune |
| PTY platform branching | 65% | High — Windows pywinpty untested |
| MultiChannel wraps ApprovalGate | 90% | Low — standard wrapper pattern |

### Open questions

1. **PTY Windows compatibility**: Will `pywinpty` install cleanly on Devin's Windows environment? If not, the terminal panel will fail to connect. Should the plan specify a fallback (e.g., disable PTY on Windows, show "Terminal not available on Windows" message)?

2. **Expert solution format**: `WorkerBase.execute()` returns `WorkerOutput` (which may be a string or a structured object). The Judge needs to write the solution to a `.py` file for TestingBatterySkill to run. Is the string-to-file conversion in the Judge robust enough, or should ExpertPanelManager save the solution to a file directly?

3. **Debate round selection**: The plan runs `max_rounds=3` rounds unconditionally. Should there be an early-exit condition (e.g., if all experts converge on the same solution in round 1, skip rounds 2-3 to save cost)?

4. **Telegram polling lifecycle**: The background polling task in `web/server.py` startup runs forever. Is there a shutdown handler to cancel it cleanly when the server stops? If not, the task may leak on restart.

5. **load_scopes Postgres query**: The plan implements the TODO from Plan 81, but assumes `memory_router.postgres_trace_store.fetch()` exists. Does it? If not, the query will fail silently (caught by except, logs warning, returns empty list).

---

## Part 3: Answer Format

Respond with:

1. **Verdict**: "Clean pass" OR "Issues found"
2. **If issues found, categorize**:
   - **HIGH** — would cause Devin STOP condition, test failure, broken build, data loss, security vulnerability, or Windows incompatibility. Blocks split.
   - **LOW** — style, naming, speculative future, perf without measured impact. Prompt Creator adjudicates.
3. **For each issue**: concrete failure scenario + suggested fix + cite specific plan lines
4. **Cross-plan dependency check**: Verify execution order (86→87→88→89) is correct and no circular dependencies exist
5. **Other concerns** — open field for anything not covered above

Permitted: "Clean pass" if Rev1 is sound. Do not invent issues to fill space.
