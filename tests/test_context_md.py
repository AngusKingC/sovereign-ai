"""Tests for CONTEXT.md file."""


class TestContextMd:
    """Test CONTEXT.md file exists and has required content."""

    def test_file_exists(self) -> None:
        """CONTEXT.md exists at repo root."""
        import os
        assert os.path.exists("CONTEXT.md")

    def test_contains_core_concepts(self) -> None:
        """File contains 'Task', 'Worker', 'Skill', 'Orchestrator', 'Memory Router'."""
        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            content = f.read()
        assert "Task" in content
        assert "Worker" in content
        assert "Skill" in content
        assert "Orchestrator" in content
        assert "Memory Router" in content

    def test_contains_skill_tiers(self) -> None:
        """File contains 'USER_INVOKED', 'AGENT_INVOKED', 'HYBRID'."""
        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            content = f.read()
        assert "USER_INVOKED" in content
        assert "AGENT_INVOKED" in content
        assert "HYBRID" in content

    def test_contains_conventions(self) -> None:
        """File contains 'timezone-aware UTC', 'datetime.now(timezone.utc)'."""
        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            content = f.read()
        assert "timezone-aware UTC" in content
        assert "datetime.now(timezone.utc)" in content

    def test_markdown_structure(self) -> None:
        """File has proper heading hierarchy (H1 at top, H2 sections)."""
        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            lines = f.readlines()
        # First non-empty line should be H1
        first_content_line = next((line for line in lines if line.strip()), "")
        assert first_content_line.startswith("# ")
        # Should have H2 sections
        h2_lines = [line for line in lines if line.strip().startswith("## ")]
        assert len(h2_lines) > 0

    def test_tier_name_consistency(self) -> None:
        """Skill tier names in CONTEXT.md match SkillTier enum values in core/skill_taxonomy.py (prevents drift)."""
        from core.skill_taxonomy import SkillTier
        
        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Verify enum values match CONTEXT.md
        assert SkillTier.USER_INVOKED.value in content
        assert SkillTier.AGENT_INVOKED.value in content
        assert SkillTier.HYBRID.value in content
