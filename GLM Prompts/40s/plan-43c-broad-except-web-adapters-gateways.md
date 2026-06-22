# Plan 43c: Eliminate broad-except patterns in web/, adapters/, gateways/

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise. Update the
> status row in `plans/README.md` when done.
>
> Drift check (run first): `git diff --stat e5b74be..HEAD -- web/ adapters/ gateways/`
> If any in-scope file changed since this plan was written, compare
> current state excerpts against live code; on mismatch, STOP.

## Status
- Priority: P1
- Effort: M
- Risk: LOW (same pattern as Plans 41-43b, well-established)
- Depends on: none (prompt-43b already landed)
- Planned at: commit e5b74be, 2026-06-20

## Why this matters

Architecture Rule 17 requires no broad `except Exception: pass` without an inline comment and WARNING trace event. Plans 41-43b have eliminated 351 patterns across core/, system/, and skills/. The remaining three layers — web/, adapters/, gateways/ — still have 44 bare `pass` patterns and 15 silent fallback/continue patterns that swallow errors without logging. These are the same class of "dead wiring" enablers that hid real failures in core/ and system/.

## Current state

**77 total** `except Exception` blocks across 3 directories. Of those, 18 already have proper handling (`except Exception as e:` + trace/log) — skip those. **59 blocks need fixing**:

- **44 `except Exception: pass`** (bare or with `# comment`) — silent swallow
- **14 `except Exception: return <fallback>`** — returns degraded data silently, no logging
- **1 `except Exception: continue`** — silent skip

### Per-file breakdown (verified against repo at e5b74be)

#### web/ (2 files, 11 total blocks, 0 already handled, 11 need fixing)

| File | `pass` | `return <fallback>` | Already handled | Total |
|------|:---:|:---:|:---:|:---:|
| web/server.py | 6 | 4 | 0 | 10 |
| web/middleware/auth_middleware.py | 1 | 0 | 0 | 1 |
| **web/ subtotal** | **7** | **4** | **0** | **11** |

#### adapters/ (13 files, 59 total blocks, 16 already handled, 43 need fixing)

| File | `pass` | `return <fallback>` | Already handled | Total |
|------|:---:|:---:|:---:|:---:|
| adapters/ollama.py | 4 | 1 | 1 | 6 |
| adapters/anthropic.py | 3 | 0 | 2 | 5 |
| adapters/cohere.py | 3 | 1 | 1 | 5 |
| adapters/deepseek.py | 3 | 1 | 1 | 5 |
| adapters/groq.py | 3 | 1 | 1 | 5 |
| adapters/huggingface.py | 3 | 1 | 1 | 5 |
| adapters/lm_studio.py | 3 | 1 | 1 | 5 |
| adapters/mistral.py | 3 | 1 | 1 | 5 |
| adapters/openai.py | 3 | 1 | 1 | 5 |
| adapters/together.py | 3 | 1 | 1 | 5 |
| adapters/gemini.py | 1 | 0 | 2 | 3 |
| adapters/llama_cpp.py | 1 | 1 | 1 | 3 |
| adapters/mcp_adapter.py | 0 | 0 | 2 | 2 |
| **adapters/ subtotal** | **33** | **10** | **16** | **59** |

#### gateways/ (1 file, 7 total blocks, 2 already handled, 5 need fixing)

| File | `pass` | `continue` | Already handled | Total |
|------|:---:|:---:|:---:|:---:|
| gateways/telegram/gateway.py | 4 | 1 | 2 | 7 |
| **gateways/ subtotal** | **4** | **1** | **2** | **7** |

#### Grand totals

| Category | Count | Needs fixing? |
|---|:---:|:---:|
| `except Exception: pass` | 44 (7 web + 33 adapters + 4 gateways) | Yes |
| `except Exception: return <fallback>` | 14 (4 web + 10 adapters + 0 gateways) | Yes |
| `except Exception: continue` | 1 (0 + 0 + 1 gateways) | Yes |
| Already handled (`as e` + trace/log) | 18 (0 web + 16 adapters + 2 gateways) | No |
| **Total** | **77** | |
| **Need fixing** | **59** | |

#### Files with NO `except Exception` (clean, skip these):
`web/__init__.py`, `web/middleware/__init__.py`, `web/reference.py`, `adapters/__init__.py`, `adapters/base.py`, `gateways/telegram/__init__.py`

### Fix rules (same as Plans 41-43b)

1. **`except Exception: pass`** → Add `except Exception as e:` + WARNING trace/log + inline comment. Keep the `pass` only if the exception is truly ignorable AND a trace event can't be emitted (sync method constraint — see audio_capture.py exception from prompt-42.1).

2. **`except Exception: return <fallback>`** → Add `except Exception as e:` + WARNING trace/log BEFORE the return. The return stays (graceful degradation is correct behavior), but the exception must be logged for debuggability.

3. **`except Exception: continue`** → Add `except Exception as e:` + WARNING trace/log BEFORE `continue`.

4. **Keep each file's existing logging convention**: adapters that use `self.emit_trace` keep using it; adapters that use `logging` keep using it; adapters that use `print` keep using it. Do NOT standardise — this is a mechanical safety-net plan, not a refactor.

5. **Check sync vs async before choosing trace pattern**: web/server.py uses standard `logging` (sync-safe). Adapters with `self.emit_trace` are async. Use `logging.warning()` for sync contexts, `await self.emit_trace(...)` for async contexts.

## What to change

### Step 1: Fix web/server.py (6 pass + 4 return-fallback = 10 blocks)

Before editing: confirm whether web/server.py's handlers are sync or async by checking the function signatures. Use `logger.warning()` (sync-safe) for all blocks.

For each of the 6 `except Exception: pass` blocks (lines 36-37, 103-104, 162-163, 184-185, 200-201, 202-203):
- Change `except Exception:` to `except Exception as e:`
- Add `logger.warning(f"<context>: {e}")` before `pass`
- Keep inline comment per Rule 17

For each of the 4 `except Exception: return <fallback>` blocks (lines 79-80, 107-108, 119-120, 130-131):
- Change `except Exception:` to `except Exception as e:`
- Add `logger.warning(f"<method_name> failed: {e}")` BEFORE the return
- Keep the return statement unchanged

**Verification**: `Select-String -Path web\server.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" -and $_.Context.PostContext -notmatch "#" }` returns zero hits. AND `Select-String -Path web\server.py -Pattern "except Exception:" -Context 0,2 | Where-Object { $_.Context.PostContext -match "return" -and -not ($_.Context.PostContext -match "warning|logger|emit_trace") }` returns zero hits.

### Step 2: Fix web/middleware/auth_middleware.py (1 pass block)

- Change `except Exception:` to `except Exception as e:`
- Add WARNING trace event + inline comment

**Verification**: Same grep pattern as Step 1, zero hits.

### Step 3: Fix adapters/ — `pass` patterns (33 patterns across 12 files)

For each adapter file with `except Exception: pass`:
- Change `except Exception:` to `except Exception as e:`
- Add WARNING trace/log using the file's existing convention (`self.emit_trace`, `logging`, or `print`)
- Keep inline comment per Rule 17

Files to fix (pass count):
- adapters/ollama.py: 4
- adapters/anthropic.py: 3
- adapters/cohere.py: 3
- adapters/deepseek.py: 3
- adapters/groq.py: 3
- adapters/huggingface.py: 3
- adapters/lm_studio.py: 3
- adapters/mistral.py: 3
- adapters/openai.py: 3
- adapters/together.py: 3
- adapters/gemini.py: 1
- adapters/llama_cpp.py: 1

**Verification**: `Get-ChildItem -Path adapters\ -Filter "*.py" -Recurse | ForEach-Object { $matches = Select-String -Path $_.FullName -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" -and $_.Context.PostContext -notmatch "#" }; if ($matches.Count -gt 0) { Write-Host "$($_.Name): $($matches.Count) violations" } }` returns zero output.

### Step 4: Fix adapters/ — `return <fallback>` patterns (10 patterns across 10 files)

For each `except Exception: return <fallback>` block:
- Change `except Exception:` to `except Exception as e:`
- Add WARNING trace/log BEFORE the return (using the file's existing convention)
- Keep the return statement unchanged

Files to fix (return-fallback count):
- adapters/cohere.py: 1
- adapters/deepseek.py: 1
- adapters/groq.py: 1
- adapters/huggingface.py: 1
- adapters/llama_cpp.py: 1
- adapters/lm_studio.py: 1
- adapters/mistral.py: 1
- adapters/ollama.py: 1
- adapters/openai.py: 1
- adapters/together.py: 1

**Verification**: `Get-ChildItem -Path adapters\ -Filter "*.py" -Recurse | ForEach-Object { $matches = Select-String -Path $_.FullName -Pattern "except Exception:" -Context 0,1 | Where-Object { $_.Context.PostContext -match "return" -and -not ($_.Context.PostContext -match "warning" -or $_.Context.PostContext -match "logger" -or $_.Context.PostContext -match "emit_trace" -or $_.Context.PostContext -match "print") }; if ($matches.Count -gt 0) { Write-Host "$($_.Name): $($matches.Count) violations" } }` returns zero output.

### Step 5: Fix gateways/telegram/gateway.py (4 pass + 1 continue = 5 blocks)

For each `except Exception: pass` block:
- Change `except Exception:` to `except Exception as e:`
- Add WARNING trace event + inline comment (this file uses `self._emitter.emit(TraceEvent(...))`)

For the `except Exception: continue` block (line 193):
- Change `except Exception:` to `except Exception as e:`
- Add WARNING trace event BEFORE `continue`

**Verification**: `Select-String -Path gateways\telegram\gateway.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" -and $_.Context.PostContext -notmatch "#" }` returns zero hits. AND `Select-String -Path gateways\telegram\gateway.py -Pattern "except Exception:" -Context 0,2 | Where-Object { $_.Context.PostContext -match "continue" -and -not ($_.Context.PostContext -match "emit|TraceEvent|warning|logger") }` returns zero hits (uses `-Context 0,2` to inspect lines after the `except` line — the trace emission call sits between `except Exception as e:` and `continue`, so it appears in PostContext).

### Step 6: Run per-file tests

```powershell
python -m pytest tests/test_web_server.py tests/test_auth_middleware.py tests/test_anthropic_adapter.py tests/test_cohere_adapter.py tests/test_deepseek_adapter.py tests/test_gemini_adapter.py tests/test_groq_adapter.py tests/test_huggingface_adapter.py tests/test_llama_cpp_adapter.py tests/test_lm_studio_adapter.py tests/test_mcp_adapter.py tests/test_mistral_adapter.py tests/test_ollama_adapter.py tests/test_openai_adapter.py tests/test_together_adapter.py -v --tb=short
```

Expected: all pass, zero new failures.

### Step 7: Run full test suite

```powershell
python -m pytest tests/ -q --tb=no
```

Expected: 1127 passed, 61 skipped, 0 failed, 0 warnings (baseline unchanged — only added trace events, logging, and inline comments).

## Verification gates (run in order, all must pass)

1. **Drift check**: `git diff --stat e5b74be..HEAD -- web/ adapters/ gateways/` — must be empty (no changes since plan was written). If non-empty, compare code excerpts and confirm only in-scope changes.

2. **Zero `except Exception: pass` without comment**:
```powershell
Get-ChildItem -Path web\,adapters\,gateways\ -Filter "*.py" -Recurse | ForEach-Object { $matches = Select-String -Path $_.FullName -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" -and $_.Context.PostContext -notmatch "#" }; if ($matches.Count -gt 0) { Write-Host "$($_.FullName): $($matches.Count) violations" } }
```
Expected: zero output (zero violations).

3. **Zero `except Exception: return/continue` without logging**:
```powershell
Get-ChildItem -Path web\,adapters\,gateways\ -Filter "*.py" -Recurse | ForEach-Object { $matches = Select-String -Path $_.FullName -Pattern "except Exception:" -Context 0,2 | Where-Object { ($_.Context.PostContext -match "return" -or $_.Context.PostContext -match "continue") -and -not ($_.Context.PostContext -match "warning" -or $_.Context.PostContext -match "logger" -or $_.Context.PostContext -match "emit_trace" -or $_.Context.PostContext -match "print") }; if ($matches.Count -gt 0) { Write-Host "$($_.FullName): $($matches.Count) violations" } }
```
Expected: zero output (every `return`/`continue` after `except Exception` now has logging before it).

4. **Per-file tests pass**: Output from Step 6.

5. **Full test suite measurement**: `python -m pytest tests/ -q --tb=no` — expected: 1127 passed, 61 skipped, 0 failed, 0 warnings. Paste literal `Select-Object -Last 3` output as evidence.

6. **Tag-push verification**: `git ls-remote --tags origin | findstr prompt-43c` returns the tag.

## STOP conditions

- If verification gate 1 reveals pre-existing failures unrelated to this plan, stop and report.
- If a file outside the in-scope list needs editing, stop and report.
- If the fix requires >50 lines of new code per file, stop — the plan was underscoped.
- **Pre-execution count check**: Before starting Step 1, run the grep commands from Gates 2 and 3 against the current codebase. If the counts don't match the plan's claimed totals (44 pass + 14 return-fallback + 1 continue = 59 fixable), stop and report the discrepancy before proceeding. The plan's numbers must match reality.
- If the broader grep (`-match "pass"`) reveals violations NOT counted in this plan, stop and report the discrepancy before proceeding.

## Out of scope

- Fixing any `except Exception` blocks that already have proper handling (18 blocks with `as e` + trace/logging)
- Standardising trace emission patterns across adapters (keep each file's existing convention)
- Refactoring sync methods to async (the audio_capture.py exception from prompt-42.1)
- Adding new tests for the trace events (behavior is unchanged — only logging added)
- Changing the return values of any fallback patterns
- Fixing any `except` blocks with narrower exception types (e.g., `except ValueError`, `except ConnectionError`)
- Any changes to files outside web/, adapters/, gateways/

---

## For Claude review (Devin: do not execute)

1. **Count verification**: Web/ pass subtotal (7) = server.py (6) + auth_middleware.py (1). This is a directory subtotal, not a duplicate count of server.py alone. Grand totals: 44 pass + 14 return + 1 continue = 59 fixable, 18 already handled, 77 total blocks. All per-file rows sum to their directory subtotals, and all directory subtotals sum to the grand totals.

2. **return-fallback count**: web/server.py has 4 (lines 79, 107, 119, 130). Adapters have 10 (one each in 10 files). Total = 14. This should now be consistent with the per-file tables.

3. **Gate 3 grep pattern**: The verification grep for `return`/`continue` blocks checks that the post-context contains logging keywords (`warning`, `logger`, `emit_trace`, `print`). This is a heuristic, not a precise check. Is this sufficient, or should we use a more structured verification (e.g., checking that every `except Exception as e:` block has either a `pass` with comment, a trace/log call, or is one of the 18 already-handled blocks)?

4. **web/server.py sync/async**: Step 1 instructs to use `logger.warning()` (sync-safe). Need to confirm this is correct by checking whether web/server.py's exception-handling code paths are sync or async.
