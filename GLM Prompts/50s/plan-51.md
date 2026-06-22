# Plan 51: Fix exception variable shadowing + float→int type errors + DI violations

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result. If STOP fires, stop and report.
>
> **Mypy**: FILE-SCOPED only (L18). NEVER `mypy .`.
> **Commands**: PowerShell only (L21). No grep/sed/awk/cut/wc.
>
> Drift check:
> `git diff --stat prompt-50..HEAD -- adapters/ core/handlers.py cli/tui.py core/commands.py skills/`

## Status
- Priority: P2
- Effort: S
- Risk: LOW
- Depends on: prompt-50
- Planned at: commit prompt-50 (915926a), 2026-06-20
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 findings 1-2 (all 13 inner/outer except line numbers listed; PowerShell-only commands; archive execution log).
- **Line numbers verified at clone SHA `eff46f3`** (L20).

## Why this matters

309 mypy errors remain after Plans 49-50. This plan fixes 3 categories:
1. **13 exception shadowing errors** — inner `except Exception as e:` shadows outer `e`; PEP 3110 auto-cleanup deletes the shadowed variable; `raise RuntimeError(f"... {e}")` after inner block triggers "deleted variable" error.
2. **14 float→int type errors** — `start_time = 0` (int) later assigned float.
3. **3 DI violations** — gemini.py uses global `emit_trace()`, handlers.py has dead import, TUI/commands use ConsoleTraceEmitter.

## Current state

**Files in scope (21 files). Line numbers verified at SHA `eff46f3`.**

### Exception shadowing (13 files — rename inner `e` to `inner_e`)

Each file has the same pattern: outer `except Exception as e:` at indent 8, inner `except Exception as e:` at indent 12 (inside the trace emission try/except within the error handler). The inner `e` shadows the outer `e`, and after the inner block exits, Python 3 (PEP 3110) auto-deletes the exception variable, making the outer `e` appear "deleted" to mypy.

| File | Outer except (line) | Inner except (line) |
|---|---|---|
| `adapters/ollama.py` | 199 | 218 |
| `adapters/lm_studio.py` | 160 | 179 |
| `adapters/huggingface.py` | 178 | 197 |
| `adapters/groq.py` | 154 | 173 |
| `adapters/together.py` | 157 | 176 |
| `adapters/openai.py` | 154 | 173 |
| `adapters/mistral.py` | 157 | 176 |
| `adapters/deepseek.py` | 157 | 176 |
| `adapters/anthropic.py` | 157 | 176 |
| `adapters/llama_cpp.py` | 138 | 156 |
| `adapters/cohere.py` | 159 | 178 |
| `adapters/gemini.py` | 134 | 152 |
| `system/audio_capture.py` | 126 | 141 |

### Float→int (5 files — change `start_time = 0` to `start_time = 0.0`)

| File | Lines with `start_time = 0` |
|---|---|
| `skills/notes/notes_skill.py` | 59, 210, 295, 380, 557 |
| `skills/reminder/reminder_skill.py` | 59, 209, 297 |
| `skills/email/email_skill.py` | 86, 259 |
| `skills/calendar/calendar_skill.py` | 56, 217, 407 |
| `skills/calculator/skill.py` | 189, 214 (return type mismatch — different fix, see Step 2.2) |

### DI fixes (4 files)

- `adapters/gemini.py` — line 20: remove `emit_trace` from import; lines 78, 112, 138, 153: replace `await emit_trace(...)` with `await self._emitter.emit(TraceEvent(...))`
- `core/handlers.py` — line 21: remove `emit_trace` from import (dead import)
- `cli/tui.py` — line 229: `ConsoleTraceEmitter()` → `MemoryTraceEmitter()`
- `core/commands.py` — line 74: `ConsoleTraceEmitter()` → `MemoryTraceEmitter()`

**emit_trace definition** (read from `core/observability.py` at SHA `eff46f3`):
```python
async def emit_trace(event_type, component, message, level=TraceLevel.INFO, 
    data=None, session_id=None, correlation_id=None, duration_ms=None, 
    error_type=None, error_message=None, error_stack=None) -> None:
    emitter = get_trace_emitter()  # GLOBAL emitter
    event = TraceEvent(event_type=event_type, ...)
    await emitter.emit(event)
```
It's a thin wrapper — constructs `TraceEvent` with the same kwargs and emits via the GLOBAL emitter. Migration: wrap kwargs in `TraceEvent(...)` and emit via `self._emitter`.

**Step 0 — verify (slim per L18):**

0.1. `git rev-parse HEAD` — expected: descendant of prompt-50.
0.2. `git ls-remote --tags origin | findstr prompt-50` — confirm tag on origin (L5/L17/Rule 21).
0.3. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — baseline: 1166 passed, 55 skipped, 1 failed (calendar, pre-existing). If different, STOP.
0.4. `Select-String -Path adapters/ollama.py -Pattern "except Exception as e:" | Measure-Object -Line` — should show 6+ matches (confirms pattern exists). If 0, STOP — already fixed.

## What to change

### Step 1 — Fix exception variable shadowing in 13 files

**The pattern** (verified at SHA `eff46f3`):
```python
except Exception as e:           # OUTER (line numbers in table above)
    try:
        # use e: error_type=type(e).__name__, error_message=str(e)
        ...
    except Exception as e:       # INNER (line numbers in table above) — SHADOWS outer e
        # use e: data={"error": str(e)}
        ...
        pass
    raise RuntimeError(f"... {e}")  # mypy: "deleted variable e"
```

**The fix**: in each of the 13 files, rename the INNER `except Exception as e:` (at the line number in the table) to `except Exception as inner_e:`. Update all references to `e` within the inner except block to `inner_e`. The outer `except Exception as e:` stays unchanged.

1.1. For each file in the table above: find the inner except at the specified line number, rename `e` to `inner_e` in the except clause AND all references within that inner block (typically `str(e)` → `str(inner_e)`).

1.2. **Verification** (all 13 files, file-scoped per L18):
```powershell
mypy adapters/ollama.py adapters/lm_studio.py adapters/huggingface.py adapters/groq.py adapters/together.py adapters/openai.py adapters/mistral.py adapters/deepseek.py adapters/anthropic.py adapters/llama_cpp.py adapters/cohere.py adapters/gemini.py system/audio_capture.py --ignore-missing-imports 2>&1 | Select-String "deleted variable" | Measure-Object -Line
```
Expected: 0 (was 13).

### Step 2 — Fix float→int type errors in 5 skill files

2.1. For `skills/notes/notes_skill.py`, `skills/reminder/reminder_skill.py`, `skills/email/email_skill.py`, `skills/calendar/calendar_skill.py`: change every `start_time = 0` to `start_time = 0.0` at the line numbers in the table.

2.2. For `skills/calculator/skill.py` (lines 189, 214 — return type mismatch): run `Select-String -Path skills/calculator/skill.py -Pattern "return" -Context 2,0` to see the return statements. Fix the return type — either wrap with `int()`/`float()` or change the return type annotation to match the actual return value.

2.3. **Verification** (file-scoped):
```powershell
mypy skills/calculator/skill.py skills/reminder/reminder_skill.py skills/notes/notes_skill.py skills/email/email_skill.py skills/calendar/calendar_skill.py --ignore-missing-imports 2>&1 | Select-String "float.*int|int.*float" | Measure-Object -Line
```
Expected: 0 (was 14).

### Step 3 — Fix DI: adapters/gemini.py emit_trace → self._emitter.emit

3.1. In `adapters/gemini.py` line 20: remove `emit_trace` from the import. Keep `TraceEvent` (needed for inline construction).

3.2. Replace each of the 4 `await emit_trace(...)` calls (lines 78, 112, 138, 153) with:
```python
await self._emitter.emit(TraceEvent(
    event_type=...,  # same kwargs as emit_trace call
    component=...,
    message=...,
    level=...,
    # include any other kwargs the call site uses (data, duration_ms, error_type, error_message)
))
```

3.3. **Verify `self._emitter` exists** in GeminiAdapter. Run:
```powershell
Select-String -Path adapters/base.py -Pattern "_emitter"
```
If `self._emitter` is defined in the base class, proceed. If not, STOP (S4).

3.4. **Verification**:
```powershell
Select-String -Path adapters/gemini.py -Pattern "emit_trace" | Measure-Object -Line
```
Expected: 0 (was 5: 1 import + 4 calls).
```powershell
mypy adapters/gemini.py --ignore-missing-imports 2>&1 | Select-String "emit_trace" | Measure-Object -Line
```
Expected: 0.

### Step 4 — Fix DI: core/handlers.py dead import

4.1. In `core/handlers.py` line 21: remove `emit_trace` from the import line. It's imported but never called.

4.2. **Verification**:
```powershell
Select-String -Path core/handlers.py -Pattern "emit_trace" | Measure-Object -Line
```
Expected: 0 (was 1).

### Step 5 — Fix ConsoleTraceEmitter → MemoryTraceEmitter

5.1. In `cli/tui.py` line 229: change `ConsoleTraceEmitter()` to `MemoryTraceEmitter()`. Update the import on line 48.

5.2. In `core/commands.py` line 74: change `ConsoleTraceEmitter()` to `MemoryTraceEmitter()`. Update the import on line 73.

5.3. **Verification**:
```powershell
Select-String -Path cli/tui.py -Pattern "ConsoleTraceEmitter" | Where-Object { $_ -notmatch "import" } | Measure-Object -Line
Select-String -Path core/commands.py -Pattern "ConsoleTraceEmitter" | Where-Object { $_ -notmatch "import" } | Measure-Object -Line
```
Expected: 0 for both.

### Step 6 — Verify no regressions

6.1. `ruff check adapters/gemini.py core/handlers.py cli/tui.py core/commands.py skills/calculator/skill.py skills/reminder/reminder_skill.py skills/notes/notes_skill.py skills/email/email_skill.py skills/calendar/calendar_skill.py system/audio_capture.py adapters/ollama.py adapters/lm_studio.py adapters/huggingface.py adapters/groq.py adapters/together.py adapters/openai.py adapters/mistral.py adapters/deepseek.py adapters/anthropic.py adapters/llama_cpp.py adapters/cohere.py`

6.2. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: 1166 passed, 55 skipped, 1 failed (calendar, pre-existing). If NEW failure, STOP.

## Verification gates

1. `mypy adapters/ollama.py adapters/lm_studio.py adapters/huggingface.py adapters/groq.py adapters/together.py adapters/openai.py adapters/mistral.py adapters/deepseek.py adapters/anthropic.py adapters/llama_cpp.py adapters/cohere.py adapters/gemini.py system/audio_capture.py --ignore-missing-imports 2>&1 | Select-String "deleted variable" | Measure-Object -Line` — expected: 0 (was 13).
2. `mypy skills/calculator/skill.py skills/reminder/reminder_skill.py skills/notes/notes_skill.py skills/email/email_skill.py skills/calendar/calendar_skill.py --ignore-missing-imports 2>&1 | Select-String "float.*int|int.*float" | Measure-Object -Line` — expected: 0 (was 14).
3. `Select-String -Path adapters/gemini.py -Pattern "emit_trace" | Measure-Object -Line` — expected: 0 (was 5).
4. `Select-String -Path core/handlers.py -Pattern "emit_trace" | Measure-Object -Line` — expected: 0 (was 1).
5. `Select-String -Path cli/tui.py -Pattern "ConsoleTraceEmitter" | Where-Object { $_ -notmatch "import" } | Measure-Object -Line` — expected: 0. Same for `core/commands.py`.
6. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: 1166 passed, 55 skipped, 1 failed (pre-existing calendar).
7. Manual smoke: `python -c "from adapters.gemini import GeminiAdapter; from core.handlers import *; print('imports OK')"` — expected: `imports OK`.

## STOP conditions

- **S0**: HEAD not descendant of prompt-50. STOP.
- **S1**: prompt-50 tag absent from origin. STOP (L5/L17/Rule 21).
- **S2**: Shadowing pattern not present (already fixed). STOP.
- **S3**: Test baseline not 1166/55/1 (calendar). STOP.
- **S4**: GeminiAdapter base class doesn't have `self._emitter`. STOP — report.
- **S5**: File outside in-scope list needs editing. STOP.
- **S6**: New test failure. STOP.
- **S7**: Gate marked PASSED without evidence. STOP (Rule 19).
- **S8**: >50 lines per step. STOP.
- **S9**: Closing step without evidence. STOP (Rule 21/L17).
- **S10**: C5 reveals out-of-scope file. STOP.
- **S11**: C11 tag-push fails. STOP — retry; if fails, report.

## Closing steps (mandatory — Rule 21)

**C1** — `python -m pytest tests/ -q --tb=no | Select-Object -Last 3`. Confirm zero new failures.

**C2** — `ruff check <files_touched>`. Expected: 0 errors.

**C3** — `mypy <files_touched> --ignore-missing-imports` (file-scoped). Expected: 0 NEW errors.

**C4** — `git add <files_touched> && git commit -m "checkpoint: prompt-51" && git tag prompt-51`. Verify `git log -1 --oneline` + `git tag --list prompt-51`.

**C5** — `git show prompt-51 --stat`. Expected: only in-scope files.

**C6** — Simplified CHANGELOG (~10 lines, `-Encoding utf8`):
```
## 2026-06-20 HH:MM — prompt-51

**Plan**: Fix exception shadowing + float→int + DI violations

**Changed**:
- 13 adapters/system files: renamed inner exception variable e→inner_e (fixes shadowing)
- 5 skill files: start_time = 0 → 0.0 (fixes float→int)
- adapters/gemini.py: 4 emit_trace() → self._emitter.emit(TraceEvent()) (DI fix)
- core/handlers.py: removed dead emit_trace import
- cli/tui.py, core/commands.py: ConsoleTraceEmitter → MemoryTraceEmitter

**Results**:
- Mypy: [paste file-scoped counts from execution log]
- Tests: 1166 passed, 55 skipped, 1 failed (pre-existing calendar)
- Tag: prompt-51 verified on origin
```

**C7** — Archive execution log: `if (!(Test-Path C:\Jarvis\scan\logs)) { mkdir C:\Jarvis\scan\logs }; Move-Item C:\Jarvis\scan\execution-log-prompt-51.md C:\Jarvis\scan\logs\prompt-51.md` (archive, not delete — preserves longitudinal history).

**C8** — Update `SOVEREIGN_AI_HANDOFF.md`: move Plan 51 to completed, update mypy baseline, refill queue.

**C9** — `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-51 changelog and handoff update"`

**C10** — `git push origin master && git push origin prompt-51`

**C11** — `git ls-remote --tags origin | findstr prompt-51`. **If empty, plan NOT complete (Rule 21, L17).**

## Out of scope

F4 wiring (Plan 52), test suite health (Plan 53), F401 bulk (Plan 54), marine stack (Plan 55), deps (Plan 56), dead code (Plan 57), `_global_emitter` refactor (P3 deferred), calendar test fix (Plan 53).

## For Claude review

1. All 13 files now have both outer and inner except line numbers listed in the table. Is this sufficient for Devin to find the exact blocks?
2. The emit_trace definition is already read and quoted in the plan (Step 3.0 of previous REV — now in "Current state"). Is the migration instruction clear?
3. C7 archives instead of deletes. This is consistent with the handoff's updated execution log rule (archive to `scan/logs/`). Correct?
4. All commands use PowerShell (`Select-String`, `Measure-Object`, `Where-Object`, `Get-Content`). No `grep`/`sed`/`awk`/`cut`/`wc` in the plan (L21). Correct?
5. The calculator/skill.py fix (Step 2.2) delegates to Devin to read the code and fix the return type. Is the `Select-String` command sufficient guidance?
