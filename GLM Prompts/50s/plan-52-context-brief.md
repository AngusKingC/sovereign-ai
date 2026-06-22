# Plan 52 Context Brief (for Claude review)

**Current revision**: REV2 (2026-06-20)

## Prior prompt state

- **Test baseline (prompt-51)**: 1166 passed, 55 skipped, 1 failed (calendar, pre-existing)
- **Mypy**: 282 errors (post-prompt-51, per Devin's handoff update)
- **prompt-51 tag**: `a88ba88` on origin ✅
- **Clone SHA for line numbers**: `50675f2` (L20)

## Prior findings

- F4 open since prompt-35.6b: `cli/serve.py` constructs 4 cognition-loop subsystems with `_` prefix, never wires them.
- Orchestrator constructor does NOT accept `output_evaluator` — needs to be added.
- `OrchestratorImprovementLoop` IS already wired (`orchestrator.improvement_loop = improvement_loop` at line 167).
- `OutputEvaluator` constructed at line 123, before Orchestrator at line 137 — correct order for DI.
- TUI has same `_` prefix pattern (lines 349, 357, 380).

## Files in scope

3 files: `cli/serve.py`, `core/orchestrator.py`, `cli/tui.py`

## Review focus (REV2)

**What changed in REV2** (3 edits, from Claude round-1 findings):
1. Step 2.0 added: read `OutputEvaluator.evaluate()` signature before wiring (Finding 1 — prevents silent runtime TypeError).
2. Step 0.5 added: capture mypy baseline for 3 in-scope files. Gate 5 now compares against this baseline (Finding 2 — makes "0 NEW errors" verifiable).
3. Step 4.0 added: read TUI's Orchestrator constructor call before applying changes. Gate 4b added: verify `output_evaluator=` kwarg in TUI (Finding 3 — prevents wrong edit if TUI constructor differs).

**Claude should verify**:
1. Step 2.0's `Select-String` command correctly reads the evaluate() method signature.
2. Step 0.5's baseline is correctly referenced in Gate 5 ("count ≤ Step 0.5 baseline").
3. Step 4.0's `Select-String` command reads enough context (5 lines after) to see the full constructor call.
4. Gate 4b is correctly numbered (4, 4b, 5 — no collision).
5. All design questions RESOLVED per round-1 review (Q1-Q5 all answered, no findings).

## Landmines relevant

See handoff L1-L22. Most relevant: L17/Rule 21 (tag-push + completion checklist), L18 (file-scoped mypy), L19 (no clone tool runs), L20 (line numbers at SHA), L21 (PowerShell only), L22 (recurring mistakes → global_rules.md).

## Revision history

- REV1: initial draft (2026-06-20) — F4 wiring: remove _ prefixes, add output_evaluator to Orchestrator, wire trace_optimiser as attribute, update TUI to match.
