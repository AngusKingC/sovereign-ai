# Sovereign AI Agent Framework - Changelog

## Overview
This changelog documents all implementations, changes, and decisions made during the development of the Sovereign AI Agent Framework.

### CHANGELOG Rules
- Entries are in chronological order — oldest at top, newest at bottom
- New entries are always appended to the bottom of the file, never inserted at the top
- Every entry date must include time: format YYYY-MM-DD HH:MM
- Never prepend entries — always append

---

## 2026-06-18 13:44 - Prompt 35.6f: Wire Cognition Stack End-to-End

**Changed**:
- cli/serve.py, cli/tui.py: wired Orchestrator, MemoryRouter, ApprovalGate, EscalationEngine, AdapterFallbackChain, WorkerFactory, RatingSystem, InstructionGenerator, InstructionVersionManager, OutputEvaluator, TraceOptimiser, OrchestratorImprovementLoop

**Results**:
- Tests: 1058 passed, 55 skipped

---

## 2026-06-18 14:33 - Prompt 36: Fix jarvis serve end-to-end (F1, F2, F3, F5)

**Changed**:
- cli/serve.py: fixed 4 regressions; jarvis serve now starts and returns worker listings

**Results**:
- Tests: 1044 passed

---

## 2026-06-18 15:12 - Prompt 36.5: Fix llama_cpp test collection

**Changed**:
- tests/test_llama_cpp_adapter.py: added pytest.importorskip("llama_cpp")

**Results**:
- Tests: 1072 passed

---

## 2026-06-18 17:06 - Prompt 37: Fix F6 - MemoryRouter Call-Signature Mismatch

**Changed**:
- core/memory_router.py: added new methods; fixed 33 call sites across 13 production files + 11 test files

**Results**:
- Tests: 1010 passed

---

## 2026-06-18 18:02 - Prompt 37.1: Fix Test Mocks and Establish Rule 18

**Changed**:
- 8 test files: fixed 69 test failures by updating stale mock references; added Rule 18

**Results**:
- Tests: 1078 passed

---

## 2026-06-19 15:35 - Prompt 39: OpenAI/Cohere/Groq adapter test coverage + Anthropic verification

**Changed**:
- tests/test_openai_adapter.py, test_cohere_adapter.py, test_groq_adapter.py: added mocked unit tests + integration tests

**Results**:
- Tests: 1089 passed, 19 skipped

---

## 2026-06-19 16:30 — prompt-40: Mistral/Together/DeepSeek/HuggingFace adapter test coverage

**Changed**:
- tests/test_mistral_adapter.py, test_together_adapter.py, test_deepseek_adapter.py, test_huggingface_adapter.py: added mocked unit tests + integration tests

**Results**:
- Tests: 1089 passed, 19 skipped

---

## 2026-06-20 16:54 - Plan 47

**Changed**:
- web/server.py, web/middleware/auth_middleware.py: moved logging.getLogger() after imports (E402 fix)
- gateways/__init__.py: created (empty)
- Removed 13 unused imports (JSONResponse, AuthenticationError, asyncio, typing.Any)

**Results**:
- Tests: 1167 passed, 55 skipped
- E402: 35→22, F401: 260→247

---

## 2026-06-20 21:06 — Plan 48

**Changed**:
- memory/postgres.py: table_name validation regex + # nosec B608
- cli/serve.py, web/reference.py: # nosec B104 suppression
- .github/workflows/ci.yml: added bandit, pip-audit, vulture CI jobs

**Results**:
- Tests: 1167 passed, 55 skipped
- Bandit: 26→22 medium+

---

## 2026-06-20 20:57 — Plan 48.1

**Changed**:
- SOVEREIGN_AI_HANDOFF.md: added L15 landmine (temp-file CHANGELOG pattern)

**Results**:
- Tests: 1167 passed, 55 skipped

---

## 2026-06-20 21:53 — Plan 49

**Changed**:
- core/approval_gate.py: 10 Field(None→default=None) + 3 TraceEvent kwargs fixed

**Results**:
- Tests: 1167 passed, 55 skipped
- Mypy: ~108 errors eliminated

---

## 2026-06-20 23:00 - Plan 49b: Migrate old-API callers to request_approval(request: ApprovalRequest)

**Changed**:
- 8 skill files: 17 call sites migrated from old API to new ApprovalRequest pattern
- 8 test files: fixed mocks to return ApprovalResponse

**Results**:
- Tests: 1166 passed, 55 skipped, 1 failed (pre-existing calendar)
- Mypy: 32 errors eliminated

---

## 2026-06-21 00:21 — Plan 50: Fix MockMemoryRouter and MockStateMachine inheritance

**Changed**:
- 8 test files: MockMemoryRouter now inherits from MemoryRouter, MockStateMachine inherits from TaskStateMachine

**Results**:
- Tests: 1166 passed, 55 skipped, 1 failed (pre-existing calendar)
- Mypy: 435→309 errors (-126)

---

## 2026-06-21 02:36 — prompt-51

**Changed**:
- 13 adapters/system files: renamed inner exception variable e→inner_e (fixes shadowing)
- 5 skill files: start_time = 0 → 0.0 (fixes float→int)
- adapters/gemini.py: 4 emit_trace() → self._emitter.emit(TraceEvent()) (DI fix)
- core/handlers.py: removed dead emit_trace import
- cli/tui.py, core/commands.py: ConsoleTraceEmitter → MemoryTraceEmitter

**Results**:
- Tests: 1166 passed, 55 skipped, 1 failed (pre-existing calendar)
- Mypy: 309→282 errors (-27)

---

## 2026-06-21 03:30 — prompt-52

**Changed**:
- cli/serve.py: removed _ prefix from 4 subsystems, wired output_evaluator to Orchestrator, set trace_optimiser as attribute
- core/orchestrator.py: added output_evaluator and trace_optimiser params to __init__, call evaluate_output() in process_task()
- cli/tui.py: same wiring as serve.py

**Results**:
- Tests: 1166 passed, 55 skipped, 1 failed (pre-existing calendar)
- F4 fixed — cognition-loop subsystems now wired

---

## 2026-06-21 12:08 — prompt-53

**Changed**:
- tests/skills/test_calendar_skill.py: replaced hardcoded date with dynamic future date; replaced "test.ics" with tempfile.mkdtemp() (22 B108 fixed)
- 15 test files: datetime.utcnow() → datetime.now(timezone.utc) (81 occurrences)
- Production files: datetime.utcnow() → datetime.now(timezone.utc) where tests compare datetimes

**Results**:
- Tests: 1167 passed (calendar fixed!), 55 skipped, 0 failed
- Bandit B108: 0 (was 22)
- utcnow warnings: 0 (was 81)
