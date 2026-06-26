# AI Handoff

## Project Overview

Sovereign AI is a local-first, self-improving AI assistant framework built for a single user's context: media production, sailing, 3D printing, and CNC machining. It runs locally by default, escalates to cloud when the task demands it, and monitors open-loop background tasks (weather, AIS, email) — interrupting only when necessary.

**Core philosophy**: Strong, robust, modular, simple core. Wire as you go. No new horizontal capability until the existing stack is reachable and demonstrably improving worker outputs.

**Stack**: Python 3.12, Textual TUI + Rich CLI + FastAPI web server.

---

## How to use this document

This handoff is a **static process guide**. It tells the Prompt Creator (GLM or Kimi) how to make prompts and how the Prompt Creator-Devin-User workflow operates. It does NOT carry dynamic state (baselines, completed prompts, next-queue, landmines) — that lives in `PLANS.md` and `LANDMINES.md`.

**If you are a new Prompt Creator chat** (GLM or Kimi) receiving this handoff + a Devin execution log:
1. Clone the repo (if not already cloned): `git clone https://github.com/AngusKingC/sovereign-ai.git /home/z/my-project/sovereign-ai-framework`
2. Read this handoff end-to-end.
3. Read `PLANS.md` from the repo for current project state (baselines, completed prompts, next queue).
4. Read `LANDMINES.md` from the repo for known failure patterns to avoid.
5. Start the Prompt Creator workflow at Step 1.

---

## Roles

Three actors collaborate on this project. Each has a distinct job — do not cross the lines.

| Actor | Job | Tools |
|---|---|---|
| **User** | Pastes Devin's execution log to the Prompt Creator (GLM or Kimi) after each plan. Copies the Prompt Creator's download files to Devin's working tree when review fixes are needed. | IM chat with Prompt Creator; file copy on Devin's machine. |
| **Prompt Creator** | 7-step post-execution workflow. Creates plans, review guides, and revised plans. **Never edits the repo directly** — produces files in `/home/z/my-project/download/` for the user to copy. | `git fetch origin`, `git show`, `git log` (read-only). No push, no commit, no tool runs on clone. |
| **Devin** | Executes plans. Runs tests, ruff, mypy, bandit, pip-audit, vulture. Commits, tags, pushes. Updates CHANGELOG, handoff, and proposes rules. | PowerShell on Windows; the repo's working tree. |

**Key separation rule**: The Prompt Creator does NOT commit to or push to the repo. Devin does NOT create plans or review guides. The user is the bridge — copies files between the Prompt Creator's download folder and Devin's working tree.

---

## Repository bootstrap

The minimum needed to start working. Full environment (Python version, OS, optional deps, install commands) lives in `AGENTS.md` inside the repo — read it after cloning.

- **Repo**: https://github.com/AngusKingC/sovereign-ai (GitHub)
- **Default branch**: `master`
- **Tags**: `prompt-{N}` for each completed plan (e.g. `prompt-59`). Tag-push gate is mandatory.
- **Clone (Devin)**: Windows local path managed by Devin Desktop. All plan execution happens here.
- **Clone (Prompt Creator review)**: `/home/z/my-project/sovereign-ai-framework/` on Linux sandbox. Read-only.
- **After cloning**: read `AGENTS.md` from the repo root for Devin's always-on rules and full environment details.

---

## Prompt Creator Workflow (GLM, Kimi)

When the user pastes a Devin execution log, the Prompt Creator (GLM or Kimi) follows these steps in order. Do not skip steps. Do not improvise.

1. **Read the execution log end-to-end.** Extract: actual test counts for ALL test suites (pytest, Vitest, Playwright — not just Python), ruff/mypy/bandit/pip-audit/vulture counts, any STOP conditions triggered, any rule proposals Devin submitted (C9), any deviations from the plan. **When new test suites are added (e.g., Vitest in Plan 84, Playwright in Plan 85), the extract step must include them — the test count list is not fixed.**

2. **Verify the repo state.** `git fetch origin` → check the prompt's tag exists on origin → check the CHANGELOG entry matches → check the commit stat matches the plan's scope (no scope creep) → check `PLANS.md` was updated (completed prompts row, baselines, queue shift). If anything doesn't match, flag to the user.

3. **Re-read this handoff** to remind yourself how to make prompts (Roles, Workflow, Plan Template, Document Relationships). Also re-read `LANDMINES.md` to remind yourself of failure patterns to avoid.

4. **Create new AGENTS.md rules** if you spotted a recurring pattern across multiple execution logs that a rule could prevent. Put the rule in the new plan's opening Step 3 (not in the context brief). If no new patterns, the plan's opening Step 3 says "No new AGENTS.md rules this prompt."

5. **Make the prompt files + context brief.** For a batch of N plans: N individual files at `/home/z/my-project/download/{decade}s/plan-{N}-Rev1.md` (the plans Devin executes) and one shared brief at `/home/z/my-project/download/{decade}s/plan-{X1}-{X4}-batch-Rev1-context-brief.md` (the review guide for the panel). **Each iteration must use Rev{n} notation: Rev1, Rev2, Rev3, etc. — one file per plan per revision (e.g., `plan-86-Rev1.md`, `plan-86-Rev2.md`). Context brief is only created for Rev1. Rev2+ revisions do not need a new brief — the panel reviews the revised files directly.**

   **Context brief structure** (per Plan 76 research — based on Ghosh et al. structured prompting study + Anthropic sycophancy research + PhotoStructure proof-before-reporting pattern):

   The brief MUST use a 3-part scaffold (not a rigid box-grid, not unstructured prose):

   **Part 1: Roles/Rules** (~5 lines)
   - State the reviewer's role: "Your job is to find issues, not rewrite the plan"
   - State adversarial framing: "Assume this plan will fail — identify how"
   - State proof requirement: "Each issue must include a concrete failure scenario"

   **Part 2: Context** (~30-40 lines)
   - Plan scope summary (what files, what components)
   - Key dependencies (what existing modules this builds on)
   - **Author's reasoning (clearly labeled, to mitigate anchoring bias)**: "My reasoning for this design: [X]. Attack this reasoning — don't ratify the conclusion."
   - Named open questions for the reviewer to engage with — as many as pertinent, but each must be specific and substantive. Vague or confirmatory questions are banned; if you can answer it yourself with high confidence, don't ask it.
   - Prompt Creator's confidence level on key decisions (e.g., "65% confident on the debate pool filesystem layout")

   **Part 3: Answer Format** (~5 lines)
   - Specify the response structure (flexible, not rigid boxes)
   - ALWAYS include an "other concerns" open field so unexpected issues can surface
   - Permit "No issues found" — do not force the reviewer to invent problems

   **Brief length**: As long as it needs to be to cover the substance. No artificial cap, no padding. Every line should earn its place — if a section doesn't help the reviewer find issues, cut it.

   **Anti-sycophancy measures** (per Anthropic research — Claude sycophantic in 9-25% of reviews):
   - Open with pre-mortem frame: "Assume this plan failed in 6 months. List the most plausible reasons."
   - Explicitly permit "No issues found" — don't pad with false concerns
   - Require proof before reporting: each issue must cite a concrete failure scenario and evidence from the codebase
   - Ban style/formatting/speculative-future/feature-request comments — substance only

   **Anchoring mitigation** (per LLM anchoring bias research):
   - State the Prompt Creator's reasoning in a clearly labeled block
   - Instruct reviewer: "Criticize my reasoning, not my conclusion"
   - Disclose the Prompt Creator's confidence explicitly ("I'm 65% confident on step 3")
   - This gives the reviewer a target without forcing agreement

6. **Pause for round table review.** The user bridges: they send the plan files + context brief (Rev 1 only) or just the revised plan files (Rev 2+) to the 6-AI round table, then paste the round table's findings back to you. The round table reviews only — does not create or edit plan files, visual diagrams, only identifies issues and improvements. Wait for the user's paste. Apply findings at the Prompt Creator's discretion.

7. **Deliver the final plan.** Tell the user: "Copy `plan-{N}-Rev{n}.md` to `c:\Jarvis\Prompts\{decade}s\plan-{N}.md` and point Devin at it."

## Review Process

All plans — single-plan revisions and batch plans alike — are reviewed by the **6-AI round table**. There is no tiered system; the round table is the default and only review path.

**Round table members**: 6 AIs (configured by user — e.g., Claude, Kimi, DeepSeek, Gemini, ChatGPT, and one additional).

**Process**: Prompt Creator drafts plan(s) + context brief → 6-AI round table reviews → Prompt Creator judges responses → Prompt Creator adopts best-reasoned recommendations → Devin executes.

**Prompt Creator's commitment**: The Prompt Creator commits to adopting the highest-scoring recommendation — even if it contradicts the Prompt Creator's original position. This is what makes the pattern work: if the Prompt Creator always overrode the round table, there'd be no point.

**For roadmap-level decisions** (philosophy changes, feature arc launches), the user reviews the Prompt Creator's judgment before final decision.

---


## Batch Plan Process (Updated — Separate File Drafting)

Plans are drafted as **individual files from the start** (no combined batch file, no split step). Review happens via round table. This replaces the previous combined-file + split approach.

### Why separate files?

The combined-file + split approach introduced a mechanical transformation (split) that could introduce bugs — stale references to other plan numbers, leftover batch header text, missing S0/Closing sections. Drafting separately eliminates this overhead: what the panel reviews IS what Devin executes.

Cross-plan review is handled by the round table method and a shared batch-level context brief (below), not by bundling plans into one file.

### Scan prompts every 5 plans

After every 4-plan batch completes, a scan prompt runs to verify baselines, fix accumulated issues, and reconcile state before the next batch begins. Scan prompts are numbered at the 5-plan boundary (85, 90, 95, etc.).

**Batch structure**:
- Batch 1: Plans 81–84 (code production) → Scan 85
- Batch 2: Plans 86–89 (code production) → Scan 90
- Batch 3: Plans 91–94 (code production) → Scan 95
- etc.

### Step 1 — Draft individual plan files

Create N individual files (one per plan in the batch):

```
{PROMPT_CREATOR_WORKSPACE}/download/{decade}s/plan-{X1}-Rev1.md
{PROMPT_CREATOR_WORKSPACE}/download/{decade}s/plan-{X2}-Rev1.md
{PROMPT_CREATOR_WORKSPACE}/download/{decade}s/plan-{X3}-Rev1.md
{PROMPT_CREATOR_WORKSPACE}/download/{decade}s/plan-{X4}-Rev1.md
```

Each file is self-contained: S0 Opening, body, STOP condition, Files WILL create/edit/NOT edit, Closing, `Depends on:` line. Reads as a standalone Devin prompt.

Rules:
- Every plan file must be fully self-contained, executable (S0 opening, body, Closing).
- **Each plan's header must include a `Depends on:` line** listing prerequisite plans by number. Empty if independent. Machine-checkable by Devin at S0.1 via `/jarvis-open`.
- Each plan gets its own `prompt-{N}` tag when Devin executes it. One tag per plan.

### Step 2 — Draft the batch context brief

Create ONE shared brief covering all plans in the batch:

```
{PROMPT_CREATOR_WORKSPACE}/download/{decade}s/plan-{X1}-{X4}-batch-Rev1-context-brief.md
```

The brief follows the same 3-part scaffold (Roles/Rules, Context, Answer Format) as a standard brief, with these additions:
- **Cross-plan dependency map**: which plans depend on the output of a prior plan.
- **Sequencing risks**: what happens if plans execute out of order.
- **Author's confidence by plan**: e.g., "Plans 86–87: 80% confident. Plans 88–89: 65% confident — attack these hardest."
- **Named open questions**: as many as pertinent, but each must be specific and substantive.

### Step 3 — Round table review

Batch plans are reviewed by the **6-AI round table** — no exceptions.

Panel members: 6 members (configured by user — e.g., Claude, Kimi, DeepSeek, Gemini, ChatGPT, and one additional).

The user sends the N individual files + 1 batch context brief to the round table. The Prompt Creator collects all responses and judges them. Apply all substantiated findings to the individual files.

### Step 4 — Fix and re-review

Revise individual files as needed (one file per plan per revision):

```
{PROMPT_CREATOR_WORKSPACE}/download/{decade}s/plan-{X1}-Rev2.md
{PROMPT_CREATOR_WORKSPACE}/download/{decade}s/plan-{X2}-Rev2.md
...
```

Rev2+ files do not need a new context brief — the panel reviews the revised files directly. However, if revisions are substantial (new architecture, changed dependencies), update the batch brief to reflect the new state.

Repeat (Rev3, Rev4…) until the round table's response is a clean pass. A clean pass means: (a) no panel member reports a substantiated Critical or High issue that hasn't been addressed, and (b) any remaining Medium/Low items are documented as accepted/rejected with reasoning in the batch context brief's adjudication log.

**Severity rubric — four categories:**

- **CRITICAL**: Issues that would cause data loss, security vulnerability, or irreversible system damage. Any panel member may flag an issue as CRITICAL with a concrete failure scenario. CRITICAL issues block clean pass and must be resolved before Devin execution — no exceptions, no overrides.
- **HIGH**: Issues that would cause a Devin STOP condition, test failure, broken build, or Windows incompatibility. HIGH issues block clean pass and must be resolved or explicitly overruled with user sign-off.
- **MEDIUM**: Issues that would cause degraded functionality, poor user experience, or technical debt that should be addressed before execution but won't necessarily cause failure. MEDIUM issues should be addressed; if accepted, document reasoning in adjudication log.
- **LOW**: Style, formatting, naming preferences, speculative future features, or performance optimizations without measured impact. LOW items may be accepted or rejected at Prompt Creator discretion, with one-paragraph reasoning documented in the batch context brief adjudication log.

If a panel member and the Prompt Creator disagree on severity, the issue is treated as the higher severity until resolved.

### Execution failure within a batch

If Devin hits a STOP condition on Plan {Xn}, subsequent plans that depend on {Xn} — directly or transitively — must also STOP. Dependency is determined by each plan's `Depends on:` line, not by user judgment. Plans with no dependency on {Xn} may proceed, but only if their prerequisite tags are confirmed present on origin by `/jarvis-open`.

**Partial outputs:** If Plan {Xn} completed some but not all of its intended outputs, dependent plans must still STOP. The binary rule is: if Plan Y lists Plan X in `Depends on:`, and Plan X STOPped, Plan Y STOPs. No partial-dependency exceptions.

**Revised plan review:** After a STOP, the Prompt Creator revises the failed plan and any dependent plans. Revisions must undergo round table review before re-execution.

---

## Scan Prompt (NEW — Replaces X0 Decade-Close Plan)

Scan prompts occur every 5 plans (85, 90, 95, etc.) to verify baselines, fix accumulated issues, and reconcile state before the next batch begins.

### Purpose

After 4 plans execute, the repo accumulates small inconsistencies: stale imports, minor type errors that scraped past mypy, outdated docstrings, LANDMINES.md patterns not yet codified as rules, minor ruff warnings suppressed rather than fixed. The scan prompt cleans all of this up before the next batch begins.

The scan prompt is queued after Plan X4 in `PLANS.md` and executes before the next batch's Plan X1 begins.

**Drafting order constraint:** The next batch (e.g., 86–89) must not be drafted or panel-reviewed until the scan prompt has completed and its changes (including any new AR/OR rules proposed via C9) are committed to origin. This ensures the next batch is drafted against the post-scan repo state.

**Batch failure interaction:** If a batch fails partially (e.g., Plan 83 STOPs, halting 84), the scan must not execute until the failure is resolved and all plans 81–84 have completed. The scan verifies the full batch's output; running it on a partial batch would produce false positives.

### Scan Prompt Structure

```
## Plan {N} — N-Plan Milestone Scan and Fix

### Scope
Whole-repo scan. No new features. No new architecture. Fixes only.

### What to scan
- Run ruff, mypy, bandit, pip-audit, vulture in full — fix all findings not already documented as accepted suppressions in AGENTS.md.
- Scan LANDMINES.md: for any landmine without a corresponding AR/OR rule in AGENTS.md, propose the missing rule (C9 — Devin's standard rule-proposal channel).
- Scan CHANGELOG.md: verify every plan in the completed batch has a CHANGELOG entry.
- Scan PLANS.md: verify baselines are current and the next-5-queue reflects actual state.
- Scan all docstrings for references to removed/renamed modules.
- Run full test suite: pytest, Vitest, Playwright (if applicable).
- Verify coverage has not dropped >5% from baseline.

### What NOT to do
- Do not add new capabilities.
- Do not refactor working code unless it violates an existing AR/OR rule.
- Do not touch test fixtures beyond fixing failures caused by the above.

### STOP condition
If any scan reveals a structural problem requiring design decisions (not mechanical fixes), STOP and report to the user. Do not guess.
```

The scan prompt uses the standard S0 opening and `/jarvis-close` closing. It gets its own `prompt-{N}` tag.

---
## Prompt Creator Operating Discipline (NEW — Plan 78)

The Prompt Creator (GLM or Kimi) maintains a local rules file at `/home/z/my-project/prompt_creator_rules.md` (outside the repo, since the Prompt Creator doesn't write to the repo). Rules are prefixed `GR{n}` to mirror Devin's `AR{n}`/`OR{n}` scheme. The canonical copy of GR rules lives in this section; the local file is a mirror for the Prompt Creator's own reference.

### GR1. Refresh local rules when appropriate

At the start of every new Prompt Creator chat session, BEFORE doing any plan work:
1. Check if `/home/z/my-project/prompt_creator_rules.md` exists. If not, derive it from `AI_HANDOFF.md` + `AGENTS.md` + `LANDMINES.md` in the cloned repo.
2. If it exists, diff its `## Sync` section against the latest commit touching `AI_HANDOFF.md`, `AGENTS.md`, or `LANDMINES.md` on origin. If any of those files were updated since the last sync, re-derive the local rules file from the current repo state.
3. If a Devin execution log references a new governance patch or new AR/OR rule, refresh local rules AFTER reviewing the log (Workflow Step 4) so the new rule is in scope for the next plan.

Without this rule, a new Prompt Creator chat operates on stale rules — it doesn't know about AR20, OR39, governance patches, or new landmines added since the last chat. Stale rules → wrong plans → Devin STOP conditions → wasted cycles.

Every version of the local rules file MUST end with a `## Sync` section recording: (a) the commit SHA of `AI_HANDOFF.md` at last sync, (b) the commit SHA of `AGENTS.md` at last sync, (c) the commit SHA of `LANDMINES.md` at last sync, (d) the date.

(Source: Prompt Creator observation, post-rule-cleanup chat — Prompt Creator had no canonical rules file and was operating from inferred context. User requested codification.)

---

## Devin Plan Template

The Prompt Creator copies this opening + closing structure into every plan file. Devin runs the workflows, not manual steps.

### Opening (S0)

S0.1. **Run `/jarvis-open`** — verifies previous prompt's tag on origin and confirms working copy is clean and on master. If the workflow is missing or fails, STOP and report.

S0.2. **Read AGENTS.md in full.** AGENTS.md is always-on — every file edit in this plan MUST comply with its rules. If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for the trigger and diagnostic context behind the rule.

S0.2.5. **Re-read AGENTS.md after governance patches.** If this plan is resuming after a governance patch (Plan {N}.0 or Governance Directive) that added new rules to AGENTS.md, re-read AGENTS.md NOW before S1. The rules added by the patch were not in AGENTS.md when you originally read it at S0.2. Do not skip this re-read — the new rules (e.g., OR34 task list discipline, OR35-OR38 output discipline) apply to this plan's execution. If you do not re-read, you will execute with stale rules and may repeat the failure patterns the patch was designed to prevent.

S0.3. **Add any new rules the Prompt Creator specified for this plan and commit** before any coding step. Then proceed to the plan body (S1 onward).

### Plan body (S1-Sn)
Execute all steps specified in the plan file. After each file edit, run `/jarvis-verify`. If any step has a STOP condition, pause and report to the user before proceeding.

### Closing

**Run `/jarvis-close`** — handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md (if new pattern), rule proposal (C9), docs commit, push, and post-push verification. If the workflow is missing or fails, STOP and report.

The workflow file (`.windsurf/workflows/jarvis-close.md`) is the source of truth for the closing sequence. The Prompt Creator reads it from the repo to verify Devin's execution at Prompt Creator Workflow Step 2.

---

## Document Relationships

Five documents govern this project. Each has a single responsibility — do not duplicate content across them.

| Document | Responsibility | Who writes it | When it changes |
|---|---|---|---|
| `AI_HANDOFF.md` (this file) | Static process guide — how to make prompts, workflow, plan template, document relationships | Prompt Creator (GLM or Kimi) | Only when the workflow itself changes |
| `PLANS.md` | Dynamic project state — baselines, completed prompts, next-5-queue | Devin (at closing) | Every plan |
| `LANDMINES.md` | Known failure patterns — trigger and impact only. **Append-only** — capture once at closing, never edit after. | Devin (at closing) | When a new pattern is captured (append-only) |
| `CHANGELOG.md` | Chronological change log — one entry per plan, append-only | Devin (at closing) | Every plan |
| `AGENTS.md` | Devin's always-on rules — environment, edit discipline, git discipline, scope discipline. Rules reference their source landmine (e.g., "Source: L{n}"). | Devin (at S0.3, when the Prompt Creator proposes new rules) | When new rules are added |
| `CONTEXT.md` | Shared vocabulary — domain terms, conventions, skill tier definitions, and decision framework. Referenced by all agents for consistent terminology. | Prompt Creator (creates), all agents (read) | When domain terms or conventions change |

**Single source of truth**: each fact lives in exactly one document. Other documents reference it, don't copy it.
- Environment details → `AGENTS.md` only (HANDOFF.md carries just the bootstrap minimum).
- Current baselines → `PLANS.md` only (HANDOFF.md doesn't carry baselines).
- Process/workflow/plan template → `AI_HANDOFF.md` only (PLANS.md doesn't carry process docs).
- Known failure patterns → `LANDMINES.md` only (HANDOFF.md doesn't carry landmines).
- Per-plan change record → `CHANGELOG.md` only (PLANS.md carries the summary row, not the full change log).
- Shared vocabulary / domain terms → `CONTEXT.md` only (AGENTS.md carries rules, not vocabulary)

**Read order**:
- Prompt Creator (new chat): `AI_HANDOFF.md` → `PLANS.md` → `LANDMINES.md` → `CONTEXT.md` → start workflow
- Prompt Creator (Step 3 of workflow): re-read `AI_HANDOFF.md` + `LANDMINES.md` + `CONTEXT.md`
- Devin (S0.2): `AGENTS.md` + `CONTEXT.md` (domain vocabulary for consistent naming)
