# AI Handoff

## Project Overview

Sovereign AI is a local-first, self-improving AI assistant framework built for a single user's context: media production, sailing, 3D printing, and CNC machining. It runs locally by default, escalates to cloud when the task demands it, and monitors open-loop background tasks (weather, AIS, email) — interrupting only when necessary.

**Core philosophy**: Strong, robust, modular, simple core. Wire as you go. No new horizontal capability until the existing stack is reachable and demonstrably improving worker outputs.

**Stack**: Python 3.12, Textual TUI + Rich CLI + FastAPI web server.

---

## How to use this document

This handoff is a **static process guide**. It tells GLM how to make prompts and how the GLM-Devin-User workflow operates. It does NOT carry dynamic state (baselines, completed prompts, next-queue, landmines) — that lives in `PLANS.md` and `LANDMINES.md`.

**If you are a new GLM chat** receiving this handoff + a Devin execution log:
1. Clone the repo (if not already cloned): `git clone https://github.com/AngusKingC/sovereign-ai.git /home/z/my-project/sovereign-ai-framework`
2. Read this handoff end-to-end.
3. Read `PLANS.md` from the repo for current project state (baselines, completed prompts, next queue).
4. Read `LANDMINES.md` from the repo for known failure patterns to avoid.
5. Start the GLM workflow at Step 1.

---

## Roles

Three actors collaborate on this project. Each has a distinct job — do not cross the lines.

| Actor | Job | Tools |
|---|---|---|
| **User** | Pastes Devin's execution log to GLM after each plan. Copies GLM's download files to Devin's working tree when review fixes are needed. | IM chat with GLM; file copy on Devin's machine. |
| **GLM** | 7-step post-execution workflow. Creates plans, review guides, and revised plans. **Never edits the repo directly** — produces files in `/home/z/my-project/download/` for the user to copy. | `git fetch origin`, `git show`, `git log` (read-only). No push, no commit, no tool runs on clone. |
| **Devin** | Executes plans. Runs tests, ruff, mypy, bandit, pip-audit, vulture. Commits, tags, pushes. Updates CHANGELOG, handoff, and proposes rules. | PowerShell on Windows; the repo's working tree. |

**Key separation rule**: GLM does NOT commit to or push to the repo. Devin does NOT create plans or review guides. The user is the bridge — copies files between GLM's download folder and Devin's working tree.

---

## Repository bootstrap

The minimum needed to start working. Full environment (Python version, OS, optional deps, install commands) lives in `AGENTS.md` inside the repo — read it after cloning.

- **Repo**: https://github.com/AngusKingC/sovereign-ai (GitHub)
- **Default branch**: `master`
- **Tags**: `prompt-{N}` for each completed plan (e.g. `prompt-59`). Tag-push gate is mandatory.
- **Clone (Devin)**: Windows local path managed by Devin Desktop. All plan execution happens here.
- **Clone (GLM review)**: `/home/z/my-project/sovereign-ai-framework/` on Linux sandbox. Read-only.
- **After cloning**: read `AGENTS.md` from the repo root for Devin's always-on rules and full environment details.

---

## GLM Workflow

When the user pastes a Devin execution log, GLM follows these steps in order. Do not skip steps. Do not improvise.

1. **Read the execution log end-to-end.** Extract: actual test/ruff/mypy/bandit/pip-audit/vulture counts, any STOP conditions triggered, any rule proposals Devin submitted (C9), any deviations from the plan.

2. **Verify the repo state.** `git fetch origin` → check the prompt's tag exists on origin → check the CHANGELOG entry matches → check the commit stat matches the plan's scope (no scope creep) → check `PLANS.md` was updated (completed prompts row, baselines, queue shift). If anything doesn't match, flag to the user.

3. **Re-read this handoff** to remind yourself how to make prompts (Roles, Workflow, Plan Template, Document Relationships). Also re-read `LANDMINES.md` to remind yourself of failure patterns to avoid.

4. **Create new AGENTS.md rules** if you spotted a recurring pattern across multiple execution logs that a rule could prevent. Put the rule in the new plan's opening Step 3 (not in the context brief). If no new patterns, the plan's opening Step 3 says "No new AGENTS.md rules this prompt."

5. **Make the prompt + context brief.** Two files in `/home/z/my-project/download/`: `plan-{N}-Rev1.md` (the plan Devin executes) and `plan-{N}-Rev1-context-brief.md` (the review guide for Claude, ~30-50 lines, pointer-based). **Each iteration must use Rev{n} notation: Rev1, Rev2, Rev3, etc. Context brief is only created for Rev1. Rev2+ revisions do not need a context brief — Claude reviews the revised plan directly.**

6. **Pause for Claude review.** The user bridges: they paste the plan + context brief (Rev 1 only) or just the revised plan (Rev 2+) to Claude in a separate chat, then paste Claude's findings back to you. Claude reviews only — does not create or edit plan files, visual diagrams, only identifies issues and improvements. Wait for the user's paste. Apply findings at GLM's discretion.

7. **Deliver the final plan.** Tell the user: "Copy `plan-{N}-Rev{n}.md` to `c:\Jarvis\GLM Prompts\{decade}s\plan-{N}.md` and point Devin at it."

---

## Devin Plan Template

GLM copies this opening + closing structure into every plan file. Devin runs the workflows, not manual steps.

### Opening (S0)

S0.1. **Run `/jarvis-open`** — verifies previous prompt's tag on origin and confirms working copy is clean and on master. If the workflow is missing or fails, STOP and report.

S0.2. **Read AGENTS.md in full.** AGENTS.md is always-on — every file edit in this plan MUST comply with its rules. If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for the trigger and diagnostic context behind the rule.

S0.3. **Add any new rules GLM specified for this plan and commit** before any coding step. Then proceed to the plan body (S1 onward).

### Plan body (S1-Sn)
Execute all steps specified in the plan file. After each file edit, run `/jarvis-verify`. If any step has a STOP condition, pause and report to the user before proceeding.

### Closing

**Run `/jarvis-close`** — handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md (if new pattern), rule proposal (C9), docs commit, push, and post-push verification. If the workflow is missing or fails, STOP and report.

The workflow file (`.windsurf/workflows/jarvis-close.md`) is the source of truth for the closing sequence. GLM reads it from the repo to verify Devin's execution at GLM Workflow Step 2.

---

## Document Relationships

Five documents govern this project. Each has a single responsibility — do not duplicate content across them.

| Document | Responsibility | Who writes it | When it changes |
|---|---|---|---|
| `AI_HANDOFF.md` (this file) | Static process guide — how to make prompts, workflow, plan template, document relationships | GLM | Only when the workflow itself changes |
| `PLANS.md` | Dynamic project state — baselines, completed prompts, next-5-queue | Devin (at closing) | Every plan |
| `LANDMINES.md` | Known failure patterns — trigger and impact only. **Append-only** — capture once at closing, never edit after. | Devin (at closing) | When a new pattern is captured (append-only) |
| `CHANGELOG.md` | Chronological change log — one entry per plan, append-only | Devin (at closing) | Every plan |
| `AGENTS.md` | Devin's always-on rules — environment, edit discipline, git discipline, scope discipline. Rules reference their source landmine (e.g., "Source: L{n}"). | Devin (at S0.3, when GLM proposes new rules) | When new rules are added |
| `CONTEXT.md` | Shared vocabulary — domain terms, conventions, skill tier definitions, and decision framework. Referenced by all agents for consistent terminology. | GLM (creates), all agents (read) | When domain terms or conventions change |

**Single source of truth**: each fact lives in exactly one document. Other documents reference it, don't copy it.
- Environment details → `AGENTS.md` only (HANDOFF.md carries just the bootstrap minimum).
- Current baselines → `PLANS.md` only (HANDOFF.md doesn't carry baselines).
- Process/workflow/plan template → `AI_HANDOFF.md` only (PLANS.md doesn't carry process docs).
- Known failure patterns → `LANDMINES.md` only (HANDOFF.md doesn't carry landmines).
- Per-plan change record → `CHANGELOG.md` only (PLANS.md carries the summary row, not the full change log).
- Shared vocabulary / domain terms → `CONTEXT.md` only (AGENTS.md carries rules, not vocabulary)

**Read order**:
- GLM (new chat): `AI_HANDOFF.md` → `PLANS.md` → `LANDMINES.md` → `CONTEXT.md` → start workflow
- GLM (Step 3 of workflow): re-read `AI_HANDOFF.md` + `LANDMINES.md` + `CONTEXT.md`
- Devin (S0.2): `AGENTS.md` + `CONTEXT.md` (domain vocabulary for consistent naming)
