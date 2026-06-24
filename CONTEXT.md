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

## Sandbox Vocabulary (NEW — Plan 73)

| Term | Definition |
|---|---|
| **SandboxExecutor** | The single entry point for all code and command execution. Runs code in a Docker container with resource limits (memory, CPU, network, timeout). Falls back to subprocess if Docker unavailable AND approval gate explicitly allows it. |
| **Sandbox Image** | The Docker image used for execution. Default: `python:3.12-slim`. Configurable per-task via `image` parameter. |
| **Sandbox Policy** | Configuration determining whether Docker is required (strict) or optional (fallback to subprocess with approval). Default: strict. |
| **Sandbox Result** | Result dict from SandboxExecutor: `{success, stdout, stderr, return_code, error, sandboxed, container_id}`. `sandboxed: True` if Docker was used, `False` if subprocess fallback. |

## Cost Tracking Vocabulary (NEW — Plan 74)

| Term | Definition |
|---|---|
| **CostTracker** | The central module that aggregates token usage × cost_per_token per model, enforces daily/monthly $ caps, and emits cost traces. Single source of truth for spend. |
| **Spend Cap** | Configurable $ limit (daily or monthly). When hit, CostTracker blocks further execution and triggers fallback to cheaper model (if configured) or hard-fail. |
| **Cost Trace** | Trace event emitted by CostTracker with `model`, `tokens_in`, `tokens_out`, `cost_usd`, `cumulative_daily`, `cumulative_monthly` fields. |
| **Cost Policy** | Configuration determining cap amounts, fallback behavior, and alert thresholds. Default: $10/day, $100/month, alert at 80%, fallback to cheapest model at 90%. |
