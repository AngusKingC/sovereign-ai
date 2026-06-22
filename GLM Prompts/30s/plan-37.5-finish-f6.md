# Plan 37.5: Finish F6 — scoped_read/write, trajectory_exporter, escalation.py, and Claude's blocking fixes

> **Executor instructions**: This plan closes out F6 properly. Four mandates: (1) add `scoped_read`/`scoped_write` to MemoryRouter and update 3 caller files, (2) fix `system/trajectory_exporter.py`'s `fetch(Type, filter_func=...)` pattern, (3) fix `core/escalation.py:146` `ApprovalGate.request` → `request_approval`, (4) apply Claude's 4 blocking fixes from the original Plan 37 review that were not addressed in prompt-37 or 37.1. Plus 2 rolled-in items from the prompt-37.1 verification: TYPE_CHECKING import for StrategicContext, and CHANGELOG checkpoint hash correction.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-37.1..HEAD -- core/memory_router.py core/approval_trust.py core/escalation.py core/retention.py system/trajectory_exporter.py skills/notes/notes_skill.py skills/reminder/reminder_skill.py tests/test_approval_trust.py tests/skills/test_notes_skill.py tests/skills/test_reminder_skill.py tests/test_trajectory_exporter.py tests/test_escalation.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> If any of these files changed since prompt-37.1, compare the "Current state" against live code before proceeding; on mismatch, STOP.

## Status

- **Priority**: P1 (closes F6 — currently "PARTIALLY FIXED" in handoff)
- **Effort**: M
- **Risk**: MED (touches 7 production files + 5 test files; the scoped_read/write design decision affects 3 caller files with different calling conventions)
- **Depends on**: prompt-37.1 (commit `41cb13b`, tag `prompt-37.1`)
- **Planned at**: commit `20a1b54`, 2026-06-18
- **In scope**: 7 production files + 5 test files + 2 documentation files (handoff + CHANGELOG) + 1 non-repo memory file (global_rules.md, optional — see Step 9)
- **Out of scope**: TUI memory + cognition stack wiring (Plan 37.6), broad-except audit (Plan 38+), InputSanitiser wiring (Plan 41+), trajectory_exporter's actual functionality verification (Plan 45+ — depends on a real eval harness)

## Why this matters

Prompt-37 added 4 new MemoryRouter methods (`fetch_by_filter`, `write_to_collection`, `get_global_context`, `set_global_context`) and fixed 33 call sites across 12 files. Prompt-37.1 cleaned up the test regressions. F6 is currently marked "PARTIALLY FIXED" in the handoff because three things remain:

1. **`scoped_read` / `scoped_write` are phantom methods** — called from `core/approval_trust.py` (3 sites), `skills/notes/notes_skill.py` (6 sites), and `skills/reminder/reminder_skill.py` (4 sites). 13 call sites total. The methods don't exist on `MemoryRouter` or `ScopedMemoryRouter`. The original Plan 37 audit (finding A1) flagged this as the most time-sensitive item; it was deferred to keep 37's scope manageable. Without these methods, ApprovalTrustRegistry and the notes/reminders skills are still silently broken at runtime — `AttributeError` swallowed by broad excepts.

2. **`system/trajectory_exporter.py` uses a pattern Plan 37 didn't cover** — `self._router.fetch(Task, filter_func=...)` and `self._router.fetch(WorkerOutput, filter_func=...)`, passing CLASS OBJECTS as the first argument rather than filter dicts. Devin correctly hit Plan 37's STOP condition ("if a caller uses a pattern not covered by the 5 patterns, STOP") and deferred the file. This plan addresses it.

3. **`core/escalation.py:146` calls `self._approval_gate.request(approval_request)`** — but ApprovalGate has no `request` method. The actual method is `request_approval` (verified at `core/approval_gate.py:239`). Plan 37 listed this in Step 3 as a co-located fix but it was out of scope (escalation.py wasn't in the 14-file list). Devin correctly did not touch it. This plan fixes it.

Additionally, Claude's review of the original Plan 37 draft identified 4 blocking fixes that were never applied (rolled into this plan because they're all F6-class issues or documentation gaps about F6). And the prompt-37.1 verification surfaced 2 small items that roll in here because 37.5 already touches the same files.

## What's broken (verified against live repo at commit 20a1b54)

### A. `scoped_read` / `scoped_write` — phantom methods on MemoryRouter (13 call sites, 3 files)

**MemoryRouter's current interface** (verified at `core/memory_router.py` lines 365, 456, 516, 537 — the 4 methods from prompt-37): `fetch`, `write`, `list_keys`, `fetch_by_filter`, `write_to_collection`, `get_global_context`, `set_global_context`. **No `scoped_read` or `scoped_write`.**

**Caller files and their calling conventions** (verified by reading each call site):

**`core/approval_trust.py`** — 3 call sites, keyword form:
- Line 103: `await self.memory_router.scoped_read(scope="approval_trust", key=command)` — returns single dict or None
- Line 139: `await self.memory_router.scoped_write(scope="approval_trust", key=command, data={"level": ..., "command": ...})` — write
- Line 180: `await self.memory_router.scoped_write(scope="approval_trust", key=command, data=None)` — delete (data=None means delete)

**`skills/notes/notes_skill.py`** — 6 call sites, positional form:
- Line 147: `await self._memory_router.scoped_write("notes", f"notes:{note_id}", note)` — write
- Line 220: `await self._memory_router.scoped_read("notes", "notes:*")` — returns LIST (wildcard key)
- Line 299: `await self._memory_router.scoped_read("notes", f"notes:{note_id}")` — returns single dict or None
- Line 436: `await self._memory_router.scoped_read("notes", f"notes:{note_id}")` — same
- Line 467: `await self._memory_router.scoped_write("notes", f"notes:{note_id}", note)` — write
- Line 601: `await self._memory_router.scoped_read("notes", f"notes:{note_id}")` — same

**`skills/reminder/reminder_skill.py`** — 4 call sites, positional form:
- Line 146: `await self._memory_router.scoped_write("reminders", f"reminders:{reminder_id}", reminder)` — write
- Line 219: `await self._memory_router.scoped_read("reminders", "reminders:*")` — returns LIST (wildcard)
- Line 301: `await self._memory_router.scoped_read("reminders", f"reminders:{reminder_id}")` — single dict or None
- Line 325: `await self._memory_router.scoped_write("reminders", f"reminders:{reminder_id}", reminder)` — write

**Required method signatures** (must support BOTH calling conventions — keyword AND positional — without PEP 570 positional-only markers):

```python
async def scoped_read(
    self,
    scope: str,
    key: str,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """
    Read from a named scope.
    
    Supports both calling conventions natively — ordinary Python parameters
    are positional-or-keyword by default, so scoped_read("notes", "notes:*")
    and scoped_read(scope="notes", key="notes:*") both work without any
    special machinery.
    
    Args:
        scope: Collection/scope name (e.g., "approval_trust", "notes", "reminders").
        key: Document key within the scope. May end with "*" for wildcard reads.
    
    Returns:
        Single dict (or None) for exact key, list of dicts for wildcard key.
    """

async def scoped_write(
    self,
    scope: str,
    key: str,
    data: dict[str, Any] | None = None,
) -> None:
    """
    Write (or delete) data in a named scope.
    
    Supports both calling conventions natively — scoped_write("notes", "key", data)
    and scoped_write(scope="trust", key="cmd", data=None) both work.
    
    Args:
        scope: Collection/scope name.
        key: Document key within the scope.
        data: Dict to write. If None, delete the entry (used by approval_trust
              to revoke trust).
    """
```

**Do NOT use PEP 570 positional-only markers (`/`) or `*positional_args`** in these signatures. An earlier draft of this plan used `/` to support both conventions — that was wrong: `/` makes parameters positional-only, which would break the keyword form used by `core/approval_trust.py`. Ordinary parameters (`def scoped_read(self, scope: str, key: str)`) already support both forms because Python parameters are positional-or-keyword by default. The simpler signature is the correct signature.

**Implementation approach**: Delegate to `fetch_by_filter` and `write_to_collection` (added in prompt-37). Internally:
- `scoped_read(scope, key)` → for exact key: `fetch_by_filter(filter={"_scope": scope, "_key": key}, collection=scope)` (NO `limit=1` — see ordering bug note below), then return the **last** non-tombstone match (backends are append-only, so the latest write is the most recent). For wildcard key (ends with `*`): `fetch_by_filter(filter={"_scope": scope}, collection=scope)`, filter by key prefix in Python, exclude tombstones, return list.
- `scoped_write(scope, key, data)` → if data is None, write a tombstone (see Step 1.5); otherwise `write_to_collection(data={**data, "_scope": scope, "_key": key}, collection=scope, document_id=key)`

**Critical ordering bug to avoid** (flagged in review, second round): `fetch_by_filter` applies `limit` by slicing `all_results[:limit]` after collecting matches in storage order. Backends are append-only, so for a given key there may be multiple entries (original + tombstone, or original + later update). Using `limit=1` would return the **first** (oldest) entry, not the latest. Two consequences:
1. `scoped_read` exact-key path must NOT use `limit=1`. Fetch all matches, then check the chronologically LAST entry's tombstone status — return None if the last entry is a tombstone, else return the last entry. **DO NOT filter tombstones first and then take the last non-tombstone** — that ordering is also a bug. For storage `[entry1, tombstone]`, filter-then-take-last leaves `[entry1]` and returns the stale entry1 instead of None. The correct check is recency-first: `last = results[-1]; return None if last is a tombstone else last`.
2. The same ordering bug exists in `get_global_context` from prompt-37 — calling `set_global_context` twice would make `get_global_context` return the first value, not the latest. Plan 45+ should fix `get_global_context` to use the same "last entry wins, tombstone-aware" pattern. For now, 37.5 only fixes `scoped_read` — do not expand scope to fix `get_global_context` (STOP condition).

**Wildcard path dedup requirement** (flagged in review, second round): The wildcard path (`scoped_read("notes", "notes:*")`) must deduplicate by `_key` — group entries by key, keep only the chronologically last entry for each key, then exclude tombstones. Without dedup, an edit (write twice under the same key) would cause the wildcard listing to return both the stale and current copies. Gate 4 in the original draft didn't catch this because it wrote two distinct keys (`notes:1`, `notes:2`), not the same key twice. Gate 4a (added below) exercises the edit case.

### B. `system/trajectory_exporter.py` — `fetch(Type, filter_func=...)` pattern (2 call sites, 1 file)

**Current state** (verified at lines 64, 69):
```python
tasks = await self._router.fetch(Task, filter_func=lambda t: t.current_state == TaskStatus.COMPLETE and t.complexity_score >= min_rating)
# ...
outputs = await self._router.fetch(WorkerOutput, filter_func=lambda o: o.task_id == task.task_id)
```

This passes CLASS OBJECTS (`Task`, `WorkerOutput`) as the first argument to `fetch`, with a `filter_func` kwarg. The existing `fetch(task: Task)` interface expects an INSTANCE, not a class. This is a fundamentally different query shape — "give me all rows of type X matching predicate Y" — and doesn't fit any of prompt-37's 5 patterns.

**Fix options** (pick one based on what makes semantic sense for trajectory export):

**Option 1 (recommended)**: Use `fetch_by_filter` with a filter dict. The `filter_func` lambdas need to be replaced with filter dicts because `fetch_by_filter` doesn't support arbitrary predicates (it does support a `filter_func` parameter — see prompt-37's interface).
```python
# Fetch all tasks with current_state == COMPLETE
tasks = await self._router.fetch_by_filter(
    filter={"current_state": TaskStatus.COMPLETE},
    collection="tasks",
    filter_func=lambda t: t.get("complexity_score", 0) >= min_rating,
)
# Fetch all WorkerOutputs for this task_id
outputs = await self._router.fetch_by_filter(
    filter={"task_id": str(task.task_id)},
    collection="worker_outputs",
)
```

**Option 2 (deferred)**: If the backends don't actually store Tasks and WorkerOutputs as filterable dicts (likely — they're stored as Task objects with intent strings), then trajectory_exporter needs a different data model entirely. This is a bigger redesign and probably belongs in Plan 45+ (depends on an eval harness). For now, mark the file as `# TODO: Plan 45 — redesign trajectory export to use fetch_by_filter properly` and either skip the file or make it return an empty list with a WARNING trace event.

**STOP condition for Step 2**: If Option 1 doesn't work because the backends don't store Tasks/WorkerOutputs in a way that `fetch_by_filter` can query, STOP. Use Option 2 (return empty list + WARNING trace) and document in the CHANGELOG that trajectory export is non-functional until Plan 45.

### C. `core/escalation.py:146` — `ApprovalGate.request` is phantom (1 call site, 1 file)

**Current state** (verified):
```python
approval_response = await self._approval_gate.request(approval_request)
```

**ApprovalGate's actual methods** (verified at `core/approval_gate.py`):
- Line 239: `async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:`
- Line 372: `async def respond(self, request_id, approved, responder, always_approve=False) -> ApprovalResponse`
- Line 548: `async def check_scope(self, session_id, action_type, parameters) -> bool`
- Line 586: `async def add_scope(self, scope: ApprovalScope) -> None`
- Line 643: `async def load_scopes(self, session_id: str) -> None`
- Line 659: `async def expire_pending(self) -> None`

There is no `request` method. The fix is a 1-line change: `.request(` → `.request_approval(`.

**Note on `core/instruction_versioning.py:148`**: An earlier draft of this plan said to "also check" this file for a similar phantom `submit_for_approval` call. That instruction has been removed — `instruction_versioning.py` is NOT in the 7-file in-scope list and NOT in the drift-check command, so telling Devin to fix it would repeat the exact scope contradiction this plan's D4 closes out. If `instruction_versioning.py:148` does have a similar bug, it goes in Plan 37.6 or a separate triage plan.

### D. Claude's 4 blocking fixes from original Plan 37 review

These were never applied because Plan 37 was already in flight when the review came back. They're documentation/scope-justification fixes, not code changes (except D4):

**D1. `core/retention.py` documentation justification** — The handoff's F6 location list (line 59) and the Plan 37 entry (line 266) both list `core/retention.py` as an affected file, but Plan 37 dropped it without explanation. Verified reason: retention.py uses the CORRECT signatures (`fetch(task)`, `write(dict)`) — no `collection=`/`document_id=`/`limit=` kwargs. It was never affected by F6. The handoff's inclusion was inaccurate. **Action**: Add a note to the handoff's F6 entry explaining this, so the next reader isn't confused.

**D2. File count reconciliation** — The handoff's "Next 5 prompts" entry for Plan 37 says "12 files, ~70 call sites" but the body says "14 files". Plan 37.1 didn't fix this. **Action**: Update the handoff's Plan 37 entry to reflect the actual count (13 production files touched + memory_router.py + 8 test files = 22 files, 33 call sites fixed). Be precise.

**D3. Line-number completeness in Plan 37's scope** — Not applicable to this plan; it was a Plan 37 drafting issue. **Action**: No work needed in 37.5. Note in CHANGELOG that this lesson is captured by Rule 18.

**D4. `core/escalation.py:146` scope violation in Plan 37's Step 3** — Plan 37 listed this as a co-located fix in a section whose STOP condition forbade touching out-of-scope files. Devin correctly did not touch it. **Action**: This plan fixes the actual bug (Step 3 above), which closes the contradiction. Add a note to the CHANGELOG explaining the resolution.

### E. Rolled-in items from prompt-37.1 verification

**E1. TYPE_CHECKING import for StrategicContext** — Prompt-37.1 added the string annotation `"StrategicContext | None"` to `get_global_context` (line 516) but did NOT add `StrategicContext` to the TYPE_CHECKING import block. Mypy would report `Name 'StrategicContext' is not defined`. Gate 9 was skipped in 37.1 because mypy wasn't installed.

**Current TYPE_CHECKING block** (verified at lines 23-27):
```python
if TYPE_CHECKING:
    from core.memory_compactor import MemoryCompactor

if TYPE_CHECKING:
    from core.observability import TraceEmitter
```

**Fix**: Add StrategicContext to one of these blocks (or create a third):
```python
if TYPE_CHECKING:
    from core.memory_compactor import MemoryCompactor
    from core.schemas import StrategicContext
```

**E2. CHANGELOG checkpoint hash mismatch** — Prompt-37.1's CHANGELOG entry says "Checkpoint Commit: 9272bd7af3af6a46c5a3c761e1990423ad670062" but that's prompt-37's commit. Should be `41cb13b88adaa293da830d4eca6f2b1a796c92f6` (prompt-37.1's commit). This violates `global_rules.md` Rule 16 ("CHANGELOG must match commit") and Rule 20 ("closing sequence includes tag verification AND post-push verification") — both rules are in Devin's `global_rules.md` at `C:\Users\King\.codeium\windsurf\memories\global_rules.md`, NOT in the handoff's Architecture Rules section (which only goes to 18, and where Rule 16 is about auth middleware). When this plan cites "Rule 16" or "Rule 20," it means the global_rules.md numbering, not the handoff. The two rule documents overlap in coverage but diverge in numbering — itself a drift issue worth flagging to GLM for future plans.

**Fix**: Append a correction note to the prompt-37.1 CHANGELOG entry (do not edit history — append-only per global_rules):
```
### Checkpoint Commit Correction
- Originally listed as 9272bd7af3af6a46c5a3c761e1990423ad670062 (prompt-37's commit) — incorrect.
- Actual prompt-37.1 commit: 41cb13b88adaa293da830d4eca6f2b1a796c92f6
- Tag prompt-37.1 points to 41cb13b (verified via `git rev-parse prompt-37.1`)
```

## What to change

### Step 1 — Add `scoped_read` and `scoped_write` to MemoryRouter

**File**: `core/memory_router.py`
**Insert after**: the `set_global_context` method (after line 545 or wherever it ends — read the file first to confirm)

Add the two methods from the interface in Section A above. Implementation:

```python
async def scoped_read(
    self,
    scope: str,
    key: str,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Read from a named scope. See interface docstring in Section A."""
    if key.endswith("*"):
        # Wildcard read — return list
        prefix = key[:-1]
        all_results = await self.fetch_by_filter(
            filter={"_scope": scope},
            collection=scope,
        )
        # Group by _key, keep only the chronologically last entry for each key,
        # then exclude tombstones (deletes). This prevents stale duplicates
        # when a note/reminder is edited (written twice under the same key):
        # without dedup, the wildcard listing would return both the stale
        # and current copies. Group-by-key + take-last mirrors the exact-key
        # path's recency-first logic.
        by_key: dict[str, dict] = {}
        for r in all_results:
            k = r.get("_key", "")
            if k.startswith(prefix):
                by_key[k] = r  # later writes overwrite earlier ones in dict order
        return [v for k, v in by_key.items() if not v.get("_deleted", False)]
    else:
        # Exact key read — return single dict or None
        # CRITICAL: do NOT use limit=1 — backends are append-only, so the
        # latest write is the most recent match. limit=1 would return the
        # oldest entry, which may be a stale value or a pre-tombstone original.
        results = await self.fetch_by_filter(
            filter={"_scope": scope, "_key": key},
            collection=scope,
        )
        # Check the LAST entry's tombstone status — DO NOT filter tombstones
        # first and then take last. The filter-then-take-last ordering is a
        # bug: for storage [entry1, tombstone], filtering leaves [entry1],
        # and taking last returns entry1 (the stale value) instead of None.
        # The correct check is: look at the chronologically last entry,
        # and only then ask whether THAT entry is a tombstone.
        if not results:
            return None
        last = results[-1]
        return None if last.get("_deleted", False) else last

async def scoped_write(
    self,
    scope: str,
    key: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Write (or delete) data in a named scope. See interface docstring in Section A."""
    if data is None:
        # Delete — see Step 1.5
        await self._delete_from_collection(scope, key)
        return
    
    # Augment data with scope metadata
    write_data = data.copy() if isinstance(data, dict) else {"value": data}
    write_data["_scope"] = scope
    write_data["_key"] = key
    
    await self.write_to_collection(
        data=write_data,
        collection=scope,
        document_id=key,
    )
```

**Note on signatures**: The parameters are ordinary positional-or-keyword (no `/`, no `*positional_args`). This is intentional — both calling conventions work natively. An earlier draft used PEP 570 `/` which would have broken keyword calls. Do not re-add it.

### Step 1.5 — Add a private `_delete_from_collection` helper (needed for scoped_write with data=None)

**File**: `core/memory_router.py`
**Insert before**: the `scoped_read` method

The existing `fetch_by_filter` and `write_to_collection` don't support deletion. The `scoped_write(scope, key, data=None)` semantic (used by `core/approval_trust.py:180` to revoke trust) requires deletion. Add:

```python
async def _delete_from_collection(self, collection: str, document_id: str) -> None:
    """Delete a document from a collection by document_id.
    
    This is a best-effort delete — backends that don't support deletion
    will silently no-op. Emits a WARNING trace event on failure.
    """
    # Backends don't have a unified delete interface. For now, write a
    # tombstone marker that scoped_read can filter out.
    # TODO: Plan 45+ — add proper delete() to MemoryBackend interface.
    await self.write_to_collection(
        data={"_deleted": True, "_scope": collection, "_key": document_id},
        collection=collection,
        document_id=document_id,
    )
```

Then update `scoped_read` to filter out tombstones (already shown in Step 1's implementation — the `if not results: return None` / `last = results[-1]` / `return None if last.get("_deleted", False) else last` block). The tombstone check MUST happen on the chronologically last entry, NOT on a filtered list. The original draft of this plan filtered tombstones first and then took the last non-tombstone — that was a bug: for storage `[entry1, tombstone]`, filter-then-take-last returns the stale entry1 instead of None. The Step 1 implementation is correct — verify it does not regress.

The wildcard path also needs dedup-by-key (already shown in Step 1's implementation — the `by_key: dict[str, dict] = {}` loop). Without dedup, an edit (write twice under the same key) would return both copies in the wildcard listing. Gate 4a (below) exercises this.

**Why tombstones instead of real deletes**: The `MemoryBackend` abstract class doesn't define a `delete` method. Adding one would require changes to 3 backend files (postgres, qdrant, obsidian) + their tests. That's Plan 45+ work. For now, tombstones are correct (scoped_read checks the last entry's tombstone status) and don't expand this plan's scope.

**Critical ordering note** (flagged in review, second round): The original draft of this plan used `limit=1` in `scoped_read`'s exact-key path (first-round bug). The first-round fix changed to "filter tombstones, then take last non-tombstone" — also a bug, because for `[entry1, tombstone]` this returns entry1 instead of None. The second-round fix (current Step 1 implementation) checks the chronologically last entry's tombstone status directly: `last = results[-1]; return None if last is a tombstone else last`. Gate 5 verifies this with a write → delete → re-write sequence, and Gate 5a (added below) verifies the write → delete (no re-write) case that isolates the bug.

### Step 2 — Fix `system/trajectory_exporter.py`

**File**: `system/trajectory_exporter.py`
**Lines**: 64, 69

Read the file first. Then attempt Option 1 from Section B above. If `fetch_by_filter` doesn't work for this use case (backends don't store Tasks/WorkerOutputs as filterable dicts), fall back to Option 2:

```python
# Option 2 fallback — return empty + WARNING trace, document as Plan 45 work
try:
    event = TraceEvent(
        event_type=TraceEventType.OPERATION_ERROR,
        component=TraceComponent.ORCHESTRATOR,
        level=TraceLevel.WARNING,
        message="Trajectory export not yet functional — fetch_by_filter does not support querying Task/WorkerOutput class objects. Deferred to Plan 45.",
        data={"export_path": self._export_path},
        duration_ms=0,
    )
    await self._emitter.emit(event)
except Exception:
    pass
return  # Skip export, write empty file
```

**STOP condition for Step 2**: If neither Option 1 nor Option 2 is feasible without changes to backend files, STOP. Document in CHANGELOG and defer to Plan 45.

### Step 3 — Fix `core/escalation.py:146`

**File**: `core/escalation.py` (in-scope, drift-checked)
**Line**: 146

Change:
```python
approval_response = await self._approval_gate.request(approval_request)
```
To:
```python
approval_response = await self._approval_gate.request_approval(approval_request)
```

**Do NOT touch `core/instruction_versioning.py:148`** — an earlier draft of this plan said to "also check" it for a similar phantom call, but `instruction_versioning.py` is NOT in the 7-file in-scope list and NOT in the drift-check command. Telling Devin to fix it would repeat the exact scope contradiction this plan's D4 closes out (Plan 37 listed `escalation.py:146` as a co-located fix in a section whose STOP condition forbade touching out-of-scope files — same pattern, self-inflicted three sentences later). If `instruction_versioning.py:148` does have a similar bug, it goes in Plan 37.6 or a separate triage plan, not this one.

### Step 4 — Add TYPE_CHECKING import for StrategicContext (rolled in from prompt-37.1)

**File**: `core/memory_router.py`
**Lines**: 23-25 (the first TYPE_CHECKING block)

Change:
```python
if TYPE_CHECKING:
    from core.memory_compactor import MemoryCompactor
```
To:
```python
if TYPE_CHECKING:
    from core.memory_compactor import MemoryCompactor
    from core.schemas import StrategicContext
```

**Verify after this step**: `mypy core/memory_router.py --ignore-missing-imports` — no `Name 'StrategicContext' is not defined` error on line 516 (the `get_global_context` return annotation).

### Step 5 — Update 3 caller files to verify scoped_read/scoped_write work

**Files**: `core/approval_trust.py`, `skills/notes/notes_skill.py`, `skills/reminder/reminder_skill.py`

No code changes needed in these files — the calling conventions they already use will work with the new methods (the methods support both keyword and positional form). But run their test files to verify:

```bash
python -m pytest tests/test_approval_trust.py tests/skills/test_notes_skill.py tests/skills/test_reminder_skill.py -v --tb=short
```

**Expected**: all green. The test files already mock `scoped_read`/`scoped_write` (verified at `tests/test_approval_trust.py:19,23` and similar in the skill test files), so the mocks will start matching the real methods.

If any test fails, the mock's return shape probably doesn't match what the production code now expects. Update the mock, not the production code.

### Step 6 — Apply Claude's blocking fix D1 (retention.py documentation)

**File**: `SOVEREIGN_AI_HANDOFF.md`

Find the F6 entry (currently "PARTIALLY FIXED"). Add a sub-note:

```
**Note on `core/retention.py`**: Listed in the original F6 location list and Plan 37 entry, but verified against the live repo — retention.py uses the correct `fetch(task)` and `write(dict)` signatures. No `collection=`/`document_id=`/`limit=` kwargs. The handoff's inclusion was inaccurate; retention.py was never affected by F6. No changes needed. (Claude review finding #1, applied in Plan 37.5.)
```

### Step 7 — Apply Claude's blocking fix D2 (file count reconciliation)

**File**: `SOVEREIGN_AI_HANDOFF.md`

Update the Plan 37 entry in "Completed prompts" table to reflect actual counts:
- Files: 13 production files + `core/memory_router.py` + 8 test files = 22 total
- Call sites fixed: 33 (per CHANGELOG)
- Test files updated: 8 in prompt-37, plus 3 more in prompt-37.1 (model_registry, resource_manager, system_profiler) = 11 total

### Step 8 — Update CHANGELOG: append correction to prompt-37.1 entry

**File**: `CHANGELOG.md`

Append to the prompt-37.1 entry (do NOT edit history):

```
### Checkpoint Commit Correction (added in Plan 37.5)
- Prompt-37.1 CHANGELOG originally listed checkpoint commit as 9272bd7af3af6a46c5a3c761e1990423ad670062 (prompt-37's commit) — incorrect.
- Actual prompt-37.1 commit: 41cb13b88adaa293da830d4eca6f2b1a796c92f6
- Verified via `git rev-parse prompt-37.1` → 41cb13b88adaa293da830d4eca6f2b1a796c92f6
- global_rules.md Rule 16 violation (CHANGELOG must match commit). Corrected here; original entry preserved per append-only policy.
```

### Step 9 — Optional: Add Rule 18 equivalent to global_rules.md

**File**: `C:\Users\King\.codeium\windsurf\memories\global_rules.md` (Windows, Devin-local)

Per the original Plan 37.1 Step 7, this was skipped because the file is Devin-local and not in the repo. If Devin has time, add a rule mirroring the handoff's Rule 18. If not, defer — this is non-blocking. The handoff's Rule 18 is the source of truth.

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-37.1..HEAD -- core/memory_router.py core/approval_trust.py core/escalation.py core/retention.py system/trajectory_exporter.py skills/notes/notes_skill.py skills/reminder/reminder_skill.py tests/test_approval_trust.py tests/skills/test_notes_skill.py tests/skills/test_reminder_skill.py tests/test_escalation.py tests/test_trajectory_exporter.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
```

**Expected**: empty output (no drift since prompt-37.1). Note: this drift-check command lists all 5 in-scope test files (matching the Status line's "5 test files"), including `tests/test_escalation.py` and `tests/test_trajectory_exporter.py` that Step 3 and Step 2 touch indirectly via their corresponding production files.

### Gate 2 — `scoped_read` / `scoped_write` exist on MemoryRouter

```
python -c "from core.memory_router import MemoryRouter; mr = MemoryRouter(backends={}); print(hasattr(mr, 'scoped_read'), hasattr(mr, 'scoped_write'))"
```

**Expected**: `True True`.

### Gate 2a — Keyword calling convention works (CRITICAL — would have shipped broken in original draft)

```
python -c "import asyncio; from core.memory_router import MemoryRouter; from tests.test_memory_router import MockMemoryBackend; mr = MemoryRouter(backends={'mock': MockMemoryBackend()}); asyncio.run(mr.scoped_write(scope='test_scope', key='test_key', data={'v': 1})); r = asyncio.run(mr.scoped_read(scope='test_scope', key='test_key')); print('Keyword form:', r)"
```

**Expected**: `Keyword form: {'v': 1, '_scope': 'test_scope', '_key': 'test_key'}` (or similar augmented dict).

**Why this gate exists**: The original draft of this plan used PEP 570 `/` positional-only markers, which would have made `scoped_read(scope=..., key=...)` raise `TypeError`. Gates 2-5 in the original draft all called positionally, so the bug would have shipped clean. This gate exercises the keyword form that `core/approval_trust.py` relies on.

### Gate 3 — scoped_read/scoped_write round-trip works

```
python -c "import asyncio; from core.memory_router import MemoryRouter; from tests.test_memory_router import MockMemoryBackend; mr = MemoryRouter(backends={'mock': MockMemoryBackend()}); asyncio.run(mr.scoped_write('test_scope', 'test_key', {'data': 'value'})); r = asyncio.run(mr.scoped_read('test_scope', 'test_key')); print('Round-trip:', r)"
```

**Expected**: `Round-trip: {'data': 'value', '_scope': 'test_scope', '_key': 'test_key'}` (or similar — the augmented data is fine).

### Gate 4 — scoped_read wildcard works

```
python -c "import asyncio; from core.memory_router import MemoryRouter; from tests.test_memory_router import MockMemoryBackend; mr = MemoryRouter(backends={'mock': MockMemoryBackend()}); asyncio.run(mr.scoped_write('notes', 'notes:1', {'text': 'a'})); asyncio.run(mr.scoped_write('notes', 'notes:2', {'text': 'b'})); r = asyncio.run(mr.scoped_read('notes', 'notes:*')); print('Wildcard:', r)"
```

**Expected**: a list of 2 dicts.

### Gate 4a — scoped_read wildcard deduplicates by key after edit (CRITICAL — would have shipped broken in first-round fix)

```
python -c "import asyncio; from core.memory_router import MemoryRouter; from tests.test_memory_router import MockMemoryBackend; mr = MemoryRouter(backends={'mock': MockMemoryBackend()}); asyncio.run(mr.scoped_write('notes', 'notes:1', {'text': 'original'})); asyncio.run(mr.scoped_write('notes', 'notes:1', {'text': 'edited'})); asyncio.run(mr.scoped_write('notes', 'notes:2', {'text': 'b'})); r = asyncio.run(mr.scoped_read('notes', 'notes:*')); print('After edit, wildcard:', r)"
```

**Expected**: a list of 2 dicts — `notes:1` with `{'text': 'edited'}` (the latest write, not the original) and `notes:2` with `{'text': 'b'}`. NOT 3 dicts.

**Why this gate exists**: The original Gate 4 wrote two distinct keys (`notes:1`, `notes:2`) and didn't catch the case where the same key is written twice (an edit). Without dedup, the wildcard listing returns both the stale and current copies — 3 dicts instead of 2. The Step 1 implementation groups by `_key` and keeps only the chronologically last entry for each key, which is what makes this gate pass.

### Gate 5 — scoped_write with data=None deletes (and write → delete → re-write returns the re-write, not the original)

```
python -c "import asyncio; from core.memory_router import MemoryRouter; from tests.test_memory_router import MockMemoryBackend; mr = MemoryRouter(backends={'mock': MockMemoryBackend()}); asyncio.run(mr.scoped_write('trust', 'cmd1', {'level': 'PERM'})); asyncio.run(mr.scoped_write('trust', 'cmd1', None)); r1 = asyncio.run(mr.scoped_read('trust', 'cmd1')); print('After delete:', r1); asyncio.run(mr.scoped_write('trust', 'cmd1', {'level': 'SESSION'})); r2 = asyncio.run(mr.scoped_read('trust', 'cmd1')); print('After re-write:', r2)"
```

**Expected**:
```
After delete: None
After re-write: {'level': 'SESSION', '_scope': 'trust', '_key': 'cmd1'}
```

**Why the re-write check matters**: The original draft used `limit=1` in `scoped_read`, which would have returned the FIRST match in storage order (the original `{'level': 'PERM'}` write) instead of None after delete, and the original instead of the re-write after re-write. This gate catches that ordering bug. If `After delete` is not None, or `After re-write` shows `'PERM'` instead of `'SESSION'`, STOP — the tombstone+ordering logic is wrong.

### Gate 5a — scoped_write with data=None deletes (write → delete, NO re-write) — isolates the second-round ordering bug

```
python -c "import asyncio; from core.memory_router import MemoryRouter; from tests.test_memory_router import MockMemoryBackend; mr = MemoryRouter(backends={'mock': MockMemoryBackend()}); asyncio.run(mr.scoped_write('trust', 'cmd1', {'level': 'PERM'})); asyncio.run(mr.scoped_write('trust', 'cmd1', None)); r = asyncio.run(mr.scoped_read('trust', 'cmd1')); print('After delete (no re-write):', r)"
```

**Expected**: `After delete (no re-write): None`

**Why this gate exists (CRITICAL)**: Gate 5's `After delete` check and Gate 5a check the same thing, but Gate 5 immediately follows up with a re-write that masks the bug if the implementation is wrong. The first-round fix (filter tombstones first, then take last non-tombstone) would have failed Gate 5a — for storage `[entry1, tombstone]`, filtering leaves `[entry1]`, and taking last returns entry1 (the stale PERM value) instead of None. The current Step 1 implementation checks `last = results[-1]` and returns None if `last` is a tombstone — this passes Gate 5a. If Gate 5a fails, STOP — the tombstone ordering is still wrong, one layer deeper than the first-round fix addressed.

### Gate 6 — Caller test files green

```
python -m pytest tests/test_approval_trust.py tests/skills/test_notes_skill.py tests/skills/test_reminder_skill.py -v --tb=short
```

**Expected**: 0 failures.

### Gate 7 — escalation.py fix

```
python -m pytest tests/test_escalation.py -v --tb=short
```

**Expected**: 0 failures. (If `tests/test_escalation.py` doesn't exist, run `python -c "from core.escalation import EscalationEngine; print('imports OK')"` instead.)

### Gate 8 — trajectory_exporter.py fix

```
python -m pytest tests/test_trajectory_exporter.py -v --tb=short
```

**Expected**: 0 failures. (If `tests/test_trajectory_exporter.py` doesn't exist, run `python -c "from system.trajectory_exporter import TrajectoryExporter; print('imports OK')"` instead.)

### Gate 9 — TYPE_CHECKING import works

```
mypy core/memory_router.py --ignore-missing-imports
```

**Expected**: no `Name 'StrategicContext' is not defined` error on line 516. (If mypy isn't installed, install it first: `pip install mypy`. Do not skip this gate — prompt-37.1 skipped it and the missing import went undetected.)

### Gate 10 — Full test suite

```
python -m pytest tests/ -q --tb=short
```

**Expected**:
- Baseline (post prompt-37.1): 1078 passed, 23 skipped, 1 failed (flaky), 65 warnings
- After prompt-37.5: **1078 passed** (no new tests added — the new methods are exercised by existing caller tests, which already mock scoped_read/scoped_write), 23 skipped, 1 failed (flaky), ~65 warnings
- Acceptable range: {1077, 1078, 1079}. 1079 if any previously-skipped test now runs; 1077 if any test gets skipped due to optional deps.
- Anything outside {1077, 1078, 1079} is a regression. STOP.

### Gate 11 — F6 fully closed in handoff

```
grep "PARTIALLY FIXED" SOVEREIGN_AI_HANDOFF.md
```

**Expected**: 0 matches (F6 should be moved from "PARTIALLY FIXED" to "Recently fixed (prompt-37.5)").

### Gate 12 — Rule 18 not violated (no red test suite)

Implicit in Gate 10. If Gate 10 passes, Rule 18 is honored.

## STOP conditions

- **If Step 2 (trajectory_exporter) requires changes to backend files** (postgres.py, qdrant.py, obsidian.py), STOP. Defer to Plan 45.
- **If any caller test file fails after Step 5** and the failure is NOT a mock return-value issue, STOP. Real production bug found.
- **If Gate 9 (mypy) shows the TYPE_CHECKING import doesn't resolve**, STOP. The string annotation alone isn't enough; the import is required.
- **If Gate 10 shows fewer than 1077 passed tests**, STOP. Regression introduced.
- **If any file outside the in-scope list needs editing**, STOP. Report which file and why.
- **If total production code changes exceed 200 lines** (excluding tests), STOP. Split into 37.5a/37.5b.

## Out of scope

- **TUI memory + cognition stack wiring** — Plan 37.6 (the path users actually use; mirror of 35.6f for `cli/tui.py`)
- **Broad-except audit** — Plan 38+
- **InputSanitiser wiring** — Plan 41+
- **Proper `delete()` method on MemoryBackend interface** — Plan 45+ (currently using tombstones; works but isn't clean)
- **trajectory_exporter functional redesign** — Plan 45+ (depends on eval harness; current fix is a stub)
- **Notes/reminder skills' actual functionality** — this plan fixes their memory access, not their business logic

## Closing steps

1. `git add` the 7 in-scope production files + 5 test files (if any test changes) + `SOVEREIGN_AI_HANDOFF.md` + `CHANGELOG.md`
2. `git commit -m "fix: prompt-37.5 — finish F6 (scoped_read/write, trajectory_exporter, escalation.py, Claude's blocking fixes)"`
3. `git tag prompt-37.5`
4. `git show prompt-37.5 --stat` — verify file list. If unexpected file appears, `git tag -d prompt-37.5`, clean, re-tag.
5. **Post-tag verification (global_rules.md Rule 20)**: `git rev-parse prompt-37.5` — confirm hash matches the commit
6. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: per-file detail
   - **Implementation Notes**: which Step 2 option was taken (real fix or stub), any unexpected behaviour, the retention.py documentation note, the file count reconciliation
   - **Testing Results**: baseline (1078 passed from prompt-37.1) → final (expected 1078)
   - **Verification Gate Output**: literal output of each gate
7. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" line
   - Move F6 from "PARTIALLY FIXED" to "Recently fixed (prompt-37.5)"
   - Update "Built but not reachable" table: ApprovalTrustRegistry, notes skill, reminder skill now functionally correct (still not wired end-to-end via TUI)
   - Add the retention.py documentation note (Step 6)
   - Update the file count in the Plan 37 completed-prompts entry (Step 7)
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-37.5 changelog and handoff update"`
10. `git push origin master && git push origin prompt-37.5`
11. **Post-push verification (global_rules.md Rule 20)**: `git ls-remote --tags origin | grep prompt-37.5` — verify the tag exists on the remote. **Do not skip this step.** (Prompt-37.1 verification initially failed because the reviewer's fetch was stale; this gate confirms the tag is actually on origin.)
12. **Reconcile test count**: Paste the literal `python -m pytest tests/ -q --tb=short` output into the CHANGELOG. If the count differs from 1078, explain why.

## After Plan 37.5 lands

F6 is fully closed. The queue can now proceed to:

- **Plan 37.6** — TUI memory + cognition stack wiring (mirror of 35.6f for `cli/tui.py`). This is the path users actually use; without it, all the F6 fixes only help `jarvis serve`, not `jarvis`.
- **Plan 38** — F7 trace spam + `cli/__init__.py` (was Plan 38 before resequencing)
- **Plan 38.5** — Broad-except audit, part 1 (core/)
- **Plan 39** — Broad-except audit, part 2 (system/)
- **Plan 40** — Broad-except audit, part 3 (skills/)
- **Plan 41** — InputSanitiser wiring
- **Plan 42** — InputSanitiser redesign
- **Plan 43** — ruff triage
- **Plan 44** — mypy triage
- **Plan 45+** — graphify integration cluster, proper MemoryBackend.delete(), trajectory_exporter functional redesign

Plans 37.6 must land before Plan 38. The TUI is the path users actually use; without it, F6 fixes only help `jarvis serve`.
