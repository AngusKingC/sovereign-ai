# Plan 64 Context Brief — Core Mypy Remediation

## Purpose
Review guide for Claude. Plan-64 fixes 33 mypy type errors in `core/` files to resolve the 4-plan tolerance breach (mypy 283→294, +11 outside tolerance since Plan 60).

## Current State
- **Tag**: prompt-63b on origin, verified
- **Tests**: 1232 passed, 67 skipped
- **Mypy baseline**: 294 errors in 77 files (Plan 60 full scan)
- **Mypy tolerance**: ±10 from 283 baseline → 294 is +11, OUTSIDE tolerance
- **Ruff**: 0 errors (held since Plan 59)
- **Bandit**: 3,179 low / 0 medium / 0 high
- **pip-audit**: 19 CVEs (stable)
- **Vulture**: 23 findings

## Error Breakdown (core/ only, 33 errors)

### Tier 1 — Safe fixes (15 errors)
| # | File | Line ~ | Fix |
|---|---|---|---|
| 1 | auth.py | 114 | None guard before compare_digest |
| 2 | a2a_protocol.py | 89 | Assert parent_task_id non-None |
| 3 | rating_system.py | 325 | Replace .get with lambda in max() |
| 4 | evaluator.py | 81 | Dict → Message object |
| 5 | instruction_generator.py | 64 | Dict → Message object |
| 6 | instruction_generator.py | 177 | Dict → Message object |
| 7 | instruction_generator.py | 187 | Dict → Message object |
| 8 | orchestrator.py | 877 | dict[str, Any] annotation |
| 9 | orchestrator.py | 878 | dict[str, Any] annotation |
| 10 | orchestrator.py | 879 | dict[str, Any] annotation |
| 11 | orchestrator.py | 880 | dict[str, Any] annotation |
| 12 | orchestrator.py | 881 | dict[str, Any] annotation |
| 13 | multi_worker.py | 272 | Type narrowing (assert isinstance) |
| 14 | handlers.py | 153 | dict[str, Any] annotation |
| 15 | handlers.py | 154 | dict[str, Any] annotation |

### Tier 2 — Interface alignment (18 errors)
| # | File | Line ~ | Fix |
|---|---|---|---|
| 1 | notification.py | 54 | TYPE_CHECKING import for TelegramGateway |
| 2 | worker_factory.py | 31 | Fix LLMResponse import source (schemas → worker_base) |
| 3 | instruction_versioning.py | 147 | Rename submit_for_approval → request_approval |
| 4-7 | handlers.py | 498,501,533,536 | command.context None guards |
| 8 | multi_worker.py | 122 | ResourceBudget.check_all_budgets missing |
| 9 | multi_worker.py | 149 | Orchestrator.adapter doesn't exist |
| 10-11 | multi_worker.py | 227,317 | WorkerBase.execute doesn't exist |
| 12-13 | multi_worker.py | 302,348 | WorkerBase.adapter → worker.llm |
| 14-15 | multi_worker.py | 379,384 | record_rating signature mismatch |
| 16 | event_trigger.py | 214 | process_task missing worker_id |
| 17-18 | (system/) | — | Out of scope for this plan |

## Key Design Decisions Deferred to S1

S1 is a read-only investigation with STOP gate before any edits. Decision trees for ambiguous findings:

**WorkerBase.execute vs. run()**:
- execute() exists but unused → use run()
- execute() doesn't exist AND run() is full pipeline → replace with run()
- execute() doesn't exist AND run() is partial → STOP (needs design meeting)

**orchestrator.adapter**:
- fallback_chain provides access → use it
- No single adapter → pass explicitly from worker context
- Adding adapter property would be clean → report for approval

**record_rating signature**:
- Args map 1:1 → apply fix
- Required args unavailable at call site → STOP (no placeholder values)

## Verification
- File-scoped mypy must be 0 on all touched files
- Full-repo mypy (S6.4): soft gate — if ≥283, investigate; if <283, tolerance breach resolved
- Tests must hold at 1232 passed, 67 skipped (±5)

## Files to Review
- Plan: `/home/z/my-project/download/plan-64.md`
- Repo: `git clone https://github.com/AngusKingC/sovereign-ai.git` (tag prompt-63b)
