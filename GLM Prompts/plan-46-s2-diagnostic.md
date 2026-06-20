# Plan 46 — S2 STOP Diagnostic Commands

**Context**: STOP condition S2 fired. Audit expected 26 F821 name-occurrences across 24 lines; actual is 25. Plan 45 removed 3 (trajectory_exporter.py dead code), so expected post-Plan-45 count is 23. Actual 25 means +2 drift — likely new F821s introduced by prompt-44's InputSanitiser wiring across 8 files.

**Action**: Run the two commands below, paste both outputs back, and I'll draft Plan 46 REV3 with corrected counts + new sub-steps (or Out-of-Scope deferrals) for any new F821s.

---

## Command 1 — Full F821 list (verbose, with line numbers and missing names)

```bash
ruff check . --select F821 --output-format=concise
```

**Expected output format** (one line per occurrence):
```
path/to/file.py:LINE:COL: F821 Undefined name `NAME`
```

**What this tells us**: every F821 currently in the repo, with exact file/line/missing-name. Compare against the audit table to find what's new.

---

## Command 2 — Per-file F821 count (sorted, easy to scan)

```bash
ruff check . --select F821 --output-format=concise | cut -d: -f1 | sort | uniq -c | sort -rn
```

**Expected output format**:
```
      6 system/model_acquisition.py
      3 core/orchestrator.py
      2 core/session.py
      2 system/resource_manager.py
      2 core/handlers.py
      1 cli/command_history.py
      1 core/escalation.py
      1 core/notification.py
      1 core/retention.py
      1 core/worker_base.py
      1 core/worker_factory.py
      1 workers/echo_worker.py
      [possibly 1-2 new files not in audit]
```

**Total should be 25** (matches your reported count). Any file in this list that's NOT in the audit table below is the drift source.

---

## Audit table (from 2026-06-20 audit section 1 — what the plan was written against)

For diffing against Command 2's output.

### Runtime F821s (crash bugs — Plan 46 Step 1 fixes 3 of these)

| File | Line(s) | Missing name | Severity |
|------|---------|--------------|----------|
| `cli/command_history.py` | 97 | `uuid4` | HIGH |
| `core/session.py` | 237, 280 | `Task` (×2 lines, 2 name-occurrences) | HIGH |
| `core/worker_base.py` | 78 | `TraceEmitter` | MED (TYPE_CHECKING) |
| `core/worker_factory.py` | 581 | `LLMResponse` + `WorkerOutput` (2 names on 1 line) | MED (TYPE_CHECKING) |
| `workers/echo_worker.py` | 69 | `core` | LOW |
| ~~`system/trajectory_exporter.py`~~ | ~~88, 96, 100~~ | ~~`records`~~ | ~~REMOVED by Plan 45 Step 4.3~~ |

### TYPE_CHECKING-only F821s (string annotations — not crash bugs, deferred to Plan 47/48)

| File | Line(s) | Missing name |
|------|---------|--------------|
| `core/escalation.py` | 32 | `TraceEmitter` |
| `core/handlers.py` | 28, 428 | `Orchestrator` (×2) |
| `core/notification.py` | 54 | `TelegramGateway` |
| `core/orchestrator.py` | 44, 721 | `A2ARouter` (line 44) + `A2ARequest` + `A2AResponse` (2 names on line 721) |
| `core/retention.py` | 46 | `MemoryRouter` |
| `system/model_acquisition.py` | 255, 256, 304, 305, 734, 810 | `ResourceManager`, `ModelRegistry` (6 name-occurrences across 6 lines) |
| `system/resource_manager.py` | 227, 290 | `ModelRegistry` (×2) |

**Expected post-Plan-45 total**: 7 runtime + 16 TYPE_CHECKING = **23 name-occurrences across 21 lines**.

**Your actual**: 25.

**Drift to locate**: +2 name-occurrences in files NOT in the table above.

---

## Bonus command (optional, helps me draft the amendment faster)

If you have time, also run this — it shows the new F821s that are NOT in the audit table:

```bash
ruff check . --select F821 --output-format=concise | awk -F: '{print $1}' | sort -u | comm -23 - <(echo -e "cli/command_history.py\ncore/session.py\nworkers/echo_worker.py\ncore/worker_base.py\ncore/worker_factory.py\nsystem/trajectory_exporter.py\ncore/escalation.py\ncore/handlers.py\ncore/notification.py\ncore/orchestrator.py\ncore/retention.py\nsystem/model_acquisition.py\nsystem/resource_manager.py" | sort -u)
```

If this command outputs nothing → all F821s are in audit-table files, and the drift is "extra occurrences in existing files" (e.g., audit said `core/orchestrator.py` has 3; actual has 5).

If this command outputs file paths → those are NEW files with F821s not in the audit. These are the drift source. Likely candidates based on prompt-44's work: `cli/serve.py`, `cli/query_handler.py`, `cli/tui.py`, `cli/rich_cli.py`, `web/server.py`, `gateways/telegram/gateway.py`, `skills/web_scraper/skill.py`.

---

## What I'll do with the output

Once you paste Command 1 + Command 2 outputs (bonus command optional), I'll:

1. **Identify the drift** — which files/lines are new vs. miscounted in the audit.
2. **Categorize each new F821** — runtime crash vs. TYPE_CHECKING-only.
3. **Draft Plan 46 REV3** with:
   - Updated Step 0.3 expected count (25, not 26)
   - Updated STOP S2 threshold (25, not 26)
   - New sub-steps in Step 1 if new runtime F821s are in-scope files
   - Updated Out of Scope section if new F821s are out-of-scope (deferred to Plan 46b or rolled into Plan 47)
   - Updated Gate 5 verification criteria (corrected per-file count)
   - Updated C6 CHANGELOG procedure with a re-baseline entry
   - New revision-log entry in Status block documenting the S2 fire + amendment

Save the file as `plan-46.md` (REV3) at `/home/z/my-project/download/plans/plan-46.md` (overwriting REV2).

---

## File path

This file: `/home/z/my-project/download/diagnostic-commands/plan-46-s2-diagnostic.md`

You can also download it directly. Run the commands, paste outputs back to me, and I'll have REV3 drafted within one turn.
