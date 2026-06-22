# Plan 51 Context Brief (for Claude review)

**Current revision**: REV2 (2026-06-20)

## Prior prompt state

- **Test baseline (prompt-50)**: 1166 passed, 55 skipped, 1 failed (calendar, pre-existing)
- **Mypy**: 309 errors (post-prompt-50)
- **prompt-50 tag**: `915926a` on origin ✅
- **Clone SHA for line numbers**: `eff46f3` (L20)

## Prior findings

- **Exception shadowing**: 13 files have nested `except Exception as e:` — inner shadows outer → PEP 3110 auto-cleanup → mypy "deleted variable" error. NO `del e` statements.
- **Float→int**: `start_time = 0` (int) assigned float in 5 skill files (14 errors)
- **DI violations**: `emit_trace()` uses global emitter; migration to `self._emitter.emit(TraceEvent(...))` confirmed safe (thin wrapper, verified at SHA `eff46f3`). 4 call sites + 1 import = 5 grep matches.
- **All 13 files' outer/inner except line numbers verified** at SHA `eff46f3` — listed in plan table.

## Files in scope

21 files: 12 adapters + system/audio_capture.py (shadowing), 5 skills (float→int), adapters/gemini.py + core/handlers.py + cli/tui.py + core/commands.py (DI).

## Review focus (REV2 changes from REV1)

1. All 13 files now have outer + inner except line numbers in a table (Finding 2 fix).
2. All commands use PowerShell only — no grep/sed/awk/cut/wc (L21 compliance).
3. C7 archives execution log (not deletes) — consistent with handoff's updated rule.
4. emit_trace definition already read and quoted in plan body (not delegated to Devin).
5. Calculator/skill.py fix uses `Select-String` command for Devin to read return statements.

## Landmines relevant

See handoff L1-L21. Most relevant: L17/Rule 21 (tag-push), L18 (file-scoped mypy), L19 (no clone tool runs), L20 (line numbers at SHA), L21 (PowerShell only).

## Revision history

- REV1: recreated. Key correction: shadowing not `del e`. Line numbers at SHA `eff46f3`. emit_trace = 4 calls.
- REV2: Claude round-1 findings — all 13 line number pairs listed; PowerShell-only commands; archive execution log.
