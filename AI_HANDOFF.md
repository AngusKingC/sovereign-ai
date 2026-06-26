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

1. **Read the execution log end-to-end.** Extract: actual test/ruff/mypy/bandit/pip-audit/vulture counts, any STOP conditions triggered, any rule proposals Devin submitted (C9), any deviations from the plan.

2. **Verify the repo state.** `git fetch origin` → check the prompt's tag exists on origin → check the CHANGELOG entry matches → check the commit stat matches the plan's scope (no scope creep) → check `PLANS.md` was updated (completed prompts row, baselines, queue shift). If anything doesn't match, flag to the user.

3. **Re-read this handoff** to remind yourself how to make prompts (Roles, Workflow, Plan Template, Document Relationships). Also re-read `LANDMINES.md` to remind yourself of failure patterns to avoid.

4. **Create new AGENTS.md rules** if you spotted a recurring pattern across multiple execution logs that a rule could prevent. Put the rule in the new plan's opening Step 3 (not in the context brief). If no new patterns, the plan's opening Step 3 says "No new AGENTS.md rules this prompt."

5. **Make the prompt + context brief.** Two files in `/home/z/my-project/download/`: `plan-{N}-Rev1.md` (the plan Devin executes) and `plan-{N}-Rev1-context-brief.md` (the review guide for Claude). **Each iteration must use Rev{n} notation: Rev1, Rev2, Rev3, etc. Context brief is only created for Rev1. Rev2+ revisions do not need a context brief — Claude reviews the revised plan directly.**

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
   - 2-4 named open questions for the reviewer to engage with
   - Prompt Creator's confidence level on key decisions (e.g., "65% confident on the debate pool filesystem layout")

   **Part 3: Answer Format** (~5 lines)
   - Specify the response structure (flexible, not rigid boxes)
   - ALWAYS include an "other concerns" open field so unexpected issues can surface
   - Permit "No issues found" — do not force the reviewer to invent problems

   **Brief length**: 50-100 lines total. High-signal, no redundancy.

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

6. **Pause for Claude review.** The user bridges: they paste the plan + context brief (Rev 1 only) or just the revised plan (Rev 2+) to Claude in a separate chat, then paste Claude's findings back to you. Claude reviews only — does not create or edit plan files, visual diagrams, only identifies issues and improvements. Wait for the user's paste. Apply findings at the Prompt Creator's discretion.

7. **Deliver the final plan.** Tell the user: "Copy `plan-{N}-Rev{n}.md` to `c:\Jarvis\GLM Prompts\{decade}s\plan-{N}.md` and point Devin at it."

## Tiered Review System (NEW — Plan 76)

Not every plan needs the same review depth. The Prompt Creator selects the review tier based on plan characteristics:

### Tier 1: Claude only (default, ~80% of plans)
- **Trigger**: Routine plans, single-subsystem, mechanical fixes, scan plans, plans where AR/OR rules determine the answer
- **Process**: Prompt Creator drafts → Claude reviews → Prompt Creator revises → Devin executes
- **Cost**: Low (1 AI review)

### Tier 2: 5-AI panel (selective, ~20% of plans)
- **Trigger ANY of**:
  - Architectural decisions (new patterns, multi-subsystem integration, sequencing)
  - Prompt Creator confidence <70% in the plan design
  - Claude's review surfaces significant disagreement or open questions the Prompt Creator can't resolve
  - Novel territory (no precedent in the project — e.g., PEMADS Phase 1)
  - Reversible-but-expensive decisions (wrong choice costs multiple plans to fix)
- **Process**: Prompt Creator drafts strategy doc + plan → 5-AI panel reviews (Claude, Kimi, DeepSeek, Gemini, ChatGPT) → Prompt Creator judges responses on defined criteria → Prompt Creator adopts best-reasoned recommendation → Devin executes
- **Cost**: High (5 AI reviews + GLM judgment)

### Tier 3: 5-AI panel + user judgment (rare, ~2% of plans)
- **Trigger**: Roadmap-level decisions, philosophy changes (local-first → cloud), feature arc launches
- **Process**: 5-AI panel → Prompt Creator judges → user reviews Prompt Creator's judgment → final decision
- **Cost**: Highest (5 AI reviews + GLM judgment + user review)

### Prompt Creator's commitment
When Tier 2 or Tier 3 is triggered, the Prompt Creator commits to adopting the highest-scoring recommendation — even if it contradicts the Prompt Creator's original position. This is what makes the pattern work: if the Prompt Creator always overrode the panel, there'd be no point.

### When to trigger Tier 2 for plan review specifically
- A plan introduces a new architecture pattern (like AR19 sandbox, AR20 subprocess adapter)
- A plan touches 3+ subsystems
- Claude's review comes back with "REQUIRES CLARIFICATION" or >3 open questions
- Prompt Creator revises a plan 3+ times (Rev3+) — signals iterating in a hole

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
