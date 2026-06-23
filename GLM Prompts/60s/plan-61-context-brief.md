# Plan 61 Context Brief — Trace Store Implementation

**For**: Claude review (GLM Step 6)  
**Length**: ~40 lines  
**Purpose**: Verify Plan 61 scope, baselines, and architecture before Devin executes

---

## Quick Context

**Plan 61** implements persistent trace storage backend using Postgres. This is the first piece of the measurement layer (Plans 61-64 roadmap).

**PLANS.md queue**:
- Plan 61: Trace Store Implementation (ACTIVE)
- Plan 62: Eval Harness
- Plan 62.5: Eval Validation
- Plan 63a: Improvement Loop Wiring
- Plan 63b: Improvement Loop Validation

---

## Scope Verification

### Files to Create (3)
- `memory/postgres_trace_store.py` — PostgresTraceStore class (~200 lines)
  - Constructor with connection pool
  - store_trace() async method
  - query_traces() async method with filters
  - get_trace_by_id() async method
- `tests/test_postgres_trace_store.py` — Unit tests (~150 lines, 8-12 tests)
- `tests/test_postgres_trace_store_integration.py` — E2E test (~50 lines, 1-2 tests)

### Files to Modify (3)
- `memory/__init__.py` — Export PostgresTraceStore (+2 lines)
- `memory/router.py` — Register trace_store backend (+8 lines)
- `core/observability.py` — Route traces through MemoryRouter (+15 lines)

**Total scope**: 6 files, ~425 new/modified lines. **Contained and bounded.**

---

## Baseline Expectations

| Metric | Current | Expected | Delta |
|---|---|---|---|
| Tests | 1166 passed | 1180 passed | +14 (new trace store tests) |
| Ruff | 0 | 0 | 0 (file-scoped cleanup) |
| Mypy | 277 | 282-287 | +5-10 (Postgres typing acceptable) |

**Tolerance**: ±5 tests per PLANS.md. Mypy +5-10 acceptable for async/Postgres typing.

---

## Architecture Rules Check

✅ **AR1-AR4**: Core/memory separation — MemoryRouter used for access (not direct imports)  
✅ **AR9**: No LLM calls in new code  
✅ **AR10**: Memory access via MemoryRouter (not direct)  
✅ **AR12**: All I/O async (store, query, pool)  
✅ **AR14**: Return type annotations present  
✅ **AR15**: Input sanitization N/A (no external input)  

---

## Risk Assessment

### Low Risk ✅
- New file (postgres_trace_store.py) — isolated, no existing code to break
- Tests are comprehensive (8-12 unit + integration)
- Memory/observability integration minimal (optional backend)

### Medium Risk ⚠️
- Postgres dependency (asyncpg) — must exist in requirements.txt
- Connection string config — ensure env var/config file pattern used
- Async pool management — verify pool exhaustion handling

### Mitigation
- Plan includes: connection pool initialization, async error handling, graceful degradation (optional backend)
- Tests include: pool limits, concurrent access, connection failures
- Scope review: all file edits explicit, no scope creep authorized

---

## Key Implementation Details

**Trace storage schema** (implied, verify in code):
```
CREATE TABLE traces (
  id UUID PRIMARY KEY,
  timestamp TIMESTAMP WITH TIME ZONE,
  event_type TEXT,
  source TEXT,
  metadata JSONB,
  status TEXT
)
```

**Datetime rule** (OR20): All timestamps use `datetime.now(timezone.utc)` — never `datetime.utcnow()` or bare `datetime.now()`.

**Graceful degradation**: Trace storage optional; system works without Postgres (emit_trace catches None gracefully).

---

## Devin Execution Checklist

- [ ] S0.1: jarvis-open passes (prompt-60 tag exists)
- [ ] S0.2: AGENTS.md rules read (no new rules this plan)
- [ ] S1.1: postgres_trace_store.py created, syntax clean
- [ ] S1.2: memory/__init__.py updated, syntax clean
- [ ] S1.3: core/observability.py updated, syntax clean
- [ ] S1.4: test_postgres_trace_store.py created, ~150 lines
- [ ] S2.1: memory/router.py updated, syntax clean
- [ ] S2.2: core/observability.py trace routing added
- [ ] S3.1: Targeted tests pass (~1180 expected)
- [ ] S3.2: Mypy within tolerance
- [ ] S3.3: Ruff 0 errors
- [ ] S4.1: Integration test E2E passes
- [ ] C1-C14: jarvis-close passes, PLANS.md updated, prompt-61 tagged

---

## Questions for Claude Review

1. **Scope creep risk**: Are there any hidden dependencies in memory/router.py or core/observability.py that would expand scope?
2. **Async correctness**: Is the async pool pattern correct (psycopg pool initialization, connection lifecycle)?
3. **Test coverage**: Are the 8-12 unit tests + integration test sufficient, or missing key scenarios?
4. **Datetime compliance**: Will all timestamp uses correctly use `datetime.now(timezone.utc)`?
5. **Optional backend pattern**: Is graceful degradation (None handling) sufficient for production?

---

## Reference Docs

- **PLANS.md**: Baseline expectations, Plan 61 entry
- **AGENTS.md**: AR1-AR4, AR9-AR10, AR12, AR14, OR20
- **AI_HANDOFF.md**: Devin template (S0, S1-Sn, closing)
- **jarvis-close.md**: Closing sequence (C1-C14)

---

## Sign-Off

**Plan 61** is:
- ✅ Scoped (6 files, ~425 lines)
- ✅ Bounded (no scope expansion authorized)
- ✅ Baselined (1180 tests, +5-10 mypy acceptable)
- ✅ Architectural (AR1-AR4, AR10 compliant)
- ✅ Testable (comprehensive unit + E2E)

**Ready for Devin execution** once Claude approves.

---

**Created**: 2026-06-23  
**Plan source**: Plan 61 — Trace Store Implementation  
**Review gate**: Claude sign-off on Questions section (5 items)
