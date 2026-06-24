# Plan 68 — Phase 1 Foundation: Skill Taxonomy + CONTEXT.md

**Plan**: 68
**Rev**: 3 (incorporates two rounds of Claude review feedback)
**Type**: Feature implementation + test fix
**Priority**: 1
**Estimated scope**: ~6 files edited, ~4 files created, ~20 new tests

### Rev history
- **Rev 1**: Initial plan + context brief. Claude review: skill count wrong, email tier unclear, naming convention, HYBRID undefined, test gaps.
- **Rev 2**: Applied Rev 1 feedback (25 skills, email→HYBRID, classifications.py, consistency tests, CONTEXT.md updates). Claude review: approved with pre-flight note and staleness note suggestions.
- **Rev 3**: Applied Rev 2 feedback (pre-flight skill count check, CONTEXT.md staleness note).

---

## S0 — Opening

S0.1. Run `/jarvis-open`. Verify `prompt-67` tag on origin, clean working copy on master.

S0.2. Read AGENTS.md in full. Every file edit in this plan MUST comply with its rules.

S0.3. **No new AGENTS.md rules this prompt.** All existing rules (OR1–OR28, AR1–AR18) apply.

### Pre-flight check

Before S1, verify the skill count in the repo:
```powershell
Get-ChildItem -Path skills -Filter "skill.py" -Recurse | Measure-Object
```
If the count ≠ 25, adjust S4.1 test #10 and the CHANGELOG entry accordingly. Current plan assumes 25 (15 user, 9 agent, 1 hybrid).

---

## S1 — Investigation: Pre-existing Test Failures

Before starting feature work, identify and fix the 2 pre-existing test failures that were present at Plan 67 close.

### S1.1 — Identify failing tests

Run:
```powershell
python -m pytest tests/ -v --tb=short 2>&1 | Select-String "FAILED"
```

Record the exact test names and failure reasons.

### S1.2 — STOP gate

If more than 3 tests fail, STOP and report. If the failures require changes outside the scope of this plan (e.g., architectural changes, new dependencies), STOP and report — do not fix unilaterally (OR16).

### S1.3 — Fix failing tests

Fix each failing test using the minimal change principle. Common patterns from previous plans:
- Mock type mismatches (add `# type: ignore[arg-type]` or fix mock signatures)
- Missing async markers on test fixtures
- Stale assertions after API changes

After each fix:
- Syntax check (OR6): `python -c "import ast; ast.parse(open('<file>').read())"`
- Run the individual test file: `python -m pytest tests/<file>.py -v --tb=short`
- Diff check (OR8): `git diff --stat <file>`

### S1.4 — Verify full test suite

Run:
```powershell
python -m pytest tests/ -q --tb=short
```

Expected: **1230+ passed, 67 skipped, 0 failed**. If any failures remain, STOP and report.

---

## S2 — Feature F1: Skill Taxonomy

Implement the skill classification system (user-invoked vs agent-invoked) based on the mattpocock/skills research. This is foundational — all subsequent features (trust tiers, skill routing, permission scoping) depend on it.

### S2.1 — Define the SkillTier enum and data model

**File**: `core/skill_taxonomy.py` (NEW)

Create:
```python
"""Skill taxonomy — classification of skills by invocation mode.

Single responsibility: Define the taxonomy that classifies skills
as user-invoked (explicit CLI/trigger) or agent-invoked (automatic).
"""
from enum import Enum
from dataclasses import dataclass


class SkillTier(Enum):
    """Classification of skill invocation mode."""
    USER_INVOKED = "user_invoked"    # Explicit user action: CLI command, button press, direct request
    AGENT_INVOKED = "agent_invoked"  # Automatic: orchestrator decides to use based on task analysis
    HYBRID = "hybrid"                # Both modes: user CAN invoke directly, agent CAN auto-invoke


@dataclass(frozen=True)
class SkillClassification:
    """Immutable classification record for a skill."""
    skill_name: str
    tier: SkillTier
    description: str          # One-line human-readable description
    auto_invoke_conditions: list[str]  # When agent should auto-invoke (empty for USER_INVOKED)
    requires_approval: bool   # Whether auto-invocation requires user approval
```

### S2.2 — Create the skill classification registry

**File**: `core/skill_taxonomy.py` (same file, continue)

Add to the same file:
```python
class SkillTaxonomyRegistry:
    """Registry of skill classifications. Immutable after initialization."""

    def __init__(self) -> None:
        self._classifications: dict[str, SkillClassification] = {}

    def register(self, classification: SkillClassification) -> None:
        """Register a skill classification. Raises if duplicate."""
        if classification.skill_name in self._classifications:
            raise ValueError(f"Skill '{classification.skill_name}' already classified")
        self._classifications[classification.skill_name] = classification

    def classify(self, skill_name: str) -> SkillClassification | None:
        """Look up a skill's classification. Returns None if not registered."""
        return self._classifications.get(skill_name)

    def skills_by_tier(self, tier: SkillTier) -> list[SkillClassification]:
        """Return all skills in a given tier."""
        return [c for c in self._classifications.values() if c.tier == tier]

    def agent_invocable_skills(self) -> list[SkillClassification]:
        """Return all skills the agent can auto-invoke (AGENT_INVOKED + HYBRID)."""
        return [
            c for c in self._classifications.values()
            if c.tier in (SkillTier.AGENT_INVOKED, SkillTier.HYBRID)
        ]

    def user_invocable_skills(self) -> list[SkillClassification]:
        """Return all skills the user can invoke directly (USER_INVOKED + HYBRID)."""
        return [
            c for c in self._classifications.values()
            if c.tier in (SkillTier.USER_INVOKED, SkillTier.HYBRID)
        ]

    @property
    def all_classifications(self) -> dict[str, SkillClassification]:
        """Read-only view of all classifications."""
        return dict(self._classifications)
```

### S2.3 — Classify existing skills

**File**: `skills/classifications.py` (NEW)

Create a module that registers all existing skills with their classifications. Note: No underscore prefix — `build_default_registry()` is a public API called from initialization code.

```python
"""Skill classifications — registers all built-in skills with the taxonomy.

Single responsibility: One place to declare every skill's tier,
auto-invoke conditions, and approval requirements.
"""
from core.skill_taxonomy import (
    SkillClassification,
    SkillTaxonomyRegistry,
    SkillTier,
)


def build_default_registry() -> SkillTaxonomyRegistry:
    """Build and return the default skill classification registry."""
    registry = SkillTaxonomyRegistry()

    # USER_INVOKED skills — only activated by explicit user request
    registry.register(SkillClassification(
        skill_name="calculator",
        tier=SkillTier.USER_INVOKED,
        description="Perform mathematical calculations",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="clipboard",
        tier=SkillTier.USER_INVOKED,
        description="Read from and write to the system clipboard",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="code_execution",
        tier=SkillTier.USER_INVOKED,
        description="Execute code snippets in a sandboxed environment",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="docker",
        tier=SkillTier.USER_INVOKED,
        description="Manage Docker containers and images",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="email",
        tier=SkillTier.HYBRID,
        description="Send and read email messages",
        auto_invoke_conditions=["task mentions checking email or inbox", "user asks about unread messages"],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="file_reader",
        tier=SkillTier.USER_INVOKED,
        description="Read file contents from disk",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="file_writer",
        tier=SkillTier.USER_INVOKED,
        description="Write content to files on disk",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="git",
        tier=SkillTier.USER_INVOKED,
        description="Perform Git operations on repositories",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="pdf",
        tier=SkillTier.USER_INVOKED,
        description="Read and process PDF documents",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="screenshot",
        tier=SkillTier.USER_INVOKED,
        description="Capture screenshots of the desktop or windows",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="spreadsheet",
        tier=SkillTier.USER_INVOKED,
        description="Read and write spreadsheet files",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="terminal",
        tier=SkillTier.USER_INVOKED,
        description="Execute terminal/shell commands",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="transcription",
        tier=SkillTier.USER_INVOKED,
        description="Transcribe audio files to text",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="tts",
        tier=SkillTier.USER_INVOKED,
        description="Convert text to speech audio",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="web_scraper",
        tier=SkillTier.USER_INVOKED,
        description="Scrape content from web pages",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="web_search",
        tier=SkillTier.USER_INVOKED,
        description="Search the web for information",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))

    # AGENT_INVOKED skills — the orchestrator decides to use automatically
    registry.register(SkillClassification(
        skill_name="marine_ais",
        tier=SkillTier.AGENT_INVOKED,
        description="Track vessel positions via AIS data",
        auto_invoke_conditions=["task mentions vessel tracking or AIS", "maritime safety check"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="marine_weather",
        tier=SkillTier.AGENT_INVOKED,
        description="Monitor marine weather conditions",
        auto_invoke_conditions=["task mentions weather or sea conditions", "passage planning"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="marine_tidal",
        tier=SkillTier.AGENT_INVOKED,
        description="Check tidal information and predictions",
        auto_invoke_conditions=["task mentions tides or tidal streams", "coastal navigation"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="marine_passage_planner",
        tier=SkillTier.AGENT_INVOKED,
        description="Plan maritime passages with route optimization",
        auto_invoke_conditions=["task mentions passage planning or routing", "long-distance voyage"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="calendar",
        tier=SkillTier.AGENT_INVOKED,
        description="Manage calendar events and schedules",
        auto_invoke_conditions=["task mentions scheduling or events", "user asks about availability"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="home_assistant",
        tier=SkillTier.AGENT_INVOKED,
        description="Control smart home devices via Home Assistant",
        auto_invoke_conditions=["task mentions smart home, lights, or devices", "environment control request"],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="http_client",
        tier=SkillTier.AGENT_INVOKED,
        description="Make HTTP requests to external APIs",
        auto_invoke_conditions=["task requires external API call", "data retrieval from URL"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="notes",
        tier=SkillTier.AGENT_INVOKED,
        description="Create and manage notes",
        auto_invoke_conditions=["task mentions taking notes or remembering", "user shares information to store"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="reminder",
        tier=SkillTier.AGENT_INVOKED,
        description="Set and manage reminders",
        auto_invoke_conditions=["task mentions reminding or alerting", "time-based action needed"],
        requires_approval=False,
    ))

    return registry
```

### S2.4 — Verify syntax and mypy

After creating both files:
```powershell
python -c "import ast; ast.parse(open('core/skill_taxonomy.py').read())"
python -c "import ast; ast.parse(open('skills/classifications.py').read())"
mypy core/skill_taxonomy.py --ignore-missing-imports
mypy skills/classifications.py --ignore-missing-imports
```

Expected: 0 errors on both files.

---

## S3 — Feature F2: CONTEXT.md

Create the project-level CONTEXT.md file that defines domain terms, conventions, and shared vocabulary for multi-agent coordination.

### S3.1 — Create CONTEXT.md

**File**: `CONTEXT.md` (NEW, repo root)

```markdown
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
| **USER_INVOKED** | Only activated by explicit user request | calculator, terminal, docker |
| **AGENT_INVOKED** | Orchestrator decides to use based on task analysis | calendar, notes, reminder |
| **HYBRID** | Both user and agent can invoke | email |

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
```

### S3.2 — Verify file exists

```powershell
Test-Path CONTEXT.md
Get-Content CONTEXT.md | Measure-Object -Line
```

Expected: File exists, ~60+ lines.

---

## S4 — Tests

### S4.1 — Test skill taxonomy

**File**: `tests/test_skill_taxonomy.py` (NEW)

Write tests covering:

1. **SkillTier enum**: Verify all three tiers exist and have correct values
2. **SkillClassification**: Create a classification, verify immutability (frozen dataclass)
3. **SkillTaxonomyRegistry.register**: Register a skill, retrieve it by name
4. **SkillTaxonomyRegistry.register duplicate**: Register same name twice → raises ValueError
5. **SkillTaxonomyRegistry.classify**: Look up existing skill → returns classification
6. **SkillTaxonomyRegistry.classify missing**: Look up nonexistent skill → returns None
7. **SkillTaxonomyRegistry.skills_by_tier**: Filter by USER_INVOKED, verify only user-invoked skills returned
8. **SkillTaxonomyRegistry.agent_invocable_skills**: Verify returns AGENT_INVOKED + HYBRID only
9. **SkillTaxonomyRegistry.user_invocable_skills**: Verify returns USER_INVOKED + HYBRID only
10. **build_default_registry**: Verify all expected skills are registered (count should be 25: 15 user, 9 agent, 1 hybrid)
11. **build_default_registry tier split**: Verify all three tiers (USER_INVOKED, AGENT_INVOKED, HYBRID) have entries
12. **Auto-invoke conditions**: Verify agent-invoked and hybrid skills have non-empty auto_invoke_conditions; user-invoked skills have empty
13. **Approval requirements**: Verify destructive skills (docker, terminal, email) have requires_approval=True
14. **CONTEXT.md consistency**: Verify the skill tier names in CONTEXT.md match the SkillTier enum values in core/skill_taxonomy.py

### S4.2 — Test CONTEXT.md

**File**: `tests/test_context_md.py` (NEW)

Write tests covering:

1. **File exists**: CONTEXT.md exists at repo root
2. **Contains core concepts**: File contains "Task", "Worker", "Skill", "Orchestrator", "Memory Router"
3. **Contains skill tiers**: File contains "USER_INVOKED", "AGENT_INVOKED", "HYBRID"
4. **Contains conventions**: File contains "timezone-aware UTC", "datetime.now(timezone.utc)"
5. **Markdown structure**: File has proper heading hierarchy (H1 at top, H2 sections)
6. **Tier name consistency**: Skill tier names in CONTEXT.md match SkillTier enum values in core/skill_taxonomy.py (prevents drift)

### S4.3 — Run all new tests

```powershell
python -m pytest tests/test_skill_taxonomy.py tests/test_context_md.py -v --tb=short
```

Expected: All tests pass.

### S4.4 — Run full test suite

```powershell
python -m pytest tests/ -q --tb=short
```

Expected: **1230+ passed (±5 from baseline), 0 failed, ~67 skipped**.

---

## S5 — Verification

S5.1. Ruff on all edited/created files:
```powershell
ruff check core/skill_taxonomy.py skills/classifications.py tests/test_skill_taxonomy.py tests/test_context_md.py
```
Expected: 0 errors.

S5.2. Mypy on all edited/created files:
```powershell
mypy core/skill_taxonomy.py skills/classifications.py tests/test_skill_taxonomy.py tests/test_context_md.py --ignore-missing-imports
```
Expected: 0 errors.

S5.3. Full test suite (repeat from S4.4):
```powershell
python -m pytest tests/ -q --tb=short
```

---

## S6 — Closing

Run `/jarvis-close`. This handles:
- Full test suite
- Ruff check
- Mypy check (file-scoped)
- Git add, commit, tag `prompt-68`
- CHANGELOG entry
- PLANS.md update (completed prompts row, baselines, queue shift)
- LANDMINES.md (if new pattern — likely none)
- Rule proposal (C9)
- Docs commit
- Push + post-push verification

### Expected CHANGELOG entry
```
## 2026-06-24 — prompt-68

**Plan**: Phase 1 Foundation: Skill Taxonomy + CONTEXT.md

**Changed**:
- core/skill_taxonomy.py: NEW — SkillTier enum, SkillClassification dataclass, SkillTaxonomyRegistry
- skills/classifications.py: NEW — Default registry with 25 built-in skill classifications (15 user, 9 agent, 1 hybrid)
- CONTEXT.md: NEW — Project-level shared vocabulary and domain context
- tests/test_skill_taxonomy.py: NEW — 14 tests for skill taxonomy
- tests/test_context_md.py: NEW — 6 tests for CONTEXT.md
- tests/<failing>: Fixed 2 pre-existing test failures

**Results**:
- Tests: <count> passed, <count> skipped, 0 failed
- Ruff: 0 errors
- Mypy: 0 errors (file-scoped)
- Tag: prompt-68 verified on origin
```

---

## Pre-declared scope

**WILL edit**:
- `core/skill_taxonomy.py` (NEW)
- `skills/classifications.py` (NEW)
- `CONTEXT.md` (NEW)
- `tests/test_skill_taxonomy.py` (NEW)
- `tests/test_context_md.py` (NEW)
- Any test file(s) with pre-existing failures (identified at S1)

**Will NOT edit**:
- `core/` existing files (no modifications to orchestrator, commands, etc.)
- `skills/` existing skill implementations (no modifications to skill.py files)
- `AGENTS.md`, `LANDMINES.md`, `AI_HANDOFF.md` (no new rules this plan)
- `system/`, `workers/`, `adapters/`, `cli/`, `memory/`, `web/` directories
- Any file not listed above
