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
