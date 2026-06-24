# CONTEXT.md — Sovereign AI Shared Vocabulary

This file defines the domain terms, conventions, and shared vocabulary used across all agents and skills in the Sovereign AI framework. Every agent and skill SHOULD reference this file for consistent terminology.

## Core Concepts

| Term | Definition |
|---|---|
| **Task** | A unit of work submitted to the orchestrator. Has a UUID, intent, priority, and state machine lifecycle. |
| **Worker** | An entity that processes tasks. Registered with the orchestrator. Has a profile (worker_id, model, capabilities). |
| **Skill** | A modular capability that can be dynamically discovered and loaded. Classified by invocation tier (see Skill Taxonomy). |
| **Adapter** | An LLM provider integration (OpenAI, Anthropic, Ollama, etc.). Translates worker requests into provider-specific API calls. |
| **Orchestrator** | The central coordinator. Routes tasks to workers, manages the task lifecycle, and emits trace events. |
| **Memory Router** | The single entry point for all memory operations. Routes read/write to appropriate backends (SQLite, Qdrant, Obsidian). |
| **Trace Emitter** | Structured observability event emitter. Injected via constructor. Fire-and-forget persistence to trace store. |
| **Eval Harness** | Metrics engine (exact_match, token_f1, bleu, cosine_similarity) for evaluating worker outputs. |
| **Improvement Loop** | Closed loop: execute → evaluate → store → improve. Currently wired but not reachable from CLI. |

## Skill Tiers

| Tier | Meaning | Example |
|---|---|---|
| **USER_INVOKED** (user_invoked) | Only activated by explicit user request | calculator, terminal, docker |
| **AGENT_INVOKED** (agent_invoked) | Orchestrator decides to use based on task analysis | calendar, notes, reminder |
| **HYBRID** (hybrid) | Both user and agent can invoke | email |

> Examples reflect current classifications as of Plan 68. See `skills/classifications.py` for the authoritative list.

## Domain Context

### User Profile
- **Primary domains**: Media production, sailing, 3D printing, CNC machining
- **Environment**: Single-user, local-first, Windows workstation
- **Cloud escalation**: Only when local resources are insufficient

> **Note**: This section is deployment-specific. If forking Sovereign AI for a different context, replace these entries with your own domain profile.

### Decision Framework
- **Local first**: Run on local hardware by default
- **Escalate when needed**: Use cloud APIs (OpenAI, Anthropic) when local models can't handle the task
- **Interrupt only when necessary**: Background monitors (weather, AIS, email) should not interrupt unless action is required
- **Approval gates**: Destructive or expensive operations require explicit user approval

### Conventions
- All datetimes are timezone-aware UTC: `datetime.now(timezone.utc)`, never `datetime.utcnow()`
- All public functions have return type annotations (AR14)
- No raw LLM calls outside adapters/ (AR9)
- No memory access outside MemoryRouter (AR10)
- TraceEmitter via constructor injection only (AR11)
