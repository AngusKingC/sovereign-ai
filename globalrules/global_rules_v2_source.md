# Devin Global Rules (v2)

These rules exist because each one prevents a specific failure that has actually occurred in this project. They are not aspirational — every rule traces to a documented mistake in the CHANGELOG. Follow them exactly. When in doubt, stop and ask.

**Numbering**: L1-Ln, aligned with project-internal landmine references in `SOVEREIGN_AI_HANDOFF.md`.

**Self-evolution (read this first)**: Rule **L20** is the meta-rule. Every plan's closing sequence MUST prompt Devin to propose new rules when it hits a recurring error pattern not covered here. This file is not static — it grows with the project's failures.

---

## Execution discipline

**L1. Follow the plan's verification gates in order. Run them, paste evidence, STOP on failure.**
Each prompt is delivered as a plan file with explicit verification gates and STOP conditions. Run each gate in the listed order. Do not mark a gate PASSED before running it. Do not mark a gate PASSED if its producing step is incomplete. Do not mark a gate SKIPPED unless the plan explicitly allows it. Gate output must be pasted literally into the CHANGELOG; "PASSED" without evidence is forbidden. If a gate fails, STOP and report — do not attempt to fix it by expanding scope. If a STOP condition fires, STOP. Plans 36 and 36.5 are the reference examples. **Never assert file content from memory** — when citing regex patterns, line numbers, method signatures, or tag formats, always read the actual file first (`Get-Content path\to\file`). The 35.5.2 saga involved a report claiming the regex was `r'<thinking>(.*?)</thinking>'` when it was actually `r'<think>(.*?)</think>'` — fluent, specific, and completely wrong.

**L2. Run the relevant test file after each file change. Run the full suite at gates, not after every edit.**
After editing a production file, run its specific test file (`python -m pytest tests/test_<name>.py -v`). Run the full suite (`python -m pytest tests/ -q`) only at the plan's verification gates — before commit, before tag. Running 1000+ tests after every single edit wastes 56+ seconds per run and creates incentive to mentally batch changes before testing, which defeats the purpose. Targeted tests catch regressions faster; full suite catches integration breaks at gates.

**L3. When you fix a bug, grep for the same pattern across the codebase before closing the prompt.**
35.6d fixed `MemoryRouter.fetch(dict)` in 2 files; the same bug existed in 15+ others. 35.6f fixed `backends=[]` in a test but not in the production call site. When you fix a bug, search for the same pattern everywhere: `Select-String "pattern" -Path . -Recurse -Include *.py`. Fix all instances or document which are deferred. Localised fixes for systemic bugs are the single most common source of regressions in this project.

**L4. Never silently substitute. If the spec says X, implement X. When in doubt, STOP and report. Do not improvise.**
If a plan specifies an exact value, format, method name, or file scope, implement exactly that. If a different approach seems better, STOP and flag it in Implementation Notes as an explicit deviation with rationale. Do not silently substitute. Do not attempt to fix an ambiguity by expanding scope, substituting a different approach, or silently working around it. The `<thinking>` vs `<thought>` vs `<think>` saga (35.5/35.5.1/35.5.2) was three prompts of this mistake. A test suite that passes 100% green proves nothing if the tests were written to match the deviation rather than the spec. **If anything is ambiguous** — a spec that seems wrong, a test that fails for an unexpected reason, a file outside scope that seems to need editing, a commit that didn't push, a tag that didn't create — STOP and report. Every regression in this project's history started with someone improvising past a STOP condition.

**L5. Do not expand scope when tests find pre-existing issues outside the plan.**
If a compliance test or new test reveals pre-existing violations in files outside the current plan's scope, do not fix them in the current prompt. Log them in the CHANGELOG, note them in the handoff's "What's broken" section, and flag for a dedicated housekeeping plan. Scope creep mixed into a feature plan entangles debt work with feature work and makes both harder to roll back.

## Code construction

**L6. TraceEvent is defined in `core/observability.py`. Use exactly these fields: `event_type`, `component`, `level`, `message`, `data`, `duration_ms`.**
Never use `layer`, `payload`, or `success` — they belong to an old schema in `core/schemas.py` that was never fully migrated. Never import TraceEvent from `core/schemas.py`. The correct import is `from core.observability import TraceEvent`. The correct construction is `TraceEvent(event_type=..., component=..., level=..., message=..., data=..., duration_ms=...)`. Using the old fields causes silent failures because the old and new schemas have different field names.

**L7. Every class that emits trace events MUST use constructor-injected emitter. Never use the global `emit_trace()` function.**
Correct pattern: `def __init__(self, ..., emitter: TraceEmitter | None = None): self._emitter = emitter or MemoryTraceEmitter()`. Correct emit call: `await self._emitter.emit(TraceEvent(...))`. Using `emit_trace()` instead means every trace event test will fail with `assert 0 > 0`. The global `emit_trace()`, `get_trace_emitter()`, `set_trace_emitter()`, `_global_emitter`, and `_global_registry` in `core/observability.py` and `core/commands.py` are known violations scheduled for removal — never use them in new or modified code.

**L8. Raise domain exceptions OUTSIDE try-except blocks. Never broad-except without a trace event.**
Raising inside a `try-except Exception` silently swallows the error. Reserve `try-except` only for trace calls and external I/O that must not crash the application. If you must use a broad `except Exception`, emit a trace event at WARNING level with the exception message inside the except block. The codebase has dozens of `except Exception: pass` blocks that hide real failures — every audit finding about "dead wiring" traces back to one of these. Do not add more.

**L9. When fixing a production file, fix its test file in the same step.**
Never fix a batch of production files and leave tests for later. The sequence is always: fix one production file → fix its test file → run the relevant test file → confirm zero new failures → only then move to the next file. Leaving tests unupdated after fixing production files causes `AttributeError` on the patch target and creates more failures than existed before the fix.

**L10. Do not remove working implementation to make a test pass.**
When a regression appears, find the root cause and fix the test — never remove the implementation. Removing implementation to fix a test is always wrong. The escalation logic was incorrectly removed from `core/orchestrator.py` in Prompt 26 because of this mistake; it took Prompt 22.7 to confirm the wiring was still intact.

**L11. Verify field and class names against the actual schema file before using them.**
Before using any class or field from `core/schemas.py`, verify the exact name exists: `Select-String "^class " -Path core/schemas.py`. Never assume field names match old specs or documentation. Prompt 23 changed `EscalationDecision` and `StrategicContext` fields. Prompt 35.6d fixed a bug where the orchestrator set `StrategicContext.recent_task_summary` — a field that doesn't exist on the schema. Always verify against source.

**L12. Patch at the location where a class is defined, not where it is used.**
If the import is `from core.foo import Bar` and the code does `Bar(...)`, patch `core.foo.Bar`, not the importing module's `Bar`. If the import is inside a method body, patch the definition module. Use `Select-String "import ClassName" -Path . -Recurse -Include *.py` to find the correct patch path. Wrong patch targets are the most common cause of test failures that pass in isolation but fail in the full suite.

**L13. Never mutate Pydantic model instances after construction in tests.**
Always construct the model with the desired state from the start. Mutation via attribute assignment either raises `ValidationError` or is silently ignored. If a test needs a model in a specific state, build it that way — don't build a default and then mutate.

## Testing

**L14. Tests must verify behaviour, not just confirm the code runs.**
A test that mocks the system under test and asserts `True` is not a test — it is a smoke check. Every test must capture the actual constructed object or call the actual function and assert something specific about the result. The 35.6b `test_serve_constructs_full_orchestrator` and `test_serve_worker_factory_accessible` tests were `assert True` smoke tests — they passed but verified nothing. If your test mocks the SUT, rewrite it. The pattern: construct real objects with mocked dependencies (not mocked SUT), call real methods, assert specific properties of the result. Do not mark a test `@pytest.mark.skip` for tests that "couldn't be mocked" — fix the mock or refactor the SUT.

**L15. In tests, construct `MemoryTraceEmitter()` and pass it via constructor injection. Retrieve events via `emitter.get_events()`, never `emitter.events`.**
Correct pattern:
```python
emitter = MemoryTraceEmitter()
obj = SomeClass(emitter=emitter)
await obj.do_thing()
events = emitter.get_events()
assert len(events) > 0
assert any(e.event_type == TraceEventType.SOME_EVENT for e in events)
```
Never use `emitter.events` — it's not the public API. Never use `ConsoleTraceEmitter` in tests — it prints to stdout and can't be inspected.

## Datetime consistency

**L19. Tests and production code MUST use the same timezone strategy. Never mix naive and aware `datetime` objects.**
This is the landmine that hit Plan 53: tests used `datetime.utcnow()` (naive) while production used `datetime.now(timezone.utc)` (aware); comparison raised `TypeError: can't compare offset-naive and offset-aware datetimes`. When you fix a datetime issue on one side, grep for the other side immediately: `Select-String "datetime\.(utcnow|now)" -Path . -Recurse -Include *.py`. Both sides must use the same call. **Preferred project convention**: `datetime.now(timezone.utc)` everywhere (aware, no deprecation in Python 3.12+). Never use `datetime.utcnow()` in new code. When fixing one side, fix the other side in the same step (L9 applies).

## CHANGELOG and documentation

**L16. The CHANGELOG must match the commit. Verify before reporting completion.**
Before writing the CHANGELOG entry, run `git show --stat HEAD` and verify the file list matches what you actually changed. If the commit added 14 lines of code, the CHANGELOG must not say "no code changes required." 35.6c's CHANGELOG said "Files Modified: None" while the commit added 14 lines — this is the pattern to avoid. The CHANGELOG is a contract with the next reader; if it doesn't match the commit, it's a lie.

**L17. CHANGELOG format is simplified — ~10 lines per plan. Title, changed files, result, test count math. Record only non-trivial decisions, not every failed attempt.**
Each plan's CHANGELOG entry should be approximately 10 lines containing:
1. **Title**: `## prompt-{N} — {plan title}`
2. **Changed files**: bullet list, in-scope only (verified against `git show --stat`)
3. **Result**: 1-2 sentences — what was achieved, what was deferred
4. **Test count math**: `baseline + new = final` (e.g. `1166 + 1 = 1167`). If the arithmetic doesn't work, investigate before reporting success — either the baseline was wrong, the final was wrong, or tests broke that you didn't notice. State the exact test command used for both baseline and final — different `--ignore` flags produce different counts.
5. **Non-trivial decisions only**: record abandoned approaches, ambiguous architecture decisions, or deviations from spec — NOT every failed test, NOT every multi-edit file. If a decision was straightforward, it does not belong in the CHANGELOG.

The previous verbosity rule (old rule 17: "record every failed test, every abandoned approach, every multi-edit file") is **withdrawn** — it pushed entries to 30+ lines and obscured signal. The 35.6d CHANGELOG was acknowledged as "below standard verbosity" under the old rule; under this rule, 35.6d's actual content (3-line result + file list + math) would have been correct.

## Git and closing sequence

**L18. The correct closing sequence for every prompt:**
1. Run full test suite: `python -m pytest tests/ -q` (no `--ignore` flags — Plan 36.5 made this unnecessary). Confirm zero new failures vs the plan's stated baseline.
2. `ruff check <files_touched>` — zero errors.
3. `mypy <files_touched> --ignore-missing-imports` — zero errors. **Never `mypy .`** — file-scoped only.
4. `git add <in-scope files only> && git commit -m "checkpoint: prompt-{N}"`
5. `git tag prompt-{N}`
6. **Tag verification (mandatory):** `git show prompt-{N} --stat` — verify the file list contains ONLY files in this plan's scope. If any unexpected file appears, `git tag -d prompt-{N}`, clean the working tree, re-commit, re-tag.
7. Update `CHANGELOG.md` (append-only, using `Add-Content` — never paste into editor, never use insert operations). See Appendix A2 for the exact procedure.
8. Update `SOVEREIGN_AI_HANDOFF.md` per the plan's closing-step instructions.
9. **Rule proposal (L20):** scan your work this prompt for recurring error patterns or landmines not covered by `global_rules.md`. If found, append a "Rule proposal" section to your closing report (see L20 for format). GLM will review and update `global_rules.md` if accepted.
10. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-{N} changelog and handoff update"`
11. `git push origin master && git push origin prompt-{N}`
12. **Post-push verification (mandatory):** `git ls-remote --tags origin | Select-String "prompt-{N}"` — verify the tag exists on the remote. The 35.5.2 saga was a tag that was reported as pushed but never existed on origin. If the tag doesn't appear on origin, the push failed — fix it before reporting completion.

The checkpoint script (`scripts/checkpoint.py`) is unreliable — always do this manually. Code is committed and tagged BEFORE docs are updated. Docs are committed separately after the tag is clean.

## Meta-rule: self-evolution

**L20. When you hit a recurring error pattern or a landmine not covered by these rules, propose a new rule to GLM in your closing report. This file grows with the project's failures.**
This is the single most important rule. `global_rules.md` is not static — it is a living document that captures every failure mode this project has actually hit. If you encountered a failure this prompt that:
- Recurred in 2+ previous prompts (per CHANGELOG history), OR
- Required significant debugging time, OR
- Was not anticipated by an existing rule,

then propose a new rule. Format the proposal in your closing report as:

```
## Rule proposal for global_rules.md

Trigger: <what happened this prompt — concrete, e.g. "TypeError comparing
naive and aware datetime in test_calendar.py line 47">
Recurrence: <prompt numbers where this same pattern bit, or "first occurrence">
Proposed rule: L{n+1}. <one-line rule statement>
Anchor: <prompt number + file + line, e.g. "Plan 53, tests/test_calendar.py:47">
Why existing rules didn't catch it: <e.g. "L9 covers fix-test-together but
not timezone consistency between test and production">
```

GLM will review each proposal after the plan completes. Accepted proposals get added to this file as L{n+1} with the anchor preserved. Rejected proposals get a one-line reason in the next plan's brief.

**If your closing report contains no rule proposal section, GLM will assume you encountered no new failure patterns and will ask you to confirm before placing the next plan.** This is intentional — silence is not evidence of perfect execution; it's evidence you didn't reflect.

## CHANGELOG append position

**L21. CHANGELOG entries are ALWAYS appended to the END using `Add-Content -Encoding utf8`. NEVER insert at the top. Oldest entry at top, newest at the bottom.**
This rule was added by Devin itself during Plan 53 after the user had to manually rebuild a CHANGELOG where Devin had inserted prompt-53's entry at the TOP instead of appending to the BOTTOM. The chronological-order invariant (oldest top, newest bottom) is non-negotiable. The simplified format (~10 lines per entry, per L17) applies to every entry. Use the procedure in Appendix A2 — specifically: `Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Value "..." -Encoding utf8`. Never paste into the IDE editor. Never use insert-at-position operations. Before appending, record the current line count with `[System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count`; after appending, verify the new count exceeds the old count and that the last 5 lines match the entry you just wrote.

## Environment

**L22. This project runs on Windows. Use PowerShell, not Unix commands.**
Never use `grep`, `cat`, `touch`, `head`, `tail`, or any Unix shell command. Always use PowerShell equivalents — see Appendix A1 for the full mapping table.

---

## Appendix A1: PowerShell command cheatsheet (reference, not a rule)

| Need | PowerShell | Never use |
|---|---|---|
| Search file contents | `Select-String "pattern" -Path path\to\file` | `grep` |
| Recursive search (Python only) | `Select-String "pattern" -Path . -Recurse -Include *.py` | `grep -r` |
| Count pattern matches | `Select-String -Path file -Pattern "pat" \| Measure-Object -Line` | `grep -c` |
| Read entire file | `Get-Content path\to\file` | `cat` |
| Read first N lines | `Get-Content file \| Select-Object -First N` | `head -N` |
| Read last N lines | `Get-Content file \| Select-Object -Last N` | `tail -N` |
| Read lines N-M | `Get-Content file \| Select-Object -Skip (N-1) -First (M-N+1)` | `sed -n` |
| Line count | `(Get-Content file).Count` | `wc -l` |
| List directory | `Get-ChildItem` | `ls` |
| Create empty file | `New-Item -Path file -ItemType File` | `touch` |
| Group + count | `\| Group-Object \| Sort-Object Count -Descending` | `sort \| uniq -c` |
| Filter lines | `\| Where-Object { $_ -notmatch "import" }` | `grep -v` |

## Appendix A2: CHANGELOG append procedure (Windows/PowerShell)

Always use `Add-Content` to append to `CHANGELOG.md`. Never paste into the editor. Never use insert operations.

1. **Before appending**: record current line count with `[System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count` — never `Get-Content | Measure-Object` (truncates large files).
2. **Append with**: `Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Value "..."` — close the file in the IDE first; a locked file causes `IOException`. For entries longer than 20 lines, write the entry to a temp file first (`$entry | Set-Content -Path $temp -Encoding utf8`), then `Get-Content $temp | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8` to preserve UTF-8.
3. **After appending**: verify new count exceeds previous count, verify last 5 lines with `Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 5`, verify the boundary with `$lines[$oldCount-1..$oldCount+4]`.

---

## Revision history

- **v2.1 (2026-06-21)**: Added L21 (CHANGELOG append position) — this rule was self-added by Devin during Plan 53 as old Rule 25, then merged into v2 to preserve it when the v2 file ships. Total rules: L1-L22 (22 rules total). L19 (datetime consistency), L20 (self-evolution meta-rule), and L21 (CHANGELOG append position) are all numbered rules within L1-L22, not additional to them.
- **v2 (2026-06-21)**: Deduplicated 24 rules → 22 (L1-L22). Merged old 1+24→L1, 4+23→L4, 16+17→L16+L17 (rewritten). Added L19 (datetime consistency — Plan 53 landmine). Added L20 (self-evolution meta-rule — structural rule-proposal mechanism). Moved PowerShell cheatsheet (old 22) and CHANGELOG append procedure (old 21) to appendices A1/A2. Fixed Select-String syntax in old rules 11/12 (added `-Path`/`-Include *.py`). Renumbered 1-24 → L1-L22 with L19/L20 inserted.
- **v1**: Original 24-rule file. Each rule anchored to a specific historical failure (35.5.2 saga, 35.6d/b/c/f, Plan 36/36.5, Prompt 22.7, Prompt 26, etc.).
