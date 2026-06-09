"""
Tests for File Writer Skill.
"""

import pytest
import tempfile
import os

from skills.file_writer.skill import FileWriterSkill
from core.observability import MemoryTraceEmitter


class TestFileWriterSkill:
    """Test cases for FileWriterSkill."""

    @pytest.fixture
    def skill(self):
        """Create a FileWriterSkill instance with MemoryTraceEmitter."""
        emitter = MemoryTraceEmitter()
        return FileWriterSkill(approval_gate=None, emitter=emitter)

    @pytest.mark.asyncio
    async def test_execute_with_valid_path(self, skill):
        """Test successful file writing with valid path."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        try:
            success, bytes_written = await skill.execute(temp_path, "Test content")
            assert success is True
            assert bytes_written == len("Test content")

            # Verify content was written
            with open(temp_path, "r", encoding="utf-8") as f:
                assert f.read() == "Test content"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_with_append_mode(self, skill):
        """Test file writing in append mode."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("Initial content")
            temp_path = f.name

        try:
            success, bytes_written = await skill.execute(temp_path, " - appended", mode="append")
            assert success is True

            # Verify content was appended
            with open(temp_path, "r", encoding="utf-8") as f:
                assert f.read() == "Initial content - appended"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_with_invalid_path(self, skill):
        """Test that invalid path raises ValueError."""
        with pytest.raises(ValueError, match="Path must be a non-empty string"):
            await skill.execute("", "content")

    @pytest.mark.asyncio
    async def test_execute_with_non_string_path(self, skill):
        """Test that non-string path raises ValueError."""
        with pytest.raises(ValueError, match="Path must be a non-empty string"):
            await skill.execute(123, "content")

    @pytest.mark.asyncio
    async def test_execute_with_non_string_content(self, skill):
        """Test that non-string content raises ValueError."""
        with pytest.raises(ValueError, match="Content must be a string"):
            await skill.execute("/tmp/test.txt", 123)

    @pytest.mark.asyncio
    async def test_file_writer_with_approval_gate_none_proceeds_without_approval(self, skill):
        """Test that file writer proceeds without approval when approval_gate is None."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        try:
            success, bytes_written = await skill.execute(temp_path, "Test content")
            assert success is True
            assert bytes_written == len("Test content")

            # Verify content was written
            with open(temp_path, "r", encoding="utf-8") as f:
                assert f.read() == "Test content"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_file_writer_emits_trace_events(self, skill):
        """Test that file writer emits trace events."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        try:
            await skill.execute(temp_path, "Test content")
            
            # Check that trace events were emitted
            events = skill.emitter.get_events()
            assert len(events) > 0
            # Just check that events were emitted, don't validate specific content
        finally:
            os.unlink(temp_path)

    def test_skill_metadata_parsing(self):
        """Test that SKILL.md can be parsed correctly."""
        import os
        skill_md_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills", "file_writer", "SKILL.md")

        assert os.path.exists(skill_md_path), "SKILL.md must exist"

        with open(skill_md_path, "r") as f:
            content = f.read()

        assert "## Description" in content
        assert "## Parameters" in content
        assert "## Output" in content
        assert "## Dependencies" in content
        assert "## Hardware" in content
        assert "## Tags" in content
