"""
Tests for Skill Registry.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.skill_registry import SkillRegistry, SkillMetadata


class TestSkillRegistry:
    """Test cases for SkillRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a SkillRegistry instance."""
        return SkillRegistry()

    @pytest.mark.asyncio
    async def test_discovery_finds_all_three_skills(self, registry):
        """Test that discovery finds all three skills."""
        with patch("core.skill_registry.emit_trace", new_callable=AsyncMock):
            skills = await registry.discover_skills()

        assert len(skills) >= 3
        assert "web_scraper" in skills
        assert "file_reader" in skills
        assert "file_writer" in skills

    @pytest.mark.asyncio
    async def test_validation_rejects_malformed_skill_md(self, registry, tmp_path):
        """Test that validation rejects a malformed SKILL.md."""
        # Create a malformed skill directory
        skill_dir = tmp_path / "bad_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("This is not a valid SKILL.md")

        metadata = SkillMetadata(
            name="bad_skill",
            description="",  # Missing required field
            parameters={},
            output_format="",  # Missing required field
            dependencies=[],
            hardware="",
            tags=[],
            skill_path=str(skill_dir),
        )

        with patch("core.skill_registry.emit_trace", new_callable=AsyncMock):
            is_valid = await registry.validate_skill(metadata)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_query_by_capability_returns_correct_results(self, registry):
        """Test that query by capability returns correct results."""
        with patch("core.skill_registry.emit_trace", new_callable=AsyncMock):
            await registry.discover_skills()

        web_scraping_skills = registry.query_by_capability("web-scraping")
        assert len(web_scraping_skills) > 0
        assert any("web_scraper" in skill.name for skill in web_scraping_skills)

    @pytest.mark.asyncio
    async def test_query_by_task_type_returns_correct_results(self, registry):
        """Test that query by task type returns correct results."""
        with patch("core.skill_registry.emit_trace", new_callable=AsyncMock):
            await registry.discover_skills()

        file_io_skills = registry.query_by_task_type("file-io")
        assert len(file_io_skills) > 0
        assert any("file_reader" in skill.name or "file_writer" in skill.name for skill in file_io_skills)

    @pytest.mark.asyncio
    async def test_registry_emits_correct_trace_events(self, registry):
        """Test that registry emits correct TraceEvents."""
        with patch("core.skill_registry.emit_trace", new_callable=AsyncMock) as mock_emit:
            await registry.discover_skills()

        # Should have emitted at least one trace event
        assert mock_emit.call_count > 0

        # Check that the last call was successful
        last_call = mock_emit.call_args_list[-1]
        assert last_call[1]["success"] is True
        assert last_call[1]["component"].value == "orchestrator"

    def test_get_skill_returns_correct_metadata(self, registry):
        """Test that get_skill returns correct metadata."""
        # Manually add a skill for testing
        metadata = SkillMetadata(
            name="test_skill",
            description="Test skill",
            parameters={},
            output_format="string",
            dependencies=[],
            hardware="",
            tags=["test"],
            skill_path="/tmp/test_skill",
        )
        registry._skills["test_skill"] = metadata

        result = registry.get_skill("test_skill")
        assert result is not None
        assert result.name == "test_skill"

    def test_get_skill_returns_none_for_nonexistent(self, registry):
        """Test that get_skill returns None for nonexistent skill."""
        result = registry.get_skill("nonexistent_skill")
        assert result is None

    def test_all_skills_returns_copy(self, registry):
        """Test that all_skills returns a copy of the skills dict."""
        registry._skills["skill1"] = SkillMetadata(
            name="skill1",
            description="Skill 1",
            parameters={},
            output_format="string",
            dependencies=[],
            hardware="",
            tags=["test"],
            skill_path="/tmp/skill1",
        )

        result = registry.all_skills()
        assert "skill1" in result

        # Modifying the returned dict should not affect the original
        result["skill2"] = "test"
        assert "skill2" not in registry._skills
