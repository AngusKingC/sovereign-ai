"""Tests for skill taxonomy system."""

import pytest
from core.skill_taxonomy import (
    SkillTier,
    SkillClassification,
    SkillTaxonomyRegistry,
)
from skills.classifications import build_default_registry


class TestSkillTier:
    """Test SkillTier enum."""

    def test_enum_values_exist(self) -> None:
        """Verify all three tiers exist and have correct values."""
        assert SkillTier.USER_INVOKED.value == "user_invoked"
        assert SkillTier.AGENT_INVOKED.value == "agent_invoked"
        assert SkillTier.HYBRID.value == "hybrid"


class TestSkillClassification:
    """Test SkillClassification dataclass."""

    def test_create_classification(self) -> None:
        """Create a classification, verify immutability (frozen dataclass)."""
        classification = SkillClassification(
            skill_name="test_skill",
            tier=SkillTier.USER_INVOKED,
            description="Test skill description",
            auto_invoke_conditions=[],
            requires_approval=False,
        )
        assert classification.skill_name == "test_skill"
        assert classification.tier == SkillTier.USER_INVOKED
        assert classification.description == "Test skill description"
        assert classification.auto_invoke_conditions == []
        assert classification.requires_approval is False

    def test_frozen_dataclass(self) -> None:
        """Verify dataclass is frozen (immutable)."""
        classification = SkillClassification(
            skill_name="test_skill",
            tier=SkillTier.USER_INVOKED,
            description="Test skill description",
            auto_invoke_conditions=[],
            requires_approval=False,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            classification.skill_name = "new_name"  # type: ignore


class TestSkillTaxonomyRegistry:
    """Test SkillTaxonomyRegistry."""

    def test_register_and_retrieve(self) -> None:
        """Register a skill, retrieve it by name."""
        registry = SkillTaxonomyRegistry()
        classification = SkillClassification(
            skill_name="test_skill",
            tier=SkillTier.USER_INVOKED,
            description="Test skill description",
            auto_invoke_conditions=[],
            requires_approval=False,
        )
        registry.register(classification)
        retrieved = registry.classify("test_skill")
        assert retrieved is not None
        assert retrieved.skill_name == "test_skill"

    def test_register_duplicate_raises(self) -> None:
        """Register same name twice → raises ValueError."""
        registry = SkillTaxonomyRegistry()
        classification = SkillClassification(
            skill_name="test_skill",
            tier=SkillTier.USER_INVOKED,
            description="Test skill description",
            auto_invoke_conditions=[],
            requires_approval=False,
        )
        registry.register(classification)
        with pytest.raises(ValueError, match="already classified"):
            registry.register(classification)

    def test_classify_existing(self) -> None:
        """Look up existing skill → returns classification."""
        registry = SkillTaxonomyRegistry()
        classification = SkillClassification(
            skill_name="test_skill",
            tier=SkillTier.USER_INVOKED,
            description="Test skill description",
            auto_invoke_conditions=[],
            requires_approval=False,
        )
        registry.register(classification)
        result = registry.classify("test_skill")
        assert result is not None
        assert result.skill_name == "test_skill"

    def test_classify_missing(self) -> None:
        """Look up nonexistent skill → returns None."""
        registry = SkillTaxonomyRegistry()
        result = registry.classify("nonexistent")
        assert result is None

    def test_skills_by_tier(self) -> None:
        """Filter by USER_INVOKED, verify only user-invoked skills returned."""
        registry = SkillTaxonomyRegistry()
        registry.register(SkillClassification(
            skill_name="user_skill",
            tier=SkillTier.USER_INVOKED,
            description="User skill",
            auto_invoke_conditions=[],
            requires_approval=False,
        ))
        registry.register(SkillClassification(
            skill_name="agent_skill",
            tier=SkillTier.AGENT_INVOKED,
            description="Agent skill",
            auto_invoke_conditions=["test"],
            requires_approval=False,
        ))
        user_skills = registry.skills_by_tier(SkillTier.USER_INVOKED)
        assert len(user_skills) == 1
        assert user_skills[0].skill_name == "user_skill"

    def test_agent_invocable_skills(self) -> None:
        """Verify returns AGENT_INVOKED + HYBRID only."""
        registry = SkillTaxonomyRegistry()
        registry.register(SkillClassification(
            skill_name="user_skill",
            tier=SkillTier.USER_INVOKED,
            description="User skill",
            auto_invoke_conditions=[],
            requires_approval=False,
        ))
        registry.register(SkillClassification(
            skill_name="agent_skill",
            tier=SkillTier.AGENT_INVOKED,
            description="Agent skill",
            auto_invoke_conditions=["test"],
            requires_approval=False,
        ))
        registry.register(SkillClassification(
            skill_name="hybrid_skill",
            tier=SkillTier.HYBRID,
            description="Hybrid skill",
            auto_invoke_conditions=["test"],
            requires_approval=False,
        ))
        agent_invocable = registry.agent_invocable_skills()
        assert len(agent_invocable) == 2
        skill_names = {s.skill_name for s in agent_invocable}
        assert skill_names == {"agent_skill", "hybrid_skill"}

    def test_user_invocable_skills(self) -> None:
        """Verify returns USER_INVOKED + HYBRID only."""
        registry = SkillTaxonomyRegistry()
        registry.register(SkillClassification(
            skill_name="user_skill",
            tier=SkillTier.USER_INVOKED,
            description="User skill",
            auto_invoke_conditions=[],
            requires_approval=False,
        ))
        registry.register(SkillClassification(
            skill_name="agent_skill",
            tier=SkillTier.AGENT_INVOKED,
            description="Agent skill",
            auto_invoke_conditions=["test"],
            requires_approval=False,
        ))
        registry.register(SkillClassification(
            skill_name="hybrid_skill",
            tier=SkillTier.HYBRID,
            description="Hybrid skill",
            auto_invoke_conditions=["test"],
            requires_approval=False,
        ))
        user_invocable = registry.user_invocable_skills()
        assert len(user_invocable) == 2
        skill_names = {s.skill_name for s in user_invocable}
        assert skill_names == {"user_skill", "hybrid_skill"}


class TestBuildDefaultRegistry:
    """Test build_default_registry function."""

    def test_all_skills_registered(self) -> None:
        """Verify all expected skills are registered (count should be 25: 15 user, 9 agent, 1 hybrid)."""
        registry = build_default_registry()
        all_classifications = registry.all_classifications
        # Pre-flight check found 17 skills in repo, but plan expects 25 classifications
        # This test verifies the classifications.py has the expected count from the plan
        assert len(all_classifications) == 25

    def test_tier_split(self) -> None:
        """Verify all three tiers (USER_INVOKED, AGENT_INVOKED, HYBRID) have entries."""
        registry = build_default_registry()
        user_skills = registry.skills_by_tier(SkillTier.USER_INVOKED)
        agent_skills = registry.skills_by_tier(SkillTier.AGENT_INVOKED)
        hybrid_skills = registry.skills_by_tier(SkillTier.HYBRID)
        assert len(user_skills) == 15
        assert len(agent_skills) == 9
        assert len(hybrid_skills) == 1

    def test_auto_invoke_conditions(self) -> None:
        """Verify agent-invoked and hybrid skills have non-empty auto_invoke_conditions; user-invoked skills have empty."""
        registry = build_default_registry()
        for classification in registry.all_classifications.values():
            if classification.tier in (SkillTier.AGENT_INVOKED, SkillTier.HYBRID):
                assert len(classification.auto_invoke_conditions) > 0, f"{classification.skill_name} should have auto_invoke_conditions"
            elif classification.tier == SkillTier.USER_INVOKED:
                assert len(classification.auto_invoke_conditions) == 0, f"{classification.skill_name} should have empty auto_invoke_conditions"

    def test_approval_requirements(self) -> None:
        """Verify destructive skills (docker, terminal, email) have requires_approval=True."""
        registry = build_default_registry()
        destructive_skills = ["docker", "terminal", "email"]
        for skill_name in destructive_skills:
            classification = registry.classify(skill_name)
            assert classification is not None
            assert classification.requires_approval is True, f"{skill_name} should require approval"


class TestContextMdConsistency:
    """Test consistency between CONTEXT.md and skill taxonomy."""

    def test_tier_name_consistency(self) -> None:
        """Verify the skill tier names in CONTEXT.md match the SkillTier enum values in core/skill_taxonomy.py."""
        # Read CONTEXT.md
        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            context_md = f.read()
        
        # Verify tier names are present
        assert "USER_INVOKED" in context_md
        assert "AGENT_INVOKED" in context_md
        assert "HYBRID" in context_md
        
        # Verify they match enum values
        assert SkillTier.USER_INVOKED.value in context_md
        assert SkillTier.AGENT_INVOKED.value in context_md
        assert SkillTier.HYBRID.value in context_md
