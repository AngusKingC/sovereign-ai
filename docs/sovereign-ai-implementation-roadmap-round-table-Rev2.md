# Sovereign AI Implementation Roadmap — Round Table Review Document
## 50 Candidate Implementations: Prioritization & Recommendation

**Date**: 2026-06-27
**Project State**: Plans 91–94 complete, Plan 95 scan pending. Batch 3 complete.
**Driving Document**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` (30 gaps → Plans 91–104)
**Review Scope**: Which of 50 researched implementations should enter the Sovereign AI codebase, in what order, and with what trade-offs.

**Rev2 changes**: (1) Updated project state — Plans 91–94 all complete. (2) Removed A6 (already done in Plan 94). (3) Fixed all file paths from `ui/components/` to `src/components/panels/`. (4) Added Plan 96 (Memory Backend) to dependencies. (5) Added kill switch + approval gate coordination to A4. (6) Added client-supplied idempotency key to A1. (7) Added 500ms debounce + rollback to B12 (then demoted to Tier C). (8) Merged B7+B8+B9 into single Security Layer. (9) Split A4 into A4a (manual) + A4b (auto-trigger). (10) Added trace store prerequisite to A7. (11) Added compatibility shim requirement to B1. (12) Added default permission fallback to B8. (13) Added atomic state storage spec to A3. (14) Added Windows Docker probe to B10. (15) Added C10 Windows scheduler prerequisite. (16) Added C3 eval harness prerequisite. (17) Demoted B11 to Tier C. (18) Added retention policy to A2. (19) Defined retry ownership for B1/B2/B6. (20) Added path sandbox to B9.

---

## PART 1: ROLES / RULES

- **Your job is to find issues, not rewrite the plan.** Identify gaps in reasoning, missing dependencies, or sequencing risks. Do not produce implementation code or alternative architectures.
- **Assume this roadmap will fail.** List the most plausible reasons why these implementations will cause Devin STOP conditions, test regressions, or Windows incompatibility.
- **Each issue must include a concrete failure scenario.** Vague concerns ("this might be slow") are banned. Cite a specific trigger and observable symptom.
- **You may answer "No issues found"** for any section. Do not invent problems to fill space.
- **Attack my reasoning, not my conclusion.** I state my reasoning in clearly labeled blocks. Criticize the logic that led to the priority, not the priority itself.
- **Substance only.** No style comments, no formatting preferences, no speculative future features beyond 2026-Q3.

---

## PART 2: CONTEXT

### 2.1 Plan Scope Summary

This document recommends which of 50 researched AI agent implementations (drawn from 2026 production practices) should be adopted into Sovereign AI. The recommendations are organized into four tiers:

- **TIER A — Must Implement**: Blocks current plan execution or closes a documented UI-UX gap. These are prerequisites for Plans 93–104.
- **TIER B — Should Implement**: Significant reliability, security, or cost benefits. No documented blockers, but high value.
- **TIER C — Could Implement**: Valuable but can be deferred. Either depends on Tier B work or addresses lower-priority gaps.
- **TIER D — Won't Implement (Now)**: Interesting but misaligned with current architecture, too risky for Windows, or superseded by existing patterns.

### 2.2 Key Dependencies

- **Plan 91** (Model & Adapter Management) — COMPLETE. Created `ModelsPanel.tsx`, `modelStore.ts`, wired `api/models.py` to `ModelRegistry`.
- **Plan 92** (Model Downloader + Fallback Chain) — COMPLETE. Created `ModelDownloader.tsx`, fallback chain endpoints, approval gate for >1GB downloads.
- **Plan 93** (Worker Creation & Configuration) — COMPLETE. Created `WorkerCreator.tsx`, `WorkerEditor.tsx`, wired `api/workers.py` to `WorkerFactory`. Note: `test_list_workers` was skipped due to Pydantic serialization bug — Plan 95 scan will fix.
- **Plan 94** (Cost & Resource Controls) — COMPLETE. Un-mocked SettingsDrawer, created `ResourceMonitorPanel.tsx`, added cost policy API.
- **Plan 95** (5-Plan Milestone Scan) — PENDING. Must run before Batch 4 (96–99) begins.
- **Plan 96** (Memory Backend + UI) — QUEUED. Implements multi-backend memory (SQLite FTS5 + Kuzu Graph) with 3 UI panels. Reference: `docs/Memory-Backend-Modules-UI-Integration-Reference.md`.
- **AGENTS.md rules AR1–AR21, OR1–OR39** are always-on. Any new implementation must comply.
- **Git Bash is the shell** (not PowerShell — switched in Plan 91 post-mortem). All commands use Unix syntax.
- **Windows is the primary dev environment.** Any implementation requiring Linux-only kernel features (cgroups v2, eBPF, Firecracker) must have a Windows fallback or be Tier D.

### 2.3 Author's Reasoning (Attack This)

**My reasoning for Tier A prioritization:**

> The UI-UX Gap Analysis (Plan 90 output) identified 30 gaps. Plans 91–104 were explicitly designed to close them. Therefore, any implementation that directly closes a documented gap (e.g., Session Manager for Gap §2.9, Resource Dashboard for Gap §3.4) gets Tier A automatically. Anything not on the gap list but critical for reliability (e.g., Idempotency Keys, Kill Switch) gets Tier A because the gap list was UI-focused and missed operational safety.

**My reasoning for Tier B prioritization:**

> Sovereign AI's core philosophy is "strong, robust, modular, simple core." Tier B items (circuit breakers, backoff, audit trails) make the core robust without adding new horizontal capabilities. They are force-multipliers for everything built on top. I excluded anything that requires new infrastructure (microVMs, voice pipelines) from Tier B because those are new horizontal capabilities, not core hardening.

**My reasoning for Tier D:**

> MicroVM sandboxing (Firecracker) requires Linux kernel features unavailable on Windows. Sovereign AI's primary dev environment is Windows (Devin Desktop). Adding a Linux-only execution path would violate AR19 (Docker sandbox) and create a platform split. This belongs in a future "Linux deployment mode" plan, not now. Similarly, Representation Engineering (RepE) requires model-level access to internal activations — impossible with API-only models and overkill for a local-first framework.

**My confidence levels:**
- Tier A recommendations: **90% confident** — these are either gap-closers or obvious safety holes.
- Tier B recommendations: **75% confident** — valuable but some may overlap with existing patterns I haven't fully mapped.
- Tier C recommendations: **55% confident** — these are speculative. I may be over-indexing on research trends.
- Tier D exclusions: **85% confident** — the Windows constraint is hard, but I may be being too conservative on microVMs.

### 2.4 Named Open Questions for Reviewers

1. **Does the Kill Switch (#7) conflict with the approval gate system?** If a task is mid-approval and the kill switch fires, what happens to the pending approval state? Is there a risk of orphaned database rows?

2. **Is Idempotency (#8) actually needed before Plan 94?** Cost controls (Plan 94) will add spend caps. If a write operation retries and burns tokens, the spend cap catches it. Does idempotency add value beyond what the spend cap already provides?

3. **Should Semantic Caching (#23) be Tier A instead of Tier C?** The Gap Analysis doesn't mention caching, but Galileo.ai research shows 60–80% token reduction. Is the implementation cost (Qdrant embedding storage, similarity thresholds, TTL eviction) worth the savings given Sovereign AI's current low usage volume?

4. **Does the A2A Protocol (#41) compete with or complement the existing `core/a2a_protocol.py`?** The current module is skeletal. Is full A2A compliance a distraction from the gap-closing work, or is it necessary for the "multi-agent" vision in CONTEXT.md?

5. **Is the Reflection Loop (#31) compatible with Sovereign AI's "no training" constraint?** The framework uses frozen models (local + cloud APIs). Reflection requires the agent to modify its own behavior. Can this be done purely through prompt/context manipulation without violating the frozen-model policy?

6. **Will Configuration Hot-Reload (#46) break Windows file watchers?** Python's `watchdog` library has known issues with Windows network drives and rapid-fire events. Is the dual-trigger (poll + notify) pattern sufficient, or will it cause false reloads on Windows?

7. **Should Tool Privilege Scoping (#14) be implemented as a Pydantic schema or a runtime capability check?** If we use Pydantic, we get static validation. If we use runtime checks, we get flexibility. Which approach is less likely to cause a Devin STOP condition on Windows?

8. **Does Multi-Tier Memory (#27) require a schema migration that Plan 95 (the scan) can't handle?** If we split memory into STM/LTM/Archive, the existing SQLite schema for `MemoryRouter` changes. Is this a "structural problem requiring design decisions" (scan STOP condition) or a mechanical migration?

---

## PART 3: TIERED RECOMMENDATIONS

### TIER A — MUST IMPLEMENT
*These close documented UI-UX gaps or address operational safety holes. Implement in Plans 95–96 or immediately after Plan 95 scan.*

| # | Implementation | Gap / Blocker | Files Touched | Risk |
|---|-----------------|---------------|---------------|------|
| **A1** | **Idempotency Keys for Write Operations** (#8) | Plan 93 created workers without idempotency — retries could duplicate workers. Retrospective fix. | `core/orchestrator.py`, `core/idempotency_store.py`, `api/workers.py` | LOW — SQLite append-only table. **Rev2 H1 fix**: Client MUST supply `Idempotency-Key` header on write requests. Server stores key + response. Retries with same key return cached response. |
| **A2** | **Audit Trail for High-Value Agent Decisions** (#15) | No decision audit exists. Required for trust and debugging. Closes implicit gap in Gap Analysis §2.8 (trace viewer needs data). | `core/audit_log.py`, `api/audit.py`, `src/components/panels/AuditViewerPanel.tsx` | LOW — append-only log. **Rev2 M4 fix**: Scope to high-value events only (tool calls, approvals, model switches, kill-switch fires, cost alerts). Add 30-day retention + rotation. Do NOT log every LLM token. |
| **A3** | **Rate Limiting per Tool per Session** (#17) | Plan 94 (Cost Controls) shipped without per-tool limits. Spend caps catch cost but not rate. | `core/rate_limiter.py`, `core/cost_tracker.py`, `api/cost.py` | LOW — token bucket. **Rev2 H6 fix**: Store full bucket state (tokens + last refill timestamp) atomically in SQLite, not split between memory and DB. On restart, reload from SQLite — no state loss. |
| **A4a** | **Kill Switch — Manual Only** (#7, Phase 1) | No emergency stop. Must exist before any autonomous work. | `core/kill_switch.py`, `api/system.py`, `src/components/shell/StatusBar.tsx` (button) | LOW — API endpoint + button. Manual trigger only, no auto-trigger logic. |
| **A4b** | **Kill Switch — Auto-Trigger** (#7, Phase 2) | Auto-trigger on runaway tasks. Depends on A4a. | `core/kill_switch.py` (extend) | MEDIUM — **Rev2 C1 fix**: Kill switch MUST call `approval_gate.revoke_all_pending()` before halting. This transitions all pending approvals to KILLED state and removes them from `_pending_requests`. Prevents orphaned approval rows. |
| **A5** | **Session Manager** (#50) | Gap Analysis §2.9: "No session UI." Critical for multi-project workflow (media/sailing/CNC). | `src/components/panels/SessionManagerPanel.tsx`, `api/sessions.py`, `core/session_store.py` | LOW — extends existing session concept, SQLite-backed. **Rev2 MI-2 fix**: Store session metadata in SQLite, transcripts as files on disk (not BLOBs) to prevent DB bloat. |
| **A7** | **Trace Viewer with Search/Filter** (#49) | Gap Analysis §2.8: "Currently no trace UI." | `src/components/panels/TraceViewerPanel.tsx`, `api/traces.py` | LOW — read-only. **Rev2 H3 fix**: Verify trace store exists (`memory/postgres_trace_store.py` or `core/observability.py`). If trace store is skeletal, A2 (Audit Trail) must be completed first to feed data. |
| **A8** | **Notification Center** (#44) | Currently ad-hoc notifications. Required for approval gates, cost alerts, system events. | `src/components/panels/NotificationCenterPanel.tsx`, `core/notification_center.py`, `api/notifications.py` | LOW — **Rev2 C5 fix**: Before implementation, audit whether Telegram/Email gateways are actually wired and configured. If gateways are absent, A8 is a no-op passthrough that logs to audit trail (A2) rather than pretending to notify. Do not silently swallow alerts. |

### TIER B — SHOULD IMPLEMENT
*Significant reliability/security/cost benefits. Implement in Batch 4 (Plans 96–99) after Plan 95 scan.*

| # | Implementation | Value Proposition | Effort | Confidence |
|---|---------------|-------------------|--------|------------|
| **B1** | **Multi-Scope Circuit Breaker** (#1) | Prevents cascade failures across 15 adapters. Extends existing `WorkerCircuitBreaker`. | MEDIUM — **Rev2 H4 fix**: Refactor into hierarchy but KEEP old `WorkerCircuitBreaker` class as compatibility shim for one release cycle. Existing tests must not break. Define clear retry ownership: adapter = immediate retry, orchestrator = cross-adapter fallback, circuit breaker = fail-fast. | 80% |
| **B2** | **Jittered Exponential Backoff** (#2) | Prevents thundering herd. Retry budgets prevent runaway token spend. | LOW — extends existing retry logic. **Rev2 M2 fix**: B2 owns adapter-level retry only. B1 owns circuit-breaker-level. B6 owns orchestrator-level. No compounding. | 85% |
| **B3** | **Policy-Aware Circuit Breaker** (#3) | Fail-open for reads, fail-closed for writes. Matches approval gate philosophy. | LOW — enum + audit tag addition | 90% |
| **B4** | **Step-Count Ceiling + Token Budget** (#6) | Covers 90% of runaway scenarios. Hard stop before cost cap triggers. | LOW — counter in task context | 85% |
| **B5** | **Semantic Loop Detection** (#5) | Catches reflection loops that burn tokens. Auto-escalates. | MEDIUM — **Rev2 M1 fix**: Configurable threshold (default 0.95, not 0.92). Require similarity across at least 3 consecutive turns before escalation. Add UI slider in Agent Health panel for tuning. Log similarity scores for post-hoc analysis. | 70% |
| **B6** | **Hierarchical Retry Strategy** (#4) | 99.95% operational continuity. Matches layered architecture. | MEDIUM — RetryCoordinator class. **Rev2 M2 fix**: B6 owns orchestrator-level cross-adapter retry only. Does NOT compound with B1/B2 — each layer has its own retry budget. | 75% |
| **B7** | **Security Layer (Merged: Prompt Injection Defense + Tool Privilege Scoping + Content Safety Filter)** (#12, #14, #19) | OWASP #1 threat defense. **Rev2 merge**: Three concerns implemented as single epic for consistent trust model. Layers: (1) Input sanitization + TrustTier enum, (2) SkillPermission per-skill scoping with **default USER_APPROVED for unannotated skills** (Rev2 H5 fix — legacy skills must not break), (3) Output validation with **path sandbox allowlist + command injection check** (Rev2 M3 fix — Pydantic validates shape, not semantic safety). | MEDIUM-HIGH | 80% |
| **B10** | **Sandbox Resource Quotas** (#20) | CPU/RAM/Network/Time limits per sandbox. Prevents host resource exhaustion. | MEDIUM — **Rev2 H7 fix**: Docker `--memory`/`--cpus` flags may not enforce on Windows Docker Desktop. Add Windows capability probe (`docker info` check). Fall back to process-level limits / job objects when Docker quotas unenforceable. | 75% |

### TIER C — COULD IMPLEMENT
*Valuable but deferrable. Depends on Tier B work or addresses lower-priority gaps.*

| # | Implementation | Deferral Reason | Prerequisite |
|---|---------------|-----------------|--------------|
| **C1** | **Knowledge Graph Memory** (#21) | Adds relationship reasoning. **Rev2 H8 fix**: Plan 96 (Memory Backend) already implements Kuzu Graph — re-evaluate after Plan 96 completes. May be partially redundant. | Plan 96 complete, usage volume justifies complexity |
| **C2** | **Progressive Summarization** (#22) | 60–80% token reduction. But low usage volume means savings are small now. | CostTracker showing high token spend |
| **C3** | **Semantic Caching** (#23) | Major cost reduction. **Rev2 M6 fix**: Requires eval harness or golden QA set to tune similarity threshold. Do NOT ship without measured false-positive rate — wrong answers for similar-but-distinct prompts is worse than no cache. | Eval harness complete + CostTracker baseline |
| **C4** | **Taste Memory with Exponential Decay** (#24) | Preference drift prevention. Niche feature for rating system. | RatingSystem stable in production |
| **C5** | **Session Search** (FTS5) (#25) | "How did I solve X?" Requires transcript indexing. **Rev2 H8 fix**: Plan 96 implements FTS5 — re-evaluate after Plan 96. May be partially redundant. | Session Manager (A5) + Plan 96 complete |
| **C6** | **Memory Attribution Badges** (#28) | UI transparency. **Rev2 L1 fix**: Partially completed — Plan 91 has model adapter badges, Plan 96 has memory search backend badges. Remaining: provenance tracking in MemoryRouter. | Plan 96 complete + MemoryRouter provenance tracking |
| **C7** | **A2A Protocol Compliance** (#41) | Interoperability. But current `a2a_protocol.py` is skeletal and unused. | Multi-agent use case actually needed |
| **C8** | **MCP Server Support** (#42) | Universal plugin protocol. But Sovereign AI's skill registry is custom and working. | Plugin ecosystem demand |
| **C9** | **Extension Point Architecture** (#47) | Stricter plugin model. Overkill while skill count is <20. | Skill count >20 or community plugins requested |
| **C10a** | **Cron Scheduler + UI** (#45, Phase 1) | Proactive intelligence — scheduler only. | A4a (manual kill switch) + A2 (audit trail) + A3 (rate limiting) complete |
| **C10b** | **Cron Job Execution Context** (#45, Phase 2) | Execution metadata for audit trail. **Rev2 H3 fix**: Add `execution_metadata: {trigger: 'cron'|'user', cron_id, scheduled_time}` to task context. **Rev2 M5 fix**: Windows scheduler persistence — APScheduler with persistent job store + misfire grace time. Without this, Windows sleep/wake causes missed-then-burst execution. | C10a complete + Windows scheduler validated |
| **C11** | **Compensating Transaction Pattern** (#16) | Multi-step rollback. Currently no multi-step workflows that need it. | Complex multi-step tasks |
| **C12** | **Secrets Rotation** (#18) | Security best practice. But detect-secrets baseline (Plan 71) is manual. | Automated secret detection first |
| **C13** | **Configuration Hot-Reload** (#46, demoted from B12) | **Rev2 demotion**: Highest Windows risk (3 panels flagged). No gap closure. **If implemented**: 500ms debounce, hash stability across 2 consecutive polls, Pydantic validation before apply, automatic rollback to last known good config on validation failure. | Windows file watcher test matrix passed |
| **C14** | **Agent Health Scorecard** (#10, demoted from B11) | **Rev2 demotion**: Requires stable telemetry baseline that doesn't exist yet. Shipping now risks UI full of unactionable badges. | Telemetry schema + SSE infrastructure stable |

### TIER D — WON'T IMPLEMENT (NOW)
*Misaligned with current architecture, too risky for Windows, or superseded.*

| # | Implementation | Exclusion Reason | Revisit Condition |
|---|---------------|------------------|-----------------|
| **D1** | **MicroVM Sandbox** (#11) | Requires Linux kernel features (Firecracker/gVisor). Windows primary dev env. | Linux deployment mode added |
| **D2** | **Representation Engineering** (#13) | Requires model-level activation access. Impossible with API-only models. | Local model with activation hooks |
| **D3** | **Real-Time Voice Interface** (#43) | New horizontal capability. Not on gap list. Requires STT/TTS infrastructure. | User explicitly requests hands-free mode |
| **D4** | **Self-Play Training** (#34) | Requires model fine-tuning infrastructure. Violates frozen-model policy. | Self-hosted training pipeline |
| **D5** | **DSPy Meta-Prompting** (#33) | Requires eval harness + optimization loop. Sovereign AI has no eval harness yet. | EvalHarness (Plan 97+) complete |
| **D6** | **Multi-Agent Reflection** (#32) | Requires multiple agent instances reflecting. Overkill for single-user system. | Multi-agent mode enabled |
| **D7** | **Canary Deployment** (#38) | Requires traffic splitting + metric monitoring. Single-user system has no traffic to split. | Multi-user or high-volume deployment |
| **D8** | **Conversation Isolation** (#29) | Single-user system. No cross-session contamination risk today. | Multi-user support added |
| **D9** | **Graceful Degradation Chain** (#9) | `ModelTierRouter` already exists (Plan 79). Adding explicit degradation modes is polish, not critical. | ModelTierRouter causing hard failures |
| **D10** | **Weekly Retrospective** (#37) | Nice-to-have. Can be done manually via existing task history. | Cron jobs (C10) implemented |
| **D11** | **Feedback Loop to Eval Harness** (#39) | No eval harness exists. Circular dependency. | EvalHarness complete |
| **D12** | **Karpathy Loop** (#40) | Self-improvement loop. Requires verifiable outcomes + eval harness. | EvalHarness + self-improvement use case |
| **D13** | **Lesson Loop** (#35) | Writable memory layer. Overlaps with Reflection Loop but simpler. | Reflection Loop (#31) proves too complex |
| **D14** | **A/B Test Framework** (#36) | No traffic to split. Single-user system. | Multi-user or high-volume |
| **D15** | **Incremental Knowledge Graph Sync** (#26) | File watcher + graph updates. Complex, benefits unclear at current scale. | Codebase >10k files |
| **D16** | **Multi-Tier Memory** (#27) | Schema migration risk. **Rev2 H8 fix**: Plan 96 implements multi-backend memory with tiered backends (Tier 1 FTS5/Kuzu, Tier 2 Qdrant/Postgres). Re-evaluate after Plan 96 — may be partially redundant. | Plan 96 complete + memory performance issues |
| **D17** | **Memory Nudge System** (#30) | Proactive memory surfacing. Niche feature, hard to evaluate. | Taste Memory (C4) shows value |
| **D18** | **Reflection Loop** (#31) | Requires eval rubric + external ground truth. Sovereign AI has neither. | EvalHarness + rubric library |

---

## PART 4: SEQUENCING & DEPENDENCY MAP

```
Plan 93 (Worker Creation) ──┬──► A1 (Idempotency) ──► A2 (Audit Trail)
                            │
Plan 94 (Cost Controls) ────┼──► A3 (Rate Limiting) ──► B4 (Token Budget)
                            │
Plan 95 (Scan) ─────────────┘
                            │
                            ▼
Batch 4 (96–99) ────────────┬──► B1–B6 (Resilience Stack)
                            ├──► B7–B9 (Security Layer)
                            ├──► B10 (Sandbox Quotas)
                            ├──► B11 (Health Scorecard)
                            └──► B12 (Hot-Reload)
                            │
                            ▼
Post-100 (Research) ────────┬──► C1–C3 (Memory Enhancements)
                            ├──► C4–C6 (Search & Attribution)
                            ├──► C7–C9 (Protocol & Architecture)
                            └──► C10–C12 (Jobs & Transactions)
```

**Critical Path Risk**: If A4 (Kill Switch) is not implemented before C10 (Cron Jobs), autonomous scheduled tasks have no emergency stop. This is a **CRITICAL** sequencing violation.

**Windows Risk**: B12 (Hot-Reload) uses `watchdog` which has known Windows file system event quirks. Must include Windows-specific test coverage.

---

## PART 5: ANSWER FORMAT

Please review each tier and respond with:

1. **Critical Issues** (data loss, security vulnerability, irreversible damage) — block adoption
2. **High Issues** (Devin STOP, test failure, Windows incompatibility) — must resolve
3. **Medium Issues** (degraded functionality, technical debt) — should address
4. **Low Issues** (style, naming, speculative future) — optional

For each issue, provide:
- Concrete failure scenario (what trigger, what symptom)
- Evidence from the codebase (file name, function, or AGENTS.md rule violated)
- Suggested fix or acceptance rationale

Include an **"Other Concerns"** section for anything not covered above.

You may also:
- **Promote** a Tier C/D item to Tier A/B with justification
- **Demote** a Tier A/B item to Tier C/D with justification
- **Merge** two implementations if they overlap
- **Split** one implementation if it's actually two concerns

---

## ADJUDICATION LOG

*To be filled by Prompt Creator after round table review.*

| Issue ID | Severity | Finding | Adopted? | Reasoning |
|----------|----------|---------|----------|-----------|
| | | | | |

---

*Document version: Rev1*
*Prompt Creator confidence in overall roadmap: 75%*
*Pre-mortem assumption: This roadmap fails because we underestimated the Windows file watcher complexity for B12 and the schema migration risk for C6.*
