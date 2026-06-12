"""
Tests for File Reader Skill.
"""

import pytest
import tempfile
import os
from unittest.mock import AsyncMock, patch

from skills.file_reader.skill import FileReaderSkill
from core.observability import MemoryTraceEmitter


class TestFileReaderSkill:
    """Test cases for FileReaderSkill."""

    @pytest.fixture
    def skill(self):
        """Create a FileReaderSkill instance."""
        return FileReaderSkill(emitter=MemoryTraceEmitter())

    @pytest.mark.asyncio
    async def test_execute_with_valid_path(self, skill):
        """Test successful file reading with valid path."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("Test file content")
            temp_path = f.name

        try:
            result = await skill.execute(temp_path)
            assert result == "Test file content"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_with_custom_encoding(self, skill):
        """Test file reading with custom encoding."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("Test file content")
            temp_path = f.name

        try:
            result = await skill.execute(temp_path, encoding="utf-8")
            assert result == "Test file content"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_with_invalid_path(self, skill):
        """Test that invalid path raises ValueError."""
        with pytest.raises(ValueError, match="Path must be a non-empty string"):
            await skill.execute("")

    @pytest.mark.asyncio
    async def test_execute_with_non_string_path(self, skill):
        """Test that non-string path raises ValueError."""
        with pytest.raises(ValueError, match="Path must be a non-empty string"):
            await skill.execute(123)

    @pytest.mark.asyncio
    async def test_execute_file_not_found(self, skill):
        """Test that FileNotFoundError is raised for non-existent file."""
        with pytest.raises(FileNotFoundError):
            await skill.execute("/nonexistent/path/to/file.txt")

    def test_skill_metadata_parsing(self):
        """Test that SKILL.md can be parsed correctly."""
        import os
        skill_md_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills", "file_reader", "SKILL.md")

        assert os.path.exists(skill_md_path), "SKILL.md must exist"

        with open(skill_md_path, "r") as f:
            content = f.read()

        assert "## Description" in content
        assert "## Parameters" in content
        assert "## Output" in content
        assert "## Dependencies" in content
        assert "## Hardware" in content
        assert "## Tags" in content
