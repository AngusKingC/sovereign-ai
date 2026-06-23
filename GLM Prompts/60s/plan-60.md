# Plan 60 — 5-Plan Milestone: Full Checkpoint Scan + L25 Landmine Rename (Rev 3)

**Revision**: Rev 3 — incorporates Rev 2 + Plan 60 execution-log finding (PowerShell string ops corrupted the handoff during S2.2/S3.1). All structured-markdown edits now use explicit Edit-tool calls with exact `old_str`/`new_str` pairs. Adds new AGENTS.md rule 23, new handoff landmine M26, and GLM workflow Step 5 note. Rev 2 → Rev 3 changes listed at the bottom of this file in the Revision History section.

**CRITICAL (Rev 3)**: This plan contains EXACT `old_str`/`new_str` pairs for every structured-markdown edit. Use the Edit tool for each. NEVER use PowerShell `-replace`, `ForEach-Object`, or `Set-Content` for any edit in this plan — these corrupted the handoff during Rev 2 execution (see Rev 2 → Rev 3 Revision History).

**Prompt number**: 60
**Priority**: P1 (5-plan milestone — mandatory full scan per L18 verification cadence)
**Estimated scope**: docs-only (no `.py` files touched). Full-repo scan + handoff/AGENTS.md/plan-files/CHANGELOG docs updates.
**Baseline test count**: 1166 passed, 56 skipped (verified at Plan 59 S1.1)
**Baseline ruff**: 0 errors (post-Plan 59)
**Baseline mypy (full-repo)**: 283 errors (per handoff Plan 55 baseline — recapture at S1.3)
**Baseline bandit**: 3179 low, 0 medium (post-Plan 59 B108 suppressions)
**Baseline pip-audit**: 19 CVEs across 4 packages (per handoff Plan 56)
**Baseline vulture**: 20 high-confidence findings (per handoff Plan 57)

> **L19 compliance note**: GLM must NOT run ruff/bandit/pytest/mypy/pip-audit/vulture on clone. All counts in this plan come from (a) the handoff's Plan 55 full-scan baseline, (b) the handoff's post-Plan 59 baselines, or (c) Devin's execution log captured at S1.1-S1.6. Do not trust counts from GLM's Linux sandbox — different OS, different Python env, different tool versions.

---

## Section 0: Rules (read first, follow always)

**Note**: AGENTS.md is always-on. The stable rules in AGENTS.md (rules 1-21, plus the new rule 22 added at S0.3 below) are already loaded — don't repeat them here. Section 0 contains only the evolving L-rules that grow via L20 self-evolution.

**AGENTS.md SHA**: f9e159051b864ce89e5f377866492fb2c4d79022 (captured at S0.4). This anchors the plan to a specific AGENTS.md state per handoff landmine L20 (will become M20 after this plan completes the L25 rename).

**Tripwire**: this plan assumes AGENTS.md rules 1-21 as of 2026-06-22 (post-prompt-59 commit `bb715ed`), PLUS the new rule 22 added at S0.3. If AGENTS.md has been modified since, STOP and verify the stable rules haven't drifted from what L1-L26 below assume.

**Note on L-numbering (PRE-RENAME STATE)**: As this plan starts, the handoff "Known landmines" section uses labels L1-L25 with DIFFERENT meanings than this Section 0 (e.g., handoff L20 = "line numbers verified against clone SHA," but this Section 0 L20 = "self-evolution rule proposal"). This collision is tracked as handoff landmine L25. **S3 of this plan renames handoff landmines L1-L25 → M1-M25 to resolve the collision.** Until S3 completes, when this plan cites an L-rule, it refers to Section 0 above, NOT the handoff landmines. After S3 completes, handoff landmines are M1-M25 and there is no collision.

### Evolving rules (L1-L26, carried forward from Plan 59 — no additions)

**L1.** Follow the plan's verification gates in order. Run them, paste evidence, STOP on failure. Never assert file content from memory — always read the actual file first.

**L2.** Run the relevant test file after each file change. Run the full suite at gates, not after every edit.

**L3.** When you fix a bug, grep for the same pattern across the codebase before closing the prompt.

**L4.** Never silently substitute. If the spec says X, implement X. When in doubt, STOP and report. Do not improvise.

**L5.** Do not expand scope when tests find pre-existing issues outside the plan.

**L6.** TraceEvent is defined in `core/observability.py`. Use exactly these fields: `event_type`, `component`, `level`, `message`, `data`, `duration_ms`.

**L7.** Every class that emits trace events MUST use constructor-injected emitter. Never use the global `emit_trace()` function.

**L8.** Raise domain exceptions OUTSIDE try-except blocks. Never broad-except without a trace event.

**L9.** When fixing a production file, fix its test file in the same step.

**L10.** Do not remove working implementation to make a test pass.

**L11.** Verify field and class names against the actual schema file before using them.

**L12.** Patch at the location where a class is defined, not where it is used.

**L13.** Never mutate Pydantic model instances after construction in tests.

**L14.** Tests must verify behaviour, not just confirm the code runs.

**L15.** In tests, construct `MemoryTraceEmitter()` and pass it via constructor injection. Retrieve events via `emitter.get_events()`, never `emitter.events`.

**L16.** The CHANGELOG must match the commit. Verify before reporting completion.

**L17.** CHANGELOG format is simplified — ~10 lines per plan. Title, changed files, result, test count math. Record only non-trivial decisions.

**L18.** The correct closing sequence for every prompt: test → ruff → mypy (file-scoped) → commit → tag → tag-verify → CHANGELOG → handoff → rule-proposal → docs-commit → push → post-push-verify. **Or just run `/jarvis-close`.** Even docs-only plans must create a tag. **5-plan milestones (55, 60, 65, ...) may run `mypy .` (full-repo) at S1 — this is the only exception to the file-scoped rule.**

**L19.** Tests and production code MUST use the same timezone strategy. Never mix naive and aware `datetime`. Use `datetime.now(timezone.utc)` everywhere. Never `datetime.utcnow()` or bare `datetime.now()`.

**L20.** When you hit a recurring error pattern or a landmine not covered by these rules, propose a new rule to GLM in your closing report. Format: Trigger / Recurrence / Proposed rule / Anchor / Why existing rules didn't catch it. If none, list patterns considered with reasons. Silence is NOT acceptable.

**L21.** CHANGELOG entries are ALWAYS appended to the END using the temp-file pattern. NEVER insert at the top.

**L22.** This project runs on Windows. Use PowerShell, not Unix commands.

**L23.** Verification gates must check the actual scope of prior plans, not the entire codebase.

**L24.** Run scan tools SEQUENTIALLY, never in parallel. Each tool's output must be captured and verified before running the next.

**L25.** When removing unused parameters identified by vulture in test files, verify the parameter is not required by pytest fixture dependencies or framework protocols. If removal breaks tests, defer to Category C.

**L26.** When grepping for `datetime.utcnow`, always search for BOTH patterns: `datetime.utcnow()` (with parens) AND `datetime.utcnow` (without parens — function references like `default_factory`). Use `Select-String "datetime\.utcnow"` without the parentheses to catch both patterns.

---

## Why this plan exists

Three items bundled into one 5-plan milestone plan (all docs-only, no `.py` files touched):

1. **Full checkpoint scan (mandatory per L18 verification cadence)**: Every 5th plan runs a full-repo scan (ruff + mypy full-repo + bandit + pip-audit + vulture + pytest). Plan 55 was the last full scan; Plans 56-59 were file-scoped. Plan 60 refreshes ALL baselines in the handoff and verifies Plans 56-59 progress. This is the ONLY plan type where `mypy .` (full-repo) is permitted at S1.

2. **L25 landmine rename (deferred from Plan 59 review)**: The handoff "Known landmines" section uses labels L1-L25 with DIFFERENT meanings than per-plan Section 0 L-rules (e.g., handoff L20 = "line numbers verified against clone SHA" vs. Section 0 L20 = "self-evolution rule proposal"). This collision causes confusion when cross-referencing. **Fix**: rename handoff landmines L1-L25 → M1-M25 (minefield). Reserve `L1-Lxx` for per-plan Section 0 evolving rules only. Update cross-references in AGENTS.md, plan files, and CHANGELOG entries.

3. **Fix missing prompt-59 row in completed prompts table (Step 2 finding from GLM Plan 60 workflow)**: Plan 59's C10 handoff update missed closing step 7a — the prompt-59 row was never added to the "Completed prompts" table. This plan adds it. (The completion checklist item 6 should have caught this, but the checklist paste in Plan 59's execution log only mentioned items C1, C5, C6, C7, C8, C9, C10, C11, C12, C13 — skipping the completed-prompts row verification.)

**This plan touches ZERO `.py` files** — the docs-only exception applies (handoff Rule 21 / closing step note). Skip C2 (ruff) and C3 (mypy) at closing. All other closing steps (C1, C4-C13) remain mandatory, including the full test suite (to confirm no test fixtures broke from docs changes).

---

## Opening steps (S0)

### S0.1 — Verify prompt-59 tag on origin

```powershell
git ls-remote --tags origin | Select-String "prompt-59"
```

Expected: returns `2e9f883819e197b480969330899618b5c9d6d81f`. If empty, STOP — prompt-59 wasn't pushed.

### S0.2 — Verify local working copy (do NOT pull)

```powershell
git status
git branch --show-current
git rev-parse HEAD
```

Expected:
- `git status`: "nothing to commit, working tree clean"
- `git branch --show-current`: `master`
- `git rev-parse HEAD`: a descendant of `bb715ed` (the post-prompt-59 docs commit). Current origin/master tip is `0a3e31c` (docs: efficiency update — a post-prompt-59 user/Devin-side handoff reorganization).

**Do NOT run `git pull origin master`.** Devin's local working copy is authoritative. The previous-tag check at S0.1 is sufficient to confirm prompt-59 was pushed.

### S0.3 — Read AGENTS.md in full; add 2 new rules (rules 22 + 23)

```powershell
Get-Content AGENTS.md
```

Read every rule end-to-end. After reading, add these 2 new rules using the Edit tool (NOT PowerShell):

**Rule 22** (append to the "Environment" section, after existing rule 3) — bandit count fix:

> **22. Bandit finding count — use specific filter.** When counting bandit findings by ID (e.g., B108), filter on the literal `>> Issue: [B` pattern (the issue header line), not just the ID string. The ID appears in multiple line types per finding (issue header, "More Info" URL, and after suppression, "nosec encountered" warning lines), so `bandit ... | Select-String "B108" | Measure-Object -Line` overcounts by ~2x and triggers false-positive STOP conditions. Use the `Total issues (by severity):` summary line at the end of bandit output for authoritative medium/high counts.

**Rule 23** (append to the "Edit discipline" section, after existing rule 6) — structured-markdown edit fix (NEW in Rev 3):

> **23. Structured-markdown edits — Edit tool only.** When editing `SOVEREIGN_AI_HANDOFF.md`, `AGENTS.md`, plan files in `GLM Prompts/`, or `CHANGELOG.md`, use the Edit tool with exact `old_str`/`new_str` pairs. NEVER use PowerShell `-replace`, `ForEach-Object`, or `Set-Content` for structured markdown — these have corrupted the handoff (Plan 60 S2.2 `ForEach-Object` over `---` separators inserted the prompt-59 row 5 times throughout the document; Plan 60 S3.1 `-replace` chains partially executed, leaving duplicate L24/M24 and L25/M25 entries). If the plan provides exact `old_str`/`new_str` pairs, use them as-is. If the plan provides only prose instructions, STOP and request GLM guidance via user — do not improvise with PowerShell string ops.

**Edit-tool instructions for adding rules 22 + 23 to AGENTS.md**:

Edit #1 (add rule 22 after rule 3 in the Environment section):
- File: `AGENTS.md`
- `old_str`: `3. **Sequential scans.** Run scan tools (pytest, ruff, mypy, bandit, pip-audit, vulture) ONE AT A TIME. Parallel execution corrupts output streams and produces wrong counts.`
- `new_str`: `3. **Sequential scans.** Run scan tools (pytest, ruff, mypy, bandit, pip-audit, vulture) ONE AT A TIME. Parallel execution corrupts output streams and produces wrong counts.\n4. **Bandit finding count — use specific filter.** When counting bandit findings by ID (e.g., B108), filter on the literal ">> Issue: [B" pattern (the issue header line), not just the ID string. The ID appears in multiple line types per finding (issue header, "More Info" URL, and after suppression, "nosec encountered" warning lines), so \`bandit ... | Select-String "B108" | Measure-Object -Line\` overcounts by ~2x and triggers false-positive STOP conditions. Use the \`Total issues (by severity):\` summary line at the end of bandit output for authoritative medium/high counts.`

Edit #2 (add rule 23 after rule 6 in the Edit discipline section):
- File: `AGENTS.md`
- `old_str`: `6. **Diff check after every file edit:**`
- `new_str`: `7. **Structured-markdown edits — Edit tool only.** When editing \`SOVEREIGN_AI_HANDOFF.md\`, \`AGENTS.md\`, plan files in \`GLM Prompts/\`, or \`CHANGELOG.md\`, use the Edit tool with exact \`old_str\`/\`new_str\` pairs. NEVER use PowerShell \`-replace\`, \`ForEach-Object\`, or \`Set-Content\` for structured markdown — these have corrupted the handoff (Plan 60 S2.2 \`ForEach-Object\` over \`---\` separators inserted the prompt-59 row 5 times; Plan 60 S3.1 \`-replace\` chains left duplicate L24/M24 and L25/M25 entries). If the plan provides exact \`old_str\`/\`new_str\` pairs, use them as-is. If the plan provides only prose instructions, STOP and request GLM guidance via user.\n\n6. **Diff check after every file edit:**`

After both edits, commit the AGENTS.md change:

```powershell
git add AGENTS.md
git commit -m "rules: add AGENTS.md rules 22 (bandit count) + 23 (Edit-tool-only for structured markdown)

Created by GLM based on Plan 59 execution-log findings (rule 22)
and Plan 60 Rev 2 execution-log findings (rule 23).

Rule 22 trigger: Plan 59 S1.3 STOP — B108 overcount (44 vs 22).
Rule 23 trigger: Plan 60 Rev 2 S2.2 ForEach-Object bug + S3.1 partial -replace
left duplicate L24/M24 and L25/M25 entries in handoff. Required git restore.
Expected benefit: Prevents PowerShell string ops from corrupting structured
markdown in future plans."
```

**Do NOT proceed to any coding step until AGENTS.md is read in full AND rules 22 + 23 are committed.**

### S0.4 — Capture AGENTS.md SHA (per handoff landmine L20 → will become M20 after S3)

```powershell
git rev-parse HEAD:AGENTS.md
```

Record this SHA in the Section 0 tripwire at the top of this plan. If AGENTS.md has been modified since the post-prompt-59 state (commit `bb715ed`) plus the S0.3 rule 22 addition, STOP and verify the stable rules haven't drifted from what L1-L26 assume.

---

## Step 1 (S1) — Full scan baseline (run SEQUENTIALLY per L24)

**This is the 5-plan milestone full scan.** Per L18, full-repo `mypy .` is permitted here (and only here, plus future milestones 65, 70, ...). All other plans use file-scoped mypy.

**Per AGENTS.md rule 3 (sequential scans)**: run each tool ONE AT A TIME. Capture output. Verify count. Only then run the next tool. Parallel execution corrupts output streams.

### S1.1 — Test count baseline

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

Expected: `1166 passed, 56 skipped` (per handoff post-prompt-59 baseline, verified at Plan 59 S1.1).

**STOP condition**: if actual count differs from 1166/56 by >5, investigate per AGENTS.md rule 15 (baseline reconciliation). Possible causes:
- Test silently skipped (L3 landmine — check pytest output for `s` markers)
- Test added/removed since prompt-59 (check `git log --oneline -- tests/ | Select-Object -First 5`)

### S1.2 — Ruff full-repo baseline

```powershell
ruff check . --statistics 2>&1
```

Expected: `All checks passed!` (0 errors, per handoff post-prompt-59 baseline).

**STOP condition**: if any ruff errors found, investigate per AGENTS.md rule 15. Possible causes:
- New ruff rule enabled since Plan 59
- Code change since Plan 59 introduced new findings
- Pre-existing suppressed findings unsuppressed by config change

### S1.3 — Mypy full-repo baseline (5-plan milestone exception to L18 file-scoped rule)

```powershell
mypy . --ignore-missing-imports 2>&1 | Select-Object -Last 5
```

Expected: `Found 283 errors in N files` (per handoff Plan 55 baseline). Record the actual count and file count.

**Note**: mypy deferred to Phase 4 (Plans 66-74). This baseline is informational — verifies no new mypy errors were introduced by Plans 56-59. A sudden DECREASE is just as informative as an increase (did something get deleted, did a file get excluded from scanning, did the mypy config change, did a Plan 56-59 type fix have unintended side effects on unrelated modules).

**STOP conditions** (both directions — symmetric discipline):
- **If actual count > 283 by >10**: STOP and investigate per AGENTS.md rule 15. Possible causes:
  - New code added since Plan 55 without mypy cleanup
  - Type regression from Plan 56-59 changes
- **If actual count < 283 by >10**: STOP and investigate. Possible causes:
  - File accidentally deleted from scanning scope (check `mypy .` output file list vs. Plan 55's)
  - mypy config change (check `pyproject.toml` / `mypy.ini` for new excludes)
  - Plan 49/50/51/52 mypy eliminations still hold but were more aggressive than tracked
  - A Plan 56-59 fix had unintended type side effects on unrelated modules
  - **Decrease is NOT automatically good news** — verify the decrease corresponds to a known cleanup, not a scanning blind spot.

### S1.4 — Bandit full-repo baseline (USE NEW RULE 22 FILTER)

```powershell
# OLD pattern (overcounts — DO NOT USE):
# bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108" | Measure-Object -Line

# NEW pattern (per AGENTS.md rule 22):
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String ">> Issue: \[B108" | Measure-Object -Line
```

Expected: `0` (Plan 59 suppressed all 22 B108 findings with scoped `# nosec B108 -- local-first; test fixture path`).

Also capture the overall totals from the bandit summary line at the end of output:

```powershell
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "Total issues"
```

Expected: `Total issues (by severity): Low: 3179, Medium: 0, High: 0` (per handoff post-prompt-59 baseline — 3179 low unchanged from Plan 55, 0 medium was 22 pre-Plan-59).

**STOP condition**: if Medium > 0 or High > 0, investigate per AGENTS.md rule 15. Possible causes:
- New bandit rule triggered by code change since Plan 59
- B108 suppression removed/ineffective (check `>> Issue: \[B108` count — should be 0)

### S1.5 — pip-audit baseline

```powershell
pip-audit 2>&1 | Select-Object -Last 10
```

Expected: `19 vulnerabilities` across 4 packages (per handoff Plan 56 baseline — Starlette blocked by FastAPI, chromadb/diskcache no confirmed fixes).

Record the actual count and package list. **STOP condition**: if actual count > 19 by >2, investigate per AGENTS.md rule 15. Possible causes:
- New CVE published against an installed package
- Package added to requirements.txt since Plan 56

### S1.6 — Vulture baseline

```powershell
vulture . --min-confidence 80 2>&1 | Select-Object -Last 10
```

Expected: `20` high-confidence findings (per handoff Plan 57 baseline — 16 removed, 16 deferred as Category C, 20 remaining).

Record the actual count. **STOP condition**: if actual count > 20 by >3, investigate per AGENTS.md rule 15. Possible causes:
- New dead code added since Plan 57
- Plan 57 Category C deferral accidentally removed

### S1.7 — Baseline reconciliation summary

Compare each S1.x actual count to the handoff's stated baseline. If any count differs by >5 (or >10% for mypy), record the delta and the reason in the plan's work log. This is per AGENTS.md rule 15.

---

## Step 2 (S2) — Fix missing prompt-59 row in completed prompts table

**Finding (from GLM Plan 60 Step 2 verification)**: Plan 59's C10 handoff update missed closing step 7a. The prompt-59 row was never added to the "Completed prompts" table. The handoff's "Completed prompts" table currently ends at row 58.7.

### S2.1 — Verify the row is missing

```powershell
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "^\| 59 ").Count
```

Expected: `0` (the row is missing). If `1`, the row was already added — skip S2.2.

### S2.2 — Add the prompt-59 row (USE EDIT TOOL — NOT PowerShell)

**CRITICAL (Rev 3)**: Use the Edit tool for this edit. NEVER use PowerShell `ForEach-Object`, `-replace`, or array slicing — Plan 60 Rev 2 used `ForEach-Object` over `---` separators and inserted this row 5 times throughout the document (before every `---` separator), corrupting the handoff. Required `git restore` to recover.

**Edit-tool instruction**:

- File: `SOVEREIGN_AI_HANDOFF.md`
- `old_str` (the 58.7 row + the `---` separator that follows it):
```
| 58.7 | Datetime UTCNow in system/ and skills/ | 1166 | 46 datetime.utcnow() calls replaced with datetime.now(timezone.utc) (10 in system/, 36 in skills/). 1 default_factory=datetime.utcnow replaced with lambda: datetime.now(timezone.utc). Zero utcnow remain repo-wide. 1 F541 ruff error fixed. |

---
```
- `new_str` (58.7 row + new 59 row + `---` separator):
```
| 58.7 | Datetime UTCNow in system/ and skills/ | 1166 | 46 datetime.utcnow() calls replaced with datetime.now(timezone.utc) (10 in system/, 36 in skills/). 1 default_factory=datetime.utcnow replaced with lambda: datetime.now(timezone.utc). Zero utcnow remain repo-wide. 1 F541 ruff error fixed. |
| 59 | Ruff cleanup (110→0) + B108 scoped suppressions | 1166 | 41 files: 104 ruff fixes (F541=14, F401=2, F811=3, F841=41, E402=21, F821=21, E731=1, E741=1) + 6 E402 noqa suppressions (cli/rich_cli.py, cli/tui.py, gui/reference.py, web/reference.py). 22 B108 suppressed in 5 test files with `# nosec B108 -- local-first; test fixture path`. Bandit medium 22→0. |

---
```

**Why this is safe**: the `old_str` includes both the 58.7 row AND the `---` separator, making it unique in the file (no other `---` is preceded by exactly this row). The `new_str` inserts the 59 row between the 58.7 row and the `---` separator.

### S2.3 — Verify the row is present

```powershell
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "^\| 59 ").Count
```

Expected: `1`.

---

## Step 3 (S3) — L25 landmine rename (L1-L25 → M1-M25)

**Goal**: rename handoff "Known landmines" labels L1-L25 → M1-M25 to eliminate the collision with per-plan Section 0 L-rules. Update cross-references in AGENTS.md, plan files, and CHANGELOG entries.

### S3.1 — Rename handoff landmines L1-L25 → M1-M25 (USE EDIT TOOL — NOT PowerShell)

**CRITICAL (Rev 3)**: Use the Edit tool for EVERY edit below. NEVER use PowerShell `-replace`, `ForEach-Object`, or `Set-Content` — Plan 60 Rev 2 used `-replace` chains that partially executed, leaving duplicate L24/M24 and L25/M25 entries. Required `git restore` to recover.

Execute these 23 Edit-tool calls IN ORDER on `SOVEREIGN_AI_HANDOFF.md`. Each `old_str` is unique in the file (the label + colon pattern appears only in the landmine entry):

**Label renames (22 edits — L1 through L24, excluding L25 which gets a combined edit below)**:

| # | old_str | new_str |
|---|---|---|
| 1 | `- **L1**:` | `- **M1**:` |
| 2 | `- **L2**:` | `- **M2**:` |
| 3 | `- **L3**:` | `- **M3**:` |
| 4 | `- **L4**:` | `- **M4**:` |
| 5 | `- **L5/L17/Rule 21**:` | `- **M5/M17/Rule 21**:` |
| 6 | `- **L7**:` | `- **M7**:` |
| 7 | `- **L9**:` | `- **M9**:` |
| 8 | `- **L10**:` | `- **M10**:` |
| 9 | `- **L11**:` | `- **M11**:` |
| 10 | `- **L12**:` | `- **M12**:` |
| 11 | `- **L13**:` | `- **M13**:` |
| 12 | `- **L14**:` | `- **M14**:` |
| 13 | `- **L15**:` | `- **M15**:` |
| 14 | `- **L16**:` | `- **M16**:` |
| 15 | `- **L17/Rule 21**:` | `- **M17/Rule 21**:` |
| 16 | `- **L18**:` | `- **M18**:` |
| 17 | `- **L19**:` | `- **M19**:` |
| 18 | `- **L20**:` | `- **M20**:` |
| 19 | `- **L21**:` | `- **M21**:` |
| 20 | `- **L22 (recurring mistakes)**:` | `- **M22 (recurring mistakes)**:` |
| 21 | `- **L23 (test-production datetime coupling)**:` | `- **M23 (test-production datetime coupling)**:` |
| 22 | `- **L24 (self-evolution meta-mechanism` | `- **M24 (self-evolution meta-mechanism` |

**L25 combined label rename + content update (1 edit — replaces the entire L25 entry with the new M25 entry)**:

Edit #23:
- File: `SOVEREIGN_AI_HANDOFF.md`
- `old_str` (the entire L25 entry):
```
- **L25 (L-numbering collision — flagged 2026-06-22 by Plan 59 review, deferred to Plan 60)**: This handoff's "Known landmines" section uses labels L1-L24, but per-plan Section 0 (in plan files) ALSO uses labels L1-Lxx with DIFFERENT meanings. Example: handoff L20 = "line numbers verified against clone SHA," but Plan 59 Section 0 L20 = "self-evolution rule proposal." Same label, different rules — causes confusion when cross-referencing. **Deferred fix**: rename handoff landmines from `L1-L24` to `M1-M24` (minefield) at Plan 60 (5-plan milestone, full scan). Reserve `L1-Lxx` for per-plan evolving rules only. Update all cross-references in plan files and CHANGELOG entries at that time.
```
- `new_str` (the new M25 entry with RESOLVED status + new M26 landmine):
```
- **M25 (L-numbering collision — RESOLVED by Plan 60)**: This handoff's "Known landmines" section previously used labels L1-L25, colliding with per-plan Section 0 L-rules. **Plan 60 renamed all handoff landmines L1-L25 → M1-M25 (minefield).** Reserve `L1-Lxx` for per-plan evolving rules only. All cross-references in plan files and CHANGELOG entries updated at the same time.
- **M26 (PowerShell string ops corrupt structured markdown — NEW 2026-06-22)**: When editing `SOVEREIGN_AI_HANDOFF.md`, `AGENTS.md`, plan files, or `CHANGELOG.md`, use the Edit tool with exact `old_str`/`new_str` pairs. NEVER use PowerShell `-replace`, `ForEach-Object`, or `Set-Content` for structured markdown. Plan 60 S2.2 used `ForEach-Object` over `---` separators and inserted the prompt-59 row 5 times throughout the document (before every `---`). Plan 60 S3.1 used `-replace` chains that partially executed, leaving duplicate L24/M24 and L25/M25 entries. Both required `git restore` to recover. **Captured as AGENTS.md rule 23** — Devin now has this as a behavioral rule.
```

**Internal cross-reference updates within the handoff (2 edits)**:

Edit #24 (update "per L24 below" reference in L22/M22 entry):
- File: `SOVEREIGN_AI_HANDOFF.md`
- `old_str`: `per L24 below`
- `new_str`: `per M24 below`

Edit #25 (update "which is what L22 attempted" reference in L24/M24 entry):
- File: `SOVEREIGN_AI_HANDOFF.md`
- `old_str`: `which is what L22 attempted`
- `new_str`: `which is what M22 attempted`

**GLM workflow Step 5 note addition (1 edit — adds a new paragraph to Step 5 of the GLM workflow section)**:

Edit #26:
- File: `SOVEREIGN_AI_HANDOFF.md`
- `old_str`: `2. **plan-{N}-context-brief.md** — the review guide for Claude. ~30-50 lines, pointer-based (reference handoff sections by pointer, don't copy). Include:`
- `new_str`: `**Edit-tool-only rule for structured-markdown plans (NEW — Plan 60 Rev 3, 2026-06-22)**: When a plan includes edits to \`SOVEREIGN_AI_HANDOFF.md\`, \`AGENTS.md\`, plan files in \`GLM Prompts/\`, or \`CHANGELOG.md\`, GLM MUST provide exact \`old_str\`/\`new_str\` pairs for each edit in the plan file itself — not prose instructions. Prose like "rename each landmine label" or "append the row to the table" is NOT sufficient; Devin will improvise with PowerShell string ops, which corrupt structured markdown (see landmine M26). This rule applies to ALL future plans, not just Plan 60.\n\n2. **plan-{N}-context-brief.md** — the review guide for Claude. ~30-50 lines, pointer-based (reference handoff sections by pointer, don't copy). Include:`

**Total for S3.1**: 26 Edit-tool calls (22 label renames + 1 L25/M25+M26 combined edit + 2 cross-reference updates + 1 GLM workflow note).

**CAUTION — do NOT rename "Verification cadence (L18)"**: This subsection header in the handoff refers to the per-plan Section 0 L18, NOT the handoff landmine L18. Leave it as `L18`. The per-plan Section 0 L-rules are NOT renamed by this plan.

**CAUTION — do NOT rename "L20 self-evolution" in the C9 description**: This refers to the per-plan Section 0 L20, NOT the handoff landmine L20. Leave it as `L20`.

### S3.2 — Rename in AGENTS.md "Known landmines" section (USE EDIT TOOL)

AGENTS.md has a "Known landmines" section (currently uses L19, L24, L25 — only 3 entries). Rename using the Edit tool (NOT PowerShell):

**Edit #27** (rename L19 → M19 in AGENTS.md):
- File: `AGENTS.md`
- `old_str`: `- **L19**:`
- `new_str`: `- **M19**:`

**Edit #28** (rename L24 → M24 in AGENTS.md):
- File: `AGENTS.md`
- `old_str`: `- **L24**:`
- `new_str`: `- **M24**:`

**Edit #29** (rename L25 → M25 in AGENTS.md):
- File: `AGENTS.md`
- `old_str`: `- **L25**:`
- `new_str`: `- **M25**:`

Also update any inline reference in AGENTS.md like "per L19" → "per M19" using the Edit tool (search first, then edit each individually).

### S3.2a — Search ALL of AGENTS.md for stray handoff-landmine citations (not just the landmines block)

```powershell
Select-String -Path "AGENTS.md" -Pattern "handoff L\d|landmine L\d|per handoff L\d"
```

S3.2 only edits the landmines block. Other sections of AGENTS.md also reference L-rules — some are per-plan Section 0 L-rules (leave alone), but some may cite handoff landmines (rename to M). Apply the same decision rule as S3.3:
- The footer line ("Current count: 25 rules (L1-L25)... Check the plan's Section 0 for the latest version") and the "Quick reference" section both use bare L{n} numbering that refers to Section 0, NOT landmines — leave these alone.
- Any citation matching the handoff landmine descriptions (e.g., "line numbers verified against clone SHA" = old handoff L20) — rename.

**Why this step exists**: S3.3 searches plan files for handoff-L references outside the obvious landmine section. S3.2a applies the same search discipline to AGENTS.md, so handoff-landmine citations in non-landmine blocks of AGENTS.md aren't silently missed.

### S3.3 — Search plan files for cross-references to handoff landmines

```powershell
Get-ChildItem -Path "GLM Prompts" -Recurse -Filter "*.md" | Select-String -Pattern "handoff L\d|landmine L\d|per handoff L\d" | Select-Object Path, LineNumber, Line
```

For each match:
1. Read the line in context.
2. Determine if `L{n}` refers to a handoff landmine (rename to `M{n}`) or to a per-plan Section 0 L-rule (leave as `L{n}`).
3. **Decision rule**: if the surrounding text says "handoff", "landmine", "known landmines section", or references a rule that matches a handoff landmine description (e.g., "line numbers verified against clone SHA" = handoff L20), it's a handoff landmine — rename. Otherwise, leave as L{n}.

**Edit each occurrence individually using the Edit tool (NEVER `replace_all` — AGENTS.md rule 4; NEVER PowerShell `-replace` — new AGENTS.md rule 23).**

### S3.4 — Search CHANGELOG for cross-references to handoff landmines

```powershell
Select-String -Path "CHANGELOG.md" -Pattern "handoff L\d|landmine L\d|per handoff L\d" | Select-Object LineNumber, Line
```

For each match: apply the same decision rule as S3.3. Edit individually using the Edit tool (NOT PowerShell — per new AGENTS.md rule 23).

**CHANGELOG append discipline (AGENTS.md rule 10)**: normally CHANGELOG is append-only. However, this is a documentation rename — updating existing references to use the new M-numbering is permitted because the semantic content is unchanged. Do NOT add new CHANGELOG entries for each rename — record the bulk rename as a single line in the prompt-60 CHANGELOG entry (see C8).

### S3.5 — Verify no remaining handoff-L references that should be M

```powershell
# Should return 0 matches after rename:
Get-ChildItem -Path "GLM Prompts","SOVEREIGN_AI_HANDOFF.md","AGENTS.md","CHANGELOG.md" -Recurse -Filter "*.md" | Select-String -Pattern "handoff L\d|landmine L\d|per handoff L\d"
```

If matches remain, investigate each — some may be legitimate (referring to per-plan Section 0 L-rules, which stay as L{n}). Document any remaining matches in the plan's work log with rationale.

### S3.6 — M25 entry update + M26 landmine addition (ALREADY DONE in S3.1 Edit #23)

**Note (Rev 3)**: S3.1 Edit #23 already performs the L25→M25 label rename, M25 content update (deferred → RESOLVED), AND M26 landmine addition in a single combined edit. This step is a NO-OP — it exists only to document that the work was folded into S3.1 to avoid a separate edit that could partially execute (the Rev 2 corruption pattern).

Verify the M25 + M26 entries are present:
```powershell
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "\*\*M25").Count
# Expected: 1
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "\*\*M26").Count
# Expected: 1
```

### S3.7 — Verify the rename didn't break any tests (docs-only sanity check)

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

Expected: same as S1.1 baseline (1166 passed, 56 skipped). Docs-only changes should not affect tests, but this confirms no test fixture reads the handoff/AGENTS.md/plan-files for L-rule numbers.

---

## Step 4 (S4) — Update handoff baselines (post-Plan-60 scan)

In `SOVEREIGN_AI_HANDOFF.md`, update the "Static analysis baseline" block to reflect S1 actual counts. Use this format:

```markdown
**Static analysis baseline (post-prompt-60 — 5-plan milestone full scan)**:
- Ruff: <S1.2 actual> errors (was 0 — Plan 59 cleanup held)
- Mypy (full-repo): <S1.3 actual> errors in <N> files (was 283 — Plan 60 5-plan milestone recapture)
- Bandit: <S1.4 actual low> low, <S1.4 actual medium> medium, <S1.4 actual high> high (Plan 59 suppressed all 22 B108; Plan 60 verified clean)
- pip-audit: <S1.5 actual> CVEs across <N> packages (was 19 — Plan 60 5-plan milestone recapture)
- Vulture: <S1.6 actual> high-confidence findings (was 20 — Plan 60 5-plan milestone recapture)
```

Also update the "Test baseline" line at the top of the handoff:

```markdown
**Test baseline**: <S1.1 actual> (verified at Plan 60 S1.1 — 5-plan milestone full scan)
```

---

## Step 5 (S5) — Update handoff status sections (mandatory per closing step 7d)

Review and update each of the four status sections in `SOVEREIGN_AI_HANDOFF.md`:

### S5.1 — "What works right now"

Read the current section. Add any newly-working feature from Plans 56-59 that isn't listed. Remove any feature that broke. **Expected changes**: none — Plans 56-59 were debt cleanup, not feature work. Verify the list is still accurate.

### S5.2 — "What's broken right now"

Read the current section. Add any new breakage discovered during S1 full scan. Mark resolved items as "(RESOLVED by Plan {N})". **Expected changes**: none — Plans 56-59 didn't introduce new breakage.

### S5.3 — "What's built but not reachable"

Read the current section. Remove any subsystem wired into a runtime entry point this plan. Add any new subsystem built but not yet wired. **Expected changes**: none — Plan 60 is docs-only.

### S5.4 — "What's deferred (not started)"

Read the current section. Add any newly-deferred item. Remove any item that got started. **Expected changes**: verify the list aligns with the "Next 5 prompts" queue (S6).

---

## Step 6 (S6) — Update "Next 5 prompts" queue (mandatory per closing step 7c)

In `SOVEREIGN_AI_HANDOFF.md`, shift the queue:

- **Before**: Plan 60 (active), Plan 61, Plan 62, Plan 63, Plan 64 (open)
- **After**: Plan 61 (active), Plan 62, Plan 63, Plan 64 (open), Plan 65 (open — next 5-plan milestone)

Update each entry to reflect current scope:

### Plan 61 — Trace store implementation (P2, ACTIVE)
- Implement persistent trace event storage in Postgres for measurement layer.

### Plan 62 — Eval harness implementation (P3)
- Implement evaluation harness for improvement loop (offline evaluation of LLM outputs).

### Plan 63 — Improvement loop wire (P4)
- Wire up improvement loop components (trace store + eval harness + orchestrator).

### Plan 64 — (open slot for next GLM scoping)

### Plan 65 — 5-plan milestone full scan (P1)
- Next 5-plan milestone. Full-repo scan (ruff + mypy full-repo + bandit + pip-audit + vulture + pytest) + baseline refresh.
- **Scope to be finalized once Plans 61-64 land**: this entry is a placeholder. Plans 61-64 (trace store, eval harness, improvement loop wire, Postgres persistence) will introduce new code that may shift the mypy/ruff/vulture baselines in ways GLM can't predict now. At Plan 65 scoping time, GLM will inspect the actual repo state and write a concrete plan — do not assume the Plan 60 full-scan template copies verbatim. Expect at minimum: (a) re-capture all 6 tool baselines, (b) verify no new landmines emerged, (c) refresh the handoff status sections.

---

## Step 7 (S7) — Final verification (docs-only — per Rule 21, skip ruff/mypy)

### S7.1 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

Expected: same as S1.1 baseline (1166 passed, 56 skipped). Docs-only changes should not affect tests.

### S7.2 — Verify all handoff updates landed

```powershell
# prompt-59 row in completed prompts:
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "^\| 59 ").Count
# Expected: 1

# No remaining handoff L-references (should be M-references now):
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "landmine L\d|^\*\*L\d+\*\*").Count
# Expected: 0  (all renamed to M)

# AGENTS.md rule 22 present:
(Get-Content AGENTS.md | Select-String "Bandit finding count").Count
# Expected: 1

# Baselines block updated:
(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "post-prompt-60").Count
# Expected: >= 1
```

### S7.3 — Verify tag pre-conditions

- Working tree: only docs files modified (SOVEREIGN_AI_HANDOFF.md, AGENTS.md, CHANGELOG.md, possibly some plan files in GLM Prompts/)
- No `.py` files in `git diff --name-only`

```powershell
git diff --name-only | Where-Object { $_ -match "\.py$" }
```

Expected: empty output (no Python files touched). If any `.py` files appear, STOP — investigate scope creep.

---

## Closing: Run `/jarvis-close`

**Before relying on `/jarvis-close`**, verify it exists and contains the expected steps (per L1 — never assert file content from memory):

```powershell
Test-Path .windsurf\workflows\jarvis-close.md
Get-Content .windsurf\workflows\jarvis-close.md | Select-String "tag|push|verification"
```

If the file doesn't exist or is missing expected steps, STOP and report — don't improvise the closing sequence from memory. Fall back to the handoff's C1-C13 steps (Section: Devin plan template → Closing steps).

Run the `/jarvis-close` workflow with tag `prompt-60`. It handles C1-C13 automatically.

**Docs-only exception (Rule 21)**: this plan touches ZERO `.py` files. Skip C2 (ruff) and C3 (mypy) — no code to lint/type-check. All other steps (C1, C4-C13) remain mandatory, including:
- C1: full test suite (to confirm no test fixtures broke from docs changes)
- C4: commit
- C5: tag (`git tag prompt-60`)
- C6-C7: tag existence + file list verification (verify only docs files in the commit)
- C8: CHANGELOG entry (see below)
- C9: rule proposal (see below)
- C10: handoff update (verify ALL 5 items per closing step 7 — the prompt-60 row in completed prompts is the easy one to miss; verify with `(Get-Content SOVEREIGN_AI_HANDOFF.md | Select-String "^\| 60 ").Count` returning 1)
- C11: docs commit
- C12: push
- C13: post-push verification

**C8 CHANGELOG entry** (simplified, ~10-15 lines, append to END per AGENTS.md rule 10):

```
## 2026-06-22 <HH:MM> — prompt-60

**Plan**: 5-Plan Milestone Full Checkpoint Scan + L25 Landmine Rename (L→M)

**Changed**:
- AGENTS.md: added rule 22 (bandit count via Issue-header filter) + rule 23 (Edit-tool-only for structured markdown)
- SOVEREIGN_AI_HANDOFF.md: renamed landmines L1-L25 → M1-M25 (collision fix per old L25); added M26 (PowerShell corruption landmine); added prompt-59 row to completed prompts table; added GLM workflow Step 5 note (Edit-tool-only rule); refreshed all baselines per 5-plan milestone full scan; updated Next 5 prompts queue (Plan 61 active, Plan 65 added as next milestone)
- CHANGELOG.md: updated cross-references from handoff L{n} → M{n}
- GLM Prompts/{30s,40s,50s}/*.md: updated cross-references from handoff L{n} → M{n} where applicable

**Results**:
- Tests: <S1.1 actual count> (matches baseline)
- Ruff: <S1.2 actual> errors
- Mypy (full-repo): <S1.3 actual> errors in <N> files
- Bandit: <S1.4 actual low> low, <medium> medium, <high> high
- pip-audit: <S1.5 actual> CVEs across <N> packages
- Vulture: <S1.6 actual> high-confidence findings
- Tag: prompt-60 verified on origin
```

**C9 rule proposal**: reflect on the L25 rename process, the bandit-counting fix (rule 22), and the prompt-59 row miss. Did the rename surface any unexpected cross-references? Did the new rule 22 pattern catch the right things at S1.4? Did the completion checklist catch the prompt-60 row at C10? If any new pattern emerged, propose a rule.

---

## STOP conditions

1. **S0.1**: prompt-59 tag (`2e9f883819e197b480969330899618b5c9d6d81f`) not on origin.
2. **S0.2**: working tree dirty or not on master.
3. **S0.4**: AGENTS.md SHA differs from expected post-prompt-59 + rules 22 + 23 state.
4. **S1.1**: test count differs from 1166/56 by >5 (per AGENTS.md rule 15).
5. **S1.2**: ruff count > 0 (Plan 59 should have left it at 0; any new errors mean regression).
6. **S1.3**: mypy count > 283 by >10 OR < 283 by >10 (symmetric — new errors OR unexpected decrease; per Rev 2 F4).
7. **S1.4**: bandit Medium > 0 or High > 0 (Plan 59 should have left Medium at 0).
8. **S1.5**: pip-audit CVEs > 19 by >2 (new CVEs published since Plan 56).
9. **S1.6**: vulture findings > 20 by >3 (new dead code since Plan 57).
10. **S2.1**: prompt-59 row already exists (skip S2.2 — but investigate who added it).
11. **S3.3/S3.4**: cross-reference search finds >20 handoff-L references across `GLM Prompts/` and `CHANGELOG.md` combined (per Rev 2 F2 — lowered from >50 to >20).
12. **S3.7**: tests fail after rename (docs-only change should not break tests).
13. **S7.1**: test count drops (docs change broke a fixture).
14. **S7.3**: any `.py` files in `git diff` (scope creep — investigate).
15. **C13**: prompt-60 tag not on origin.
16. **(NEW Rev 3) PowerShell string ops for structured markdown**: if Devin catches itself using `-replace`, `ForEach-Object`, or `Set-Content` for any edit to `SOVEREIGN_AI_HANDOFF.md`, `AGENTS.md`, plan files, or `CHANGELOG.md`, STOP immediately. Use the Edit tool with exact `old_str`/`new_str` pairs instead. This is enforced by new AGENTS.md rule 23 (added at S0.3). If the plan does not provide exact `old_str`/`new_str` pairs for a structured-markdown edit, STOP and request GLM guidance via user — do NOT improvise with PowerShell.

---

## Out of scope (deferred)

- **283 mypy errors** → Phase 4 (Plans 66-74). Plan 60 captures the full-repo baseline only.
- **20 vulture findings** → permanent (Category C deferrals per Plan 57).
- **19 pip-audit CVEs** → wait for upstream patches (Starlette blocked by FastAPI, chromadb/diskcache no confirmed fixes).
- **Marine stack Python implementation** → deferred indefinitely (was Plan 61 in old queue, now removed).
- **Trace store / eval harness / improvement loop** → Phase 2 (Plans 61-63).
- **Postgres persistence** → Phase 3 (Plans 64-65).
- **Docker deployment / sandboxed execution / function-calling loop / streaming output** → deferred indefinitely.
- **Renaming per-plan Section 0 L-rules** → NOT in scope. Only handoff landmines are renamed. Per-plan Section 0 L1-L26 stays as L1-L26.
- **Renaming AGENTS.md stable rules (1-22)** → NOT in scope. Those are numbered rules, not L-labels.
- **Any code change to `.py` files** → NOT in scope. This is a docs-only 5-plan milestone.

---

## Revision History

### Rev 1 → Rev 2 (Claude review, 2026-06-22)

Claude reviewed Rev 1 against the context brief's 8 focus questions plus 1 extra finding. Result: 0 blocking, 5 substantive (H/M) findings applied. Findings F3, F5, F6, F8 confirmed no change needed (already correct in Rev 1).

**Changes applied**:

| # | Finding | Severity | Change |
|---|---|---|---|
| F1 | S3.2 only renames AGENTS.md's "Known landmines" section — doesn't search other AGENTS.md sections for stray handoff-landmine citations the way S3.3 searches plan files | H | Added new step **S3.2a** — `Select-String` pass over all of AGENTS.md for handoff-L references, applying same decision rule as S3.3. Explicitly notes footer line + "Quick reference" section are correctly left alone (they reference per-plan Section 0 L-rules). |
| F2 | S3.3/S3.4 STOP threshold of >50 is too loose — 50 handoff-L references = 50 individual judgment calls under L4, and a misclassified rename is silent | H | Lowered threshold from >50 to >20 in both the step text (S3.3 note) and the STOP-conditions summary (item 11). Added rationale: "each individual reference is a judgment call under L4 'never silently substitute'; a misclassified rename is silent and hard to catch later." |
| F4 | S1.3 mypy STOP condition is asymmetric — only triggers on increase, not decrease. A sudden decrease is just as informative (file deleted from scope, config change, unintended type side effects) | H | Made STOP conditions symmetric. Added second STOP clause: "If actual count < 283 by >10: STOP and investigate." Added 4 possible causes for decrease + explicit note "Decrease is NOT automatically good news — verify the decrease corresponds to a known cleanup, not a scanning blind spot." |
| F7 | S6 queue shift: "Plan 65 — 5-plan milestone full scan (P1)" with no content is a thin placeholder — exactly the kind of placeholder Plan 60 itself is fixing for Plan 59 (missing row problem) | M | Expanded Plan 65 entry with: (a) explicit scan tool list, (b) "Scope to be finalized once Plans 61-64 land" note explaining it's a placeholder, (c) the 3 minimum expectations for Plan 65 scoping time (re-capture baselines, verify no new landmines, refresh status sections). |
| F8 | STOP-condition item 11 still says ">50" — if F2 lowers the threshold, the number needs updating in two places (step + STOP summary), which is the exact single-fact-two-locations drift this project catches elsewhere | M (meta) | Both locations updated in lockstep. This finding itself is an instance of the drift pattern — captured here to make the pattern visible. |

**Findings with no change**:

| # | Finding | Severity | Why no change |
|---|---|---|---|
| F3 | Docs-only exception coverage | — | Confirmed correctly applied. Notably more careful than earlier plans: S7.3's explicit `git diff --name-only \| Where-Object { $_ -match "\.py$" }` check closes the loop rather than asserting "no .py files" from intent. |
| F5 | S2 prompt-59 row accuracy | — | Row text correctly states "104 ruff fixes" — picked up the reconciled handoff number rather than the earlier 110/111/113 confusion. No issue. |
| F6 | Rule 22 placement (Environment section) | — | "Environment" (rules 1-3, all about scan tool usage) is a reasonable home. A dedicated "Scan counting" section would be cleaner long-term but isn't worth a special step in this plan. Leave as-is. |
| F8 (original) | S3.6 M25 entry content | — | Already includes the resolution detail ("renamed all handoff landmines L1-L25 → M1-M25... cross-references in plan files and CHANGELOG entries updated at the same time"). No further detail needed. (Note: F8 was reused for the dual-location threshold drift finding above — the original F8 finding required no change.) |

**Net effect on plan execution**: Plan 60 Rev 2 is slightly longer (+~25 lines across S1.3, S3.2a, S6, STOP conditions, Revision History) but materially more robust. The symmetric mypy STOP (F4) and the lowered threshold (F2) catch failure modes that Rev 1 would have silently let through. The S3.2a search (F1) closes a real coverage gap in the rename procedure.

### Rev 2 → Rev 3 (execution-log finding, 2026-06-22)

**Trigger**: Plan 60 Rev 2 execution corrupted the handoff during S2.2 and S3.1. Devin used PowerShell `ForEach-Object` and `-replace` chains instead of the Edit tool, producing:
- S2.2: prompt-59 row inserted 5 times (before every `---` separator in the handoff)
- S3.1: partial `-replace` execution left duplicate L24/M24 and L25/M25 entries

Both required `git restore SOVEREIGN_AI_HANDOFF.md` to recover. Origin was not affected (corruption was local only).

**Root cause**: Rev 2 provided prose instructions ("rename each landmine label", "append the row to the table") without exact `old_str`/`new_str` pairs. Devin improvised with PowerShell string ops, which are fragile for structured markdown.

**Changes applied (5 items)**:

| # | Change | Location |
|---|---|---|
| R3-1 | Added CRITICAL header at top of plan: "This plan contains EXACT old_str/new_str pairs for every structured-markdown edit. Use the Edit tool for each." | Line 5 |
| R3-2 | S0.3 expanded: now adds 2 rules (rule 22 bandit count + rule 23 Edit-tool-only). Provides exact Edit-tool old_str/new_str for both rules. | S0.3 |
| R3-3 | S2.2 rewritten: replaced prose "Append to the completed prompts table" with exact Edit-tool old_str (58.7 row + ---) / new_str (58.7 row + 59 row + ---). Added CRITICAL warning about the ForEach-Object bug. | S2.2 |
| R3-4 | S3.1 rewritten: replaced prose "rename each landmine label" with a table of 22 label-only Edit-tool calls + 1 combined L25→M25+M26 edit + 2 cross-reference edits + 1 GLM workflow note edit. Total: 26 explicit Edit-tool calls. Added CRITICAL warning about the -replace bug. | S3.1 |
| R3-5 | S3.2 rewritten: replaced prose with 3 explicit Edit-tool calls for AGENTS.md landmines (L19→M19, L24→M24, L25→M25). | S3.2 |

**New handoff/AGENTS.md changes executed BY this plan (preventing future occurrences)**:

| Change | File | Purpose |
|---|---|---|
| New rule 23 | AGENTS.md | "Structured-markdown edits — Edit tool only. NEVER use PowerShell -replace/ForEach-Object/Set-Content for handoff/AGENTS.md/plan files/CHANGELOG." |
| New landmine M26 | SOVEREIGN_AI_HANDOFF.md | Documents the PowerShell corruption pattern (S2.2 ForEach-Object bug + S3.1 partial -replace). Points to AGENTS.md rule 23. |
| New GLM workflow Step 5 note | SOVEREIGN_AI_HANDOFF.md | Tells GLM to provide exact old_str/new_str pairs for every structured-markdown edit in future plans — not prose instructions. |

**Net effect on plan execution**: Plan 60 Rev 3 is ~100 lines longer than Rev 2 (due to the 26 explicit Edit-tool tables in S3.1) but eliminates the corruption risk. The 3 new handoff/AGENTS.md changes (rule 23, M26, GLM workflow note) ensure this class of mistake cannot recur in future plans — GLM is now required to provide exact old_str/new_str, and Devin is now required to use the Edit tool (not PowerShell) for structured markdown.
