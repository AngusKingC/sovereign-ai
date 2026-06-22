# Sovereign AI Agent Framework — Project Handoff

**Last updated**: 2026-06-22 — post-prompt-60 (5-plan milestone full scan + L25 landmine rename L→M + M26 PowerShell-corruption landmine)

**Repository**: https://github.com/AngusKingC/sovereign-ai
**Default branch**: `master`
**Clone (Devin, Windows)**: Devin's local working copy (path managed by Devin Desktop)
**Clone (GLM, review sandbox)**: `/home/z/my-project/sovereign-ai-framework/` (Linux; optional deps NOT installed — see L19)
**`origin` remote**: points to the GitHub repo above. All `git push origin` / `git pull origin` commands target this repo.

---

## Start here (for a new GLM chat receiving this handoff)

If you are a new GLM chat and the user has pasted this handoff + a Devin execution log, follow this sequence:

1. **If the repo is not cloned in your sandbox, clone it now:**
   ```bash
   git clone https://github.com/AngusKingC/sovereign-ai.git /home/z/my-project/sovereign-ai-framework
   ```
   (If it's already cloned, `cd /home/z/my-project/sovereign-ai-framework && git fetch origin` to get the latest.)

2. **⚠ L19 (critical — read before doing anything):** GLM must NOT run `mypy`, `bandit`, `pytest`, `pip-audit`, or `vulture` on its clone. Counts come from Devin's execution log only. Different OS, different Python env, different tool versions give false confidence. GLM's clone is for reading files (line numbers, content, structure) and `git fetch`/`git show`/`git log` (read-only) — NOT for running tools.

3. **Start the [GLM workflow](#glm-workflow) at Step 1.** Read the pasted execution log end-to-end, then proceed through Steps 2-8 in order.

4. **Do not edit the repo directly.** GLM produces files in `/home/z/my-project/download/` for the user to copy to Devin's working tree. See [Roles](#roles) for the full separation rules.

---

**Test baseline**: 1166 passed, 56 skipped (verified at Plan 60 S1.1 — 5-plan milestone full scan)

---

## Table of contents

0. [Start here](#start-here-for-a-new-glm-chat-receiving-this-handoff) — onboarding for a new GLM chat (clone, L19 reminder, where to begin)
1. [Repository & environment](#repository--environment) — repo URL, clone paths, Python version, OS, optional deps
2. [Project vision](#project-vision)
3. [What works right now](#what-works-right-now)
4. [What's broken right now](#whats-broken-right-now)
5. [What's built but not reachable](#whats-built-but-not-reachable)
6. [What's deferred (not started)](#whats-deferred-not-started)
7. [Roles](#roles) — who does what (GLM vs Devin vs User)
8. [GLM workflow](#glm-workflow) — GLM's 7-step post-execution process
9. [Devin plan template](#devin-plan-template) — opening + closing steps GLM copies into every plan
10. [Architecture rules](#architecture-rules-never-violate)
11. [Dependency injection rules](#dependency-injection-rules)
12. [Completed prompts](#completed-prompts)
13. [Known landmines](#known-landmines)
14. [Hardware context](#hardware-context)
15. [Environment](#environment) — Python version, install/run commands, optional deps
16. [User domain context](#user-domain-context)
17. [Next 5 prompts](#next-5-prompts)

---

## Repository & environment

- **Repo**: https://github.com/AngusKingC/sovereign-ai (GitHub, private)
- **Default branch**: `master`
- **Tags**: `prompt-{N}` for each completed plan (e.g. `prompt-58.7`). Tag-push gate is mandatory (L5/L17/Rule 21).
- **Clone (Devin)**: Windows local path managed by Devin Desktop. All plan execution happens here.
- **Clone (GLM review)**: `/home/z/my-project/sovereign-ai-framework/` on Linux sandbox. Used for read-only verification (line numbers, file existence, ruff/bandit counts). **Cannot run pytest** — optional deps not installed (see L19).
- **`origin` remote**: always refers to the GitHub repo above.

---

**Static analysis baseline (post-prompt-60 — 5-plan milestone full scan)**:
- Ruff: 0 errors (was 0 — Plan 59 cleanup held)
- Mypy (full-repo): 277 errors in 67 files (was 283 — Plan 60 5-plan milestone recapture; delta of -6 within acceptable range)
- Bandit: 3179 low, 0 medium, 0 high (Plan 59 suppressed all 22 B108; Plan 60 verified clean)
- pip-audit: 19 CVEs across 4 packages (was 19 — Plan 60 5-plan milestone recapture)
- Vulture: 22 high-confidence findings (was 20 — Plan 60 5-plan milestone recapture; delta of +2 within acceptable range)

<!-- NOTE TO DEVIN: Replace each <S1.x actual> placeholder above with the actual count captured at Plan 60 S1.x. Delete this comment after filling in. -->

**Devin rules**: **Devin Desktop config (2026-06-22)** — three layers of rules/tools:
1. **AGENTS.md** (repo root, always-on): 23 stable rules across 6 categories (rules 1-21 original + rule 22 bandit count + rule 23 Edit-tool-only for structured markdown — both added by Plan 60). Devin Desktop auto-discovers this.
2. **Section 0** (per-plan, evolving): L1-L26 rules that grow via L20 self-evolution (Devin proposes via C9, GLM accepts/rejects). Canonical source: `globalrules/global_rules_v2.md` in this repo (v2.4, 25 rules — Plan 59 Section 0 extended to L26, the repo copy will catch up at next docs sync).
3. **Workflows + Skills** (`.windsurf/` directory):
   - `/jarvis-close` — full C1-C13 closing sequence (prevents "forgot to tag")
   - `/jarvis-verify` — post-edit syntax + diff + test checks
   - `/jarvis-scan` — sequential 6-tool full scan (L24 enforced)
   - `jarvis-b108-suppress` skill — auto-invoked on B108 bandit findings
   - `jarvis-f841-triage` skill — auto-invoked on F841 ruff findings
The `/globalrules/` folder is reference-only (frozen Plan 54 snapshot).

---

## Project Vision

A local-first, self-improving AI assistant for one user's specific context: media production, sailing, 3D printing, CNC machining. Runs locally by default, escalates to cloud when the task demands it, monitors open-loop background tasks (weather, AIS, email) and interrupts only when necessary.

**Core philosophy**: Strong, robust, simple core. Wire as you go. No new horizontal capability until the existing stack is reachable and demonstrably improving worker outputs.

---

## What works right now

- **`jarvis`** (no args) — starts Textual TUI with full cognition stack wired. User can type queries, get responses from local Ollama. Memory is stateful across queries.
- **`jarvis "query"`** — non-interactive single-query mode via Rich CLI.
- **`jarvis --rich`** — Rich-based interactive CLI with slash commands.
- **`jarvis --setup` / `--reconfigure` / `--doctor`** — SetupWizard runs, writes config + `.env`, doctor checks Ollama/Postgres/Qdrant/Obsidian reachability.
- **`jarvis serve`** — starts FastAPI server. Accepts task submissions via POST /api/tasks, returns worker listings via GET /api/workers.
- **TUI slash commands** — `/help`, `/status`, `/clear`, `/exit`, `/model`, `/adapter`, `/theme` work. `/adapter` supports 10 adapters.
- **Session manager** — in-memory mode works. Postgres persistence does not.
- **Command history** — in-memory mode works. Postgres persistence does not.

---

## What's broken right now

> **Note**: Previously tracked issues F4 and F9 have been resolved. Kept here for historical context — see "What's built but not reachable" for currently-dormant subsystems.

### F4 — `cli/serve.py` cognition-loop wiring (RESOLVED by Plan 52)
- **Was**: Subsystems constructed with `_` prefix (Plan 46) to silence F841, never wired into request path.
- **Fix (Plan 52)**: `worker_factory`, `output_evaluator`, `trace_optimiser` wired into orchestrator loop in `cli/serve.py` and `cli/tui.py`.
- **Remaining**: `TrajectoryExporter` still dormant — see "What's built but not reachable" table below. Wiring deferred to a future plan (not Plan 52, which is complete).

### F9 — Dependency CVEs (PARTIALLY RESOLVED by Plan 56)
- **Was**: 55 dependency CVEs across 14 packages.
- **Fix (Plan 56)**: 11 packages upgraded, 36 CVEs fixed. pip-audit: 55→19 CVEs.
- **Remaining**: 19 CVEs across 4 packages — deferred pending upstream patches (Starlette blocked by FastAPI incompatibility, chromadb/diskcache no confirmed fixes). Run `pip-audit` for current list.

---

## What's built but not reachable

| Subsystem | File | Why it's dormant |
|---|---|---|
| MultiWorkerDispatcher | `core/multi_worker.py` | Never constructed anywhere |
| A2ARouter | `core/a2a_protocol.py` | Same |
| MonitorDaemon | `system/monitor_daemon.py` | Same |
| VoiceDaemon | `system/voice_daemon.py` | Same |
| TelegramGateway | `gateways/telegram/gateway.py` | Same |
| RetentionDaemon | `system/retention_daemon.py` | Same |
| RetentionManager | `system/retention_manager.py` | Same |
| TriggerEngine | `core/event_trigger.py` | Same |
| NotificationSystem | `core/notification.py` | Same |
| ResourceBudget | `core/resource_budget.py` | Same |
| VerbosityManager | `core/verbosity.py` | Same |
| TrajectoryExporter | `system/trajectory_exporter.py` | Functional (prompt-45) but not reachable. Wiring NOT done in Plan 52 (Plan 52 wired cognition loop only). Deferred to a future plan. |
| MemoryCompactor | `core/memory_compactor.py` | Same |
| MCPServer | `skills/mcp_server.py` | Built but never started |
| MCPAdapter | `adapters/mcp_adapter.py` | Built but never constructed |
| MarineWeather (SKILL.md) | `skills/marine/weather/SKILL.md` | Spec only — no Python implementation yet (Plan 61) |
| MarineAIS (SKILL.md) | `skills/marine/ais/SKILL.md` | Spec only — no Python implementation yet (Plan 61) |
| MarineTidal (SKILL.md) | `skills/marine/tidal/SKILL.md` | Spec only — no Python implementation yet (Plan 61) |
| MarinePassagePlanner (SKILL.md) | `skills/marine/passage_planner/SKILL.md` | Spec only — no Python implementation yet (Plan 61) |

When a subsystem is wired into a runtime entry point, remove it from this table.

---

## What's deferred (not started)

1. **Marine stack Python implementation** — weather, AIS, tidal, passage_planner. SKILL.md specs exist (created Plan 55). Implement as Python skills — Plan 61.
2. **Sandboxed execution** for `skills/terminal/` and `skills/code_execution/`. Currently runs subprocesses on host.
3. **Streaming output** from Ollama through worker pipeline to TUI/Web GUI.
4. **Function-calling / tool-use loop.** Route-once-generate-once is a generation behind.
5. **Deployment story.** Docker compose with Postgres + Qdrant + Jarvis + Ollama.
6. **Eval harness.** Held-out task suite to measure self-improvement.
7. **Plan mode.** Agent proposes, user approves, agent executes.

---

## Roles

Three actors collaborate on this project. Each has a distinct job — do not cross the lines.

| Actor | Job | Tools |
|---|---|---|
| **User** | Pastes Devin's execution log to GLM after each prompt. Copies GLM's download files to Devin's working tree when review fixes are needed. | IM chat with GLM; file copy on Devin's machine. |
| **GLM** (this AI) | 7-step post-execution workflow (see [GLM workflow](#glm-workflow)). Creates plans, review guides, and revised plans. **Never edits the repo directly** — produces files in `/home/z/my-project/download/` for the user to copy. | `git fetch origin`, `git show`, `git log` (read-only). No push, no commit, no tool runs on clone (L19). |
| **Devin** | Executes plans. Runs tests, ruff, mypy, bandit, pip-audit, vulture. Commits, tags, pushes. Updates CHANGELOG, handoff, and proposes rules. | PowerShell on Windows; the repo's working tree. |

**Key separation rules:**
- GLM does NOT commit to or push to the repo. GLM does NOT directly modify Devin's local working tree. GLM MAY produce edited copies of repo files (CHANGELOG.md, SOVEREIGN_AI_HANDOFF.md, AGENTS.md) in `/home/z/my-project/download/` for the user to manually copy to Devin's working tree. The user is the bridge — GLM never touches origin or Devin's filesystem directly. Devin does the actual commits (closing steps 7-10).
- GLM does NOT run pytest/mypy/ruff/bandit/pip-audit/vulture on its clone (L19). Counts come from Devin's execution log.
- Devin does NOT create plans or review guides. GLM does.
- The user is the bridge — copies files between GLM's download folder and Devin's working tree.

---

## GLM workflow

When the user pastes a Devin execution log, GLM follows these 7 steps in order. Do not skip steps. Do not improvise.

### Step 1 — Read the pasted execution log

The user's paste IS the execution log. It contains every command Devin ran, every output, every error, every STOP condition. Read it end-to-end before doing anything else. Extract:
- Actual test count, ruff count, mypy count, bandit count, pip-audit count, vulture count
- Any STOP conditions triggered
- Any rule proposals Devin submitted (C9)
- Any deviations from the plan (scope creep, silent skips, etc.)

### Step 2 — Check the latest repo to verify Devin followed the prompt correctly

```bash
git fetch origin
git log --oneline origin/master -5
git show origin/master:CHANGELOG.md | sed -n '/prompt-{N}/,/^## /p' | head -30
git ls-remote --tags origin | grep prompt-{N}
```

Verify:
- The prompt's tag exists on origin (e.g. `prompt-59`)
- The CHANGELOG entry matches what Devin reported in the execution log
- The commit stat matches the files the plan said to touch (no scope creep)
- The handoff's "Completed prompts" table has the new row
- The handoff's baselines are updated
- The "Next 5 prompts" queue is refilled

If anything doesn't match, flag it to the user — Devin may have deviated from the plan.

### Step 3 — Read the handoff to remind yourself how to make prompts

Re-read these sections every time:
- [Start here](#start-here-for-a-new-glm-chat-receiving-this-handoff) — the onboarding block at the top (clone if needed, L19 reminder)
- [Roles](#roles) — confirm who does what
- [GLM workflow](#glm-workflow) — this section
- [Devin plan template](#devin-plan-template) — the opening + closing steps to copy into the new plan
- [Known landmines](#known-landmines) — avoid repeating past mistakes
- [Completed prompts](#completed-prompts) — what's been done, what patterns emerged
- [Next 5 prompts](#next-5-prompts) — what's queued next

**Also read from the repo (not the handoff):**
- `AGENTS.md` — the 22 stable rules Devin auto-discovers. Read this before Step 4 (creating new AGENTS.md rules) so you don't propose duplicates. Get it via `git show origin/master:AGENTS.md` or read from your clone at `AGENTS.md`.
- The previous plan's Section 0 (L1-L26 evolving rules). Plans live in `GLM Prompts/{decade}s/plan-{N-1}.md` in the repo, where `{decade}` is the floor of the plan number divided by 10 (e.g. plan-59 → `50s`, plan-60 → `60s`, plan-61 → `60s`, plan-72 → `70s`). Read the previous plan's Section 0 and carry its L1-L26 rules forward into the new plan, adding any new L-rules that were proposed in the previous plan's C9 rule-proposal step. Example: `git show origin/master:"GLM Prompts/50s/plan-59.md" | sed -n '/^## Section 0/,/^---$/p'`

### Step 4 — Create new AGENTS.md rules from execution-log findings

GLM sees patterns across multiple execution logs that Devin can't see (Devin only executes one plan at a time and has no memory of past execution logs). When GLM spots a recurring inefficiency, mistake, or workaround in Devin's execution logs, GLM creates a new rule for `AGENTS.md` — the always-on stable rules file that Devin auto-discovers.

**Before creating a new rule**: read `AGENTS.md` from the repo (`git show origin/master:AGENTS.md` or read from your clone). Confirm the rule doesn't already exist — if it does, don't create a duplicate. If a similar rule exists but doesn't cover the specific pattern you spotted, propose amending the existing rule rather than adding a new one.

**When to create a rule**: after reading the execution log (Step 1) and reviewing the repo state (Step 2), scan for any of these signals:
- Devin repeated the same mistake across 2+ prompts (e.g. running `mypy .` instead of file-scoped, using Unix commands on Windows, forgetting to tag)
- Devin hit a STOP condition that a simple rule could have prevented
- Devin worked around a problem in a way that suggests the rules didn't cover it
- Devin's execution took noticeably longer than necessary due to a workflow gap
- A landmine in the handoff's "Known landmines" section would be better as an AGENTS.md rule (so Devin follows it automatically, not just when GLM notices)

**How to format the rule**: write the rule as an instruction to Devin, phrased to fit AGENTS.md's existing categories (PowerShell / scans / git / editing / scope / etc.). Each rule needs:
- **Rule text**: one-line instruction (e.g. "Always use file-scoped mypy (`mypy file.py`), never `mypy .` — it takes 2-5 minutes and stalls the terminal.")
- **Category**: which AGENTS.md section it belongs in
- **Trigger**: concrete event from the execution log (e.g. "Devin ran `mypy .` in Plan 59 S3.3 and waited 4 minutes")
- **Expected benefit**: one line — what gets faster/cleaner if Devin follows this rule

**Where to put the rules**: in the new plan's opening Step 3 (see [Devin plan template](#devin-plan-template)). Devin will read them at S0.3 and add them to AGENTS.md before any other coding. Do NOT put the rules in the context brief — they go in the plan itself so Devin finds them at the right moment.

**If no new patterns are found**: the plan's opening Step 3 should say "No new AGENTS.md rules this prompt." Silence is NOT acceptable — explicit reflection is required, same as Devin's C9 rule-proposal step.

**Relationship to Devin's C9 rule-proposal step**: complementary, not duplicative. Devin's C9 proposes rules based on what Devin noticed during execution. GLM's Step 4 creates rules based on patterns GLM noticed across multiple execution logs. Both feed into AGENTS.md, but via different paths: Devin's C9 goes through the user-review-then-commit path; GLM's Step 4 goes directly into the next plan for Devin to implement at opening.

### Step 5 — Make the prompt + review guide for Claude

Create two files in `/home/z/my-project/download/` (clear the folder first — see [File hygiene](#file-hygiene)):

1. **`plan-{N}.md`** — the plan Devin will execute. Structure:
   - Section 0: rules (L1-L26, evolving)
   - Why this plan exists
   - Opening steps (S0) — copied from [Devin plan template](#devin-plan-template)
   - Body steps (S1, S2, ...) — the actual work
   - Closing: "Run `/jarvis-close`" — references [Devin plan template](#devin-plan-template)
   - STOP conditions
   - Out of scope (deferred)

2. **`plan-{N}-context-brief.md`** — the review guide for Claude. ~30-50 lines, pointer-based (reference handoff sections by pointer, don't copy). Include:
   - What's different from the previous plan
   - What this plan does (1-2 lines per step)
   - Baselines (tests, ruff, mypy, etc. — sourced from handoff, NOT from GLM clone per L19)
   - Review focus questions for Claude (3-6 specific questions)

### Step 6 — Review Claude's proposals

**User-bridge step**: GLM and Claude are different AIs in different chats. The user bridges them: they paste the plan + context brief to Claude in a separate chat, then paste Claude's findings back to this GLM chat. **Wait for the user's paste before proceeding.** Do not assume Claude's findings — you cannot see them until the user pastes them.

When Claude reviews the plan, it returns findings. GLM's job:
- **Blocking findings (B1, B2, ...)**: must be fixed before plan execution. Either fix the plan file directly, or if the finding is about repo state (e.g. duplicate CHANGELOG entries), produce a fix in the download folder for the user to apply.
- **High-severity (H1, H2, ...)**: should be fixed. Same approach.
- **Medium (M1, M2, ...)**: fix if cheap, defer if expensive. Document deferrals.
- **Low (L1, L2, ...)**: defer unless trivial.

Per the [Claude review workflow](#claude-review-workflow) section: no cap on revision rounds — continue until PLACE with zero findings. If the same blocking finding persists across 3+ rounds, flag it to the user as a potential impasse (don't auto-escalate, but do surface the stalemate).

### Step 7 — Implement the good proposals

Apply the fixes from step 6 to the plan file (and to download-folder copies of repo files if the finding is about repo state). Keep a `CHANGES.md` in the download folder summarizing what was applied, what was deferred, and why.

**File hygiene**: before generating a new batch of files, clear the download folder:
```bash
rm -f /home/z/my-project/download/*
```
This prevents stale files from confusing the user.

### Step 8 — Remake the prompt as "Rev 2" (if review changed it)

If Claude's review produced changes (Step 6-7), the revised plan becomes "Rev 2". Update the plan file in place (don't create `plan-60-rev2.md` — overwrite `plan-60.md`). Update the context brief to note "Revised: Rev 2, changes from Rev 1: <list>".

If the review produced no changes (PLACE on first pass), skip this step.

**Final delivery**: the download folder should contain exactly:
- `plan-{N}.md` — the plan for Devin (revised if applicable)
- `plan-{N}-context-brief.md` — the review guide for Claude (for reference)
- Any repo-file copies the user needs to apply manually (e.g. `CHANGELOG.md`, `SOVEREIGN_AI_HANDOFF.md`) — only if the review found issues in repo state
- `CHANGES.md` — summary of what was applied (only if Rev 2)

Tell the user: "Copy `plan-{N}.md` to `c:\Jarvis\GLM Prompts\{decade}s\plan-{N}.md` and point Devin at it."

---

## Devin plan template

GLM copies these opening + closing steps into every plan file. Devin executes them from the plan, not from this handoff.

### Opening steps (GLM puts these at the start of every plan's Step 0)

1. **Verify previous prompt completed** (prevents starting on stale state):
   ```powershell
   git ls-remote --tags origin | findstr prompt-{N-1}
   ```
   If empty, STOP — previous prompt's tag wasn't pushed. Fix that first.

2. **Verify local working copy is clean and on master** (do NOT pull):
   ```powershell
   git status
   git branch --show-current
   git rev-parse HEAD
   ```
   - `git status` should show "nothing to commit, working tree clean"
   - `git branch --show-current` should show `master`
   - `git rev-parse HEAD` should match the expected post-`prompt-{N-1}` HEAD
   - **Do NOT run `git pull origin master`.** Devin's local working copy is authoritative. Pulling from GitHub risks overwriting local work or pulling in unexpected changes. The previous-tag check above is sufficient to confirm the prior plan was pushed.
   - **If review fixes need to be applied** (e.g. CHANGELOG/handoff corrections from GLM review), they are applied MANUALLY to the local copy BEFORE the plan starts — not via git pull.

3. **Read AGENTS.md in full and add any new rules GLM specified for this plan** (mandatory before any coding step):
   ```powershell
   Get-Content AGENTS.md
   ```
   - Read every rule in AGENTS.md end-to-end. These are the always-on rules Devin auto-discovers — they govern every coding step in this plan. Do NOT skip this read even if you've read AGENTS.md before; rules may have changed since the previous plan.
   - After reading, check this plan's opening for any new rules GLM created based on execution-log findings (see [GLM workflow → Step 4](#step-4--create-new-agentsmd-rules-from-execution-log-findings)). GLM puts new rules directly in the plan, not in the context brief.
   - If this plan specifies new rules, **add them to AGENTS.md now** before any other step:
     1. Open `AGENTS.md`
     2. For each new rule, find the section matching the rule's `Category` (PowerShell / scans / git / editing / scope / etc.)
     3. Append the rule at the end of that section, numbered as the next rule in the section
     4. Commit the change:
        ```powershell
        git add AGENTS.md
        git commit -m "rules: add AGENTS.md rule(s) from plan-{N} opening step 3

        Created by GLM based on execution-log findings.
        Trigger: <from plan>
        Expected benefit: <from plan>"
        ```
   - **Do NOT proceed to any coding step until AGENTS.md is read in full AND all new rules are committed.** Coding without the rules active risks repeating the same inefficiency the rule addresses.
   - If this plan says "No new AGENTS.md rules this prompt," skip the add-to-AGENTS.md part but still read AGENTS.md in full.

Note: `Start-Transcript` does NOT work with Devin's multi-terminal architecture — Devin runs commands in separate terminal instances. The execution log is the user's chat paste (which shows every command + output). Do not use `Start-Transcript`.

### Closing steps (GLM puts these at the end of every plan)

Devin executes all of these. Steps 7-8 (handoff update + rule proposal) are Devin's responsibility (NOT GLM's — GLM does not edit the repo).

1. Run full test suite: `python -m pytest tests/ -q --tb=short`. Confirm zero new failures.
2. `ruff check <files_touched>` — zero errors.
3. `mypy <files_touched> --ignore-missing-imports` — zero errors. **File-scoped only** (L18).
4. `git add . && git commit -m "checkpoint: prompt-{N}" && git tag prompt-{N}`
5. `git show prompt-{N} --stat` — verify file list contains only files in this plan.
6. Update `CHANGELOG.md` with **SIMPLIFIED** entry (~10 lines):
   ```
   ## YYYY-MM-DD HH:MM — prompt-{N}
   
   **Plan**: <one-line plan title>
   
   **Changed**:
   - <file>: <what changed (1 line)>
   
   **Results**:
   - Mypy: <before> → <after>
   - Tests: <count> passed, <count> skipped, <count> failed
   - Tag: prompt-{N} verified on origin
   ```
   Use `-Encoding utf8` on both `Get-Content` and `Add-Content` (L15).
7. Update this handoff — 5 updates required:
   - **(a) Completed prompts table**: move completed plan to "Completed prompts" table (add new row at the bottom with #, prompt name, test count, one-line notes).
   - **(b) Baselines**: update "Test baseline" line and "Static analysis baseline" block with actual counts from this plan's S1.
   - **(c) Next 5 prompts queue**: shift the queue — Plan {N+1} becomes active, add a new open slot at the bottom. If the active plan changed scope during execution, update its entry in the queue.
   - **(d) Status sections** (mandatory — these drift if not updated every plan):
     - **"What works right now"**: add any newly-working feature (e.g. "POST /api/tasks now returns task_id" after wiring). Remove any feature that broke during this plan.
     - **"What's broken right now"**: add any new breakage discovered/fixed-partially this plan. Mark resolved items as "(RESOLVED by Plan {N})" — see F4/F9 in that section for the pattern. Remove fully-resolved items if the section gets too long.
     - **"What's built but not reachable"**: remove any subsystem that got wired into a runtime entry point this plan. Add any new subsystem built but not yet wired. Update the "Why it's dormant" column if the reason changed.
     - **"What's deferred (not started)"**: add any newly-deferred item. Remove any item that got started this plan (it should move to "Completed prompts" or "What's built but not reachable" as appropriate).
   - **(e) Landmines**: if this plan hit a new failure pattern not covered by existing landmines, add a new landmine entry (L{n+1} or M{n+1} after Plan 60 renumbers). If a landmine was resolved by a rule added to AGENTS.md, mark it "(FIXED — captured as AGENTS.md rule {n})".
8. **Rule proposal (self-evolution — L20 in global_rules_v2.md, L24 in this handoff)**: scan your work this prompt for recurring error patterns or landmines not covered by `global_rules.md`. If found, append a `## Rule proposal for global_rules.md` section to your closing report with:
   ```
   Trigger: <what happened this prompt — concrete, e.g. "TypeError comparing naive and aware datetime in test_calendar.py line 47">
   Recurrence: <prompt numbers where this same pattern bit, or "first occurrence">
   Proposed rule: L{n+1}. <one-line rule statement>
   Anchor: <prompt number + file + line>
   Why existing rules didn't catch it: <one line>
   ```
   If no new failure patterns were encountered, append: `## Rule proposal — none (no new failure patterns this prompt)`. Silence is NOT acceptable — explicit reflection is required. GLM reviews each proposal after the plan completes and updates `global_rules.md` (now v2) if accepted.
9. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-{N} changelog and handoff update"`
10. `git push origin master && git push origin prompt-{N}`
11. **Post-push verification** (mandatory — confirms the push actually worked):
    ```powershell
    git ls-remote --tags origin | findstr prompt-{N}
    ```
    Expected: returns the tag SHA (e.g. `2e9f883...`). If empty, the push failed — re-run step 10. If still empty after a second attempt, STOP and report (network issue, auth issue, or tag conflict).

**Note**: The user pastes Devin's chat transcript to GLM after the plan completes — this is covered in [GLM workflow → Step 1](#step-1--read-the-pasted-execution-log), not here. Devin does not need to do anything for this; it happens automatically when the user copies the chat.

### Plan completion checklist (GLM puts this at the end of every plan — Devin must paste ALL before reporting done)

```
1. C1 test suite: <paste last 3 lines of pytest>
2. C4 tag created: <paste git tag --list prompt-{N}>
3. C5 file list: <paste git show prompt-{N} --stat>
4. C10 pushed: <paste git push origin prompt-{N}>
5. C11 tag on origin: <paste git ls-remote --tags origin | findstr prompt-{N}>
6. Handoff completed-prompts row: <paste the new completed-prompts table row>
7. Handoff baselines updated: <paste the test baseline + mypy count lines>
8. Handoff status sections updated: <paste the diff of "What works" / "What's broken" / "What's built but not reachable" / "What's deferred" sections — show what changed>
9. Rule proposal section: <paste either the proposal block OR "none — no new failure patterns this prompt">
```

If any check fails or output is missing (including the rule-proposal section), the plan is NOT complete (Rule 21, L17, L24).

**CHANGELOG append procedure**: simplified entries (~10 lines). Use `-Encoding utf8` on both `Get-Content` and `Add-Content` (L15). For entries >20 lines, use temp-file pattern. NEVER use `Get-Content | Measure-Object` for line counts — use `[System.IO.File]::ReadAllLines(...).Count`.

### Claude review workflow

Plans go through Claude review before Devin execution. Context briefs are ~30-50 lines, pointer-based (reference handoff sections by pointer, don't copy). No cap on revision rounds — continue until PLACE with zero findings.

---

## Architecture rules (never violate)

1. `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, or `system/`.
2. `workers/` may import from `core/` and `adapters/` but never from `cli/`.
3. `memory/` may import from `core/` only.
4. `adapters/` may import from `core/` only.
5. `skills/` may import from `core/` only.
6. `web/` may import from `core/` only.
7. `system/` may import from `core/` and `memory/`.
8. `cli/` may import from anywhere.
9. All public functions and methods have return type annotations.
10. No raw LLM calls outside `adapters/`.
11. No memory access outside `MemoryRouter`.
12. No global mutable state. (Known violations: `_global_registry` in `core/commands.py`, `_global_emitter` in `core/observability.py`. Removal deferred — requires DI refactor.)
13. All I/O operations are async.
14. `InputSanitiser` MUST be called on all externally-sourced content before it enters LLM context. ✅ Wired (prompt-44, redesigned prompt-45).
15. `ApprovalTrustRegistry` MUST be consulted by `ApprovalGate` before raising any approval request.
16. Auth middleware MUST wrap ALL FastAPI routes and WebSocket handshakes. No unauthenticated endpoints except `/health`.
17. No broad `except Exception: pass` without inline comment + WARNING trace. ✅ All directories compliant.
18. Tests change with code. Full test suite MUST pass before tagging.
19. Execute steps and gates in listed order. Gate output must be pasted literally — "PASSED" without evidence is forbidden.
20. `table_name` in `memory/postgres.py` MUST be validated against `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$` at construction time.
21. **Closing steps 1-11 are MANDATORY for code-touching plans. A plan is NOT complete until the completion checklist passes.** Tag-push gate verification (`git ls-remote --tags origin | findstr prompt-NN`) is mandatory. Handoff baselines MUST be updated. **Docs-only exception**: plans that touch no `.py` files may skip steps 2 (ruff) and 3 (mypy) — no code to lint/type-check. All other steps (1, 4-11) remain mandatory, including tests (to confirm no test fixtures broke from docs changes), CHANGELOG, handoff update, rule proposal, tag, push, and post-push verify.

---

## Dependency injection rules

- `TraceEmitter` and `CommandRegistry` constructed ONCE in `cli/main.py` and passed down. (Currently violated — deferred.)
- All components receive emitter via constructor: `emitter: TraceEmitter | None = None`. Default to `MemoryTraceEmitter()`, never `ConsoleTraceEmitter()`.
- Never import `get_trace_emitter`, `set_trace_emitter`, `emit_trace`, `_global_emitter`, or `_global_registry` anywhere.
- When passing emitter to `super().__init__()`, the parameter MUST appear in the subclass `__init__` signature BEFORE the `super()` call.

---

## Completed prompts

| # | Prompt | Tests | Notes |
|---|---|---|---|
| 44 | InputSanitiser wiring | 1134 | 5 entry points wired. 7 wiring tests. |
| 45 | InputSanitiser redesign + trajectory_exporter | 1167 | 6-layer defense. 27 new tests. fetch_by_type() added. 6 tests un-skipped. |
| 46 | F821 + F811 + F841 cleanup | 1167 | 3 F821, 8 F811, 33 F841 fixed. |
| 47 | E402 + gateways/__init__.py + unused imports | 1167 | E402: 35→22, F401: 260→247. |
| 48 | Security: B608 + B104 + CI bandit/pip-audit/vulture | 1167 | SQL injection fixed. CI jobs added. |
| 48.1 | CHANGELOG append procedure fix | 1167 | L15 landmine. Temp-file pattern. |
| 49 | ApprovalGate schema + TraceEvent kwargs | 1167 | 10 Field(default=None) + 3 TraceEvent kwargs. ~108 mypy eliminated. |
| 49b | Migrate old-API callers | 1166 | 17 call sites across 8 skills. 32 mypy eliminated. |
| 50 | MockMemoryRouter/MockStateMachine inheritance | 1166 | 122 mypy eliminated across 8 test files. |
| 51 | Exception shadowing + float→int + DI fixes | 1166 | 27 mypy eliminated. e→inner_e, float→int casts. |
| 52 | F4 wiring — cognition-loop into serve.py | 1166 | worker_factory etc. wired into request path. |
| 53 | Test suite health — calendar + B108 + datetime | 1167 | Calendar test fixed. 22 B108 fixed. 81 utcnow fixed in 15 test files. 28 test utcnow + 90 production utcnow deferred to Plan 58. |
| 54 | F401 bulk cleanup + global_rules v2.1 ship + handoff fix | 1167 | 246 F401 fixed across 118 files. v2.1 rules shipped (L19/L20/L21). Handoff baselines updated. globalrules/ folder created. |
| 55 | 5-plan milestone: full scan + Marine stack start | 1167 | 4 SKILL.md files created (weather, AIS, tidal, passage_planner). Full-repo scan: ruff=111, mypy=283, bandit=22B108+3179low, pip-audit=37CVEs, vulture=32. Fresh baselines for Plans 56-60. |
| 56 | Dependency updates | 1167 | 11 packages upgraded (aiohttp, cryptography, idna, pygments, pypdf, pytest, python-dotenv, python-multipart, urllib3, pillow, setuptools). pip-audit: 55→19 CVEs. Starlette deferred (FastAPI incompatibility), chromadb/diskcache deferred (no confirmed fixes). |
| 57 | Vulture cleanup | 1167 | 16 dead-code findings removed (12 adapters + 3 core + 1 worker). 16 deferred as Category C (5 core + 11 tests). Vulture: 32→20. |
| 58 | Datetime UTCNow Cleanup | 1167 | 107 datetime.utcnow() calls replaced with datetime.now(timezone.utc) (28 test + 78 production + 1 scope expansion). Zero utcnow remain. 46+ bare datetime.now() calls deferred to Plan 58.5 (pre-existing L19 violations outside scope). |
| 58.5 | Bare datetime.now() cleanup | 1167 | 231 bare datetime.now() calls replaced with datetime.now(timezone.utc) (205 test + 26 production). Zero bare datetime.now() remain. 0 Category C deferrals (all calls were Category A/B - safe to convert). L19 compliance achieved for all datetime calls. |
| 58.6 | Datetime UTCNow in Field(default_factory=...) | 1166 | 12 datetime.utcnow function references in Field(default_factory=...) replaced with lambda: datetime.now(timezone.utc) (8 files). Zero utcnow remain in core/. 2 pre-existing ruff errors suppressed with scoped noqa. |
| 58.7 | Datetime UTCNow in system/ and skills/ | 1166 | 46 datetime.utcnow() calls replaced with datetime.now(timezone.utc) (10 in system/, 36 in skills/). 1 default_factory=datetime.utcnow replaced with lambda: datetime.now(timezone.utc). Zero utcnow remain repo-wide. 1 F541 ruff error fixed. |
| 59 | Ruff cleanup (110→0) + B108 scoped suppressions | 1166 | 41 files: 104 ruff fixes (F541=14, F401=2, F811=3, F841=41, E402=21, F821=21, E731=1, E741=1) + 6 E402 noqa suppressions (cli/rich_cli.py, cli/tui.py, gui/reference.py, web/reference.py). 22 B108 suppressed in 5 test files with `# nosec B108 -- local-first; test fixture path`. Bandit medium 22→0. |

---

## Known landmines

- **M1**: `global_rules.md` is Devin-local and unreachable. Don't cite it as authority. C8 targets the handoff.
- **M2**: Gates marked PASSED without literal output (Rule 19). All gates must require pasted output.
- **M3**: `@pytest.mark.skip` because mocking was hard. Fix the mock, don't skip.
- **M4**: Tagging with a red test suite forbidden.
- **M5/M17/Rule 21**: Tag-push gate mandatory. `git ls-remote --tags origin | findstr prompt-NN` must return the tag.
- **M7**: Per-file counts that don't match evidence. Always cite the source.
- **M9**: Devin memories are not authoritative. All authority comes from the handoff.
- **M10**: Test count assertions require measurement. Always paste output.
- **M11**: "No interactive shell" not a valid skip reason.
- **M12**: Scope creep. Only in-scope files.
- **M13**: Capture actual counts at plan-start, don't predict from prior scans.
- **M14**: Bandit commands MUST use `--exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache`.
- **M15**: CHANGELOG simplified (~10 lines). `-Encoding utf8` mandatory on both `Get-Content` and `Add-Content`.
- **M16**: Pydantic v2 + mypy requires `Field(default=None, ...)`, not `Field(None, ...)`.
- **M17/Rule 21**: Closing steps mandatory. Plan not complete until completion checklist passes.
- **M18**: File-scoped mypy only per-plan. NEVER `mypy .`. Full-repo mypy only at 5-plan checkpoints (55, 60...).
- **M19**: GLM must NOT run mypy/bandit/pytest/pip-audit/vulture on clone. Counts come from execution log.
- **M20**: Line numbers in plans verified against clone SHA. Note the SHA in the plan.
- **M21**: Plans must use PowerShell commands (`Select-String`, `Measure-Object`), not `grep`/`sed`/`awk`/`cut`/`wc`.
- **M22 (recurring mistakes)**: If GLM notices Devin repeating the same mistake or inefficient workflow pattern across multiple prompts (e.g. running `mypy .` instead of file-scoped, skipping tag-push, using Unix commands on Windows), GLM should add a step to the next plan instructing Devin to add the lesson to its `global_rules.md` file. Example plan step: "Add to `global_rules.md`: 'Always use file-scoped mypy (e.g. `mypy file.py`), never `mypy .` — it takes 2-5 minutes and stalls the terminal.' If `global_rules.md` doesn't exist or can't be edited, skip and document the skip in CHANGELOG." This ensures Devin's behavioral guardrails stay current with recurring issues GLM observes from the execution logs. **Note**: As of 2026-06-21, this mechanism is now **structural** — every plan's closing sequence includes C9 (rule-proposal step) per M24 below. GLM no longer needs to add ad-hoc rule-addition steps; the structural mechanism handles it.
- **M23 (test-production datetime coupling)**: when changing `datetime.utcnow()` to `datetime.now(timezone.utc)` in test files, check if production code compares datetimes with test data. If production uses `utcnow()` (naive) and tests use `now(timezone.utc)` (aware), Python raises `TypeError: can't compare offset-naive and offset-aware datetimes`. Both must change together. Always scope datetime changes to include both test AND production files that interact with the same datetime values. **Captured as global_rules_v2.md L19** — Devin now has this as a behavioral rule, not just a GLM-side landmine.
- **M24 (self-evolution meta-mechanism — NEW 2026-06-21)**: Every plan's closing sequence MUST include a rule-proposal step (C9 above). Devin scans its work for failure patterns not covered by `global_rules.md` and either (a) submits a structured proposal, or (b) explicitly states "none — no new failure patterns this prompt." Silence is NOT acceptable — explicit reflection is required. GLM reviews each proposal after the plan completes and updates `global_rules.md` if accepted. This makes `global_rules.md` a living document that grows with the project's actual failures, rather than relying on GLM to notice recurring patterns reactively (which is what M22 attempted, less reliably). First active prompt: Plan 54 (or whichever plan first ships global_rules_v2.md to Devin).
- **M25 (L-numbering collision — RESOLVED by Plan 60)**: This handoff's "Known landmines" section previously used labels L1-L25, colliding with per-plan Section 0 L-rules. **Plan 60 renamed all handoff landmines L1-L25 → M1-M25 (minefield).** Reserve `L1-Lxx` for per-plan evolving rules only. All cross-references in plan files and CHANGELOG entries updated at the same time.
- **M26 (PowerShell string ops corrupt structured markdown — NEW 2026-06-22)**: When editing `SOVEREIGN_AI_HANDOFF.md`, `AGENTS.md`, plan files, or `CHANGELOG.md`, use the Edit tool with exact `old_str`/`new_str` pairs. NEVER use PowerShell `-replace`, `ForEach-Object`, or `Set-Content` for structured markdown. Plan 60 S2.2 used `ForEach-Object` over `---` separators and inserted the prompt-59 row 5 times throughout the document (before every `---`). Plan 60 S3.1 used `-replace` chains that partially executed, leaving duplicate L24/M24 and L25/M25 entries. Both required `git restore` to recover. **Captured as AGENTS.md rule 23** — Devin now has this as a behavioral rule.

**Verification cadence (L18)**:
- Every plan: ruff (file-scoped) + mypy (file-scoped) + pytest.
- Every 5th plan (55, 60...): full scan (ruff + mypy . + bandit + pip-audit + vulture + pytest).
- Security-sensitive plans: always run bandit.
- Dependency-touching plans: always run pip-audit.
- Docs-only plans (no `.py` files touched): pytest count + tag check + handoff/CHANGELOG update + rule proposal + tag + push + post-push verify. Skip ruff (step 2) and mypy (step 3) — no code to check. See architecture rule 21 for the docs-only exception clause.

---

## Hardware context

- **GPU**: NVIDIA RTX 3060 Mobile — 6GB VRAM
- **RAM**: ~15.6GB available after VRAM
- **OS**: Windows
- **Local LLM**: Ollama with `qwen2.5-coder:7b` (Q4_K_M)

---

## Environment

- **Python**: 3.12.13 (Devin's venv on Windows; GLM sandbox has 3.12.13 in `/home/z/.venv/`)
- **OS (Devin)**: Windows — use PowerShell, not Unix commands (L21). `Select-String` not `grep`, `Measure-Object` not `wc`.
- **OS (GLM review sandbox)**: Linux — cannot run pytest/mypy/bandit/pip-audit/vulture meaningfully because optional deps are not installed (L19). Use for read-only verification only (file existence, line numbers, ruff/bandit static counts).
- **Install (Devin)**: `pip install -r requirements.txt` in venv. CLI entry point `jarvis` installed via `pip install -e .`.
- **Run tests (Devin)**: `python -m pytest tests/ -q --tb=short`
- **Optional dependencies** (in `requirements.txt` but NOT installed in GLM sandbox — causes collection errors on `test_anthropic_adapter.py`, `test_cohere_adapter.py`, `test_gemini_adapter.py`, `test_groq_adapter.py`, `test_openai_adapter.py`, `test_postgres_backend.py`, `test_qdrant_backend.py`):
  - `anthropic`, `cohere`, `google-genai`, `groq`, `openai` — LLM provider SDKs
  - `asyncpg` — Postgres async driver (for `memory/postgres.py`)
  - `qdrant-client` — vector DB SDK (for `memory/qdrant.py`)
- **GLM sandbox limitation**: `pip install` is blocked by PEP 668 (externally-managed-environment). GLM must NOT attempt to install optional deps — counts come from Devin's execution log per L19.

---

## User domain context

- **Media production** — video scripts, content creation
- **3D printing and CNC machining** — file generation, design workflows
- **Sailing** — route planning, weather monitoring, AIS tracking

---

## Next 5 prompts

### Plan 61 — Trace store implementation (P2, ACTIVE)
- Implement persistent trace event storage in Postgres for measurement layer.

### Plan 62 — Eval harness implementation (P3)
- Implement evaluation harness for improvement loop (offline evaluation of LLM outputs).

### Plan 62.5 — Eval validation (P3)
- Validate eval harness with held-out task suite.

### Plan 63a — Improvement loop wire (P4)
- Wire up improvement loop components (trace store + eval harness + orchestrator).

### Plan 63b — Improvement loop validate (P4)
- Validate improvement loop end-to-end.

### Plan 65 — 5-plan milestone full scan (P1)
- Next 5-plan milestone. Full-repo scan (ruff + mypy full-repo + bandit + pip-audit + vulture + pytest) + baseline refresh.
- **Scope to be finalized once Plans 61-64 land**: this entry is a placeholder. Plans 61-64 (trace store, eval harness, improvement loop wire, Postgres persistence) will introduce new code that may shift the mypy/ruff/vulture baselines in ways GLM can't predict now. At Plan 65 scoping time, GLM will inspect the actual repo state and write a concrete plan — do not assume the Plan 60 full-scan template copies verbatim. Expect at minimum: (a) re-capture all 6 tool baselines, (b) verify no new landmines emerged, (c) refresh the handoff status sections.
