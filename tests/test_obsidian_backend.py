"""
Obsidian backend tests.

Single responsibility: Test Obsidian markdown vault integration,
file I/O operations, and markdown formatting.
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from core.schemas import Task, TaskPriority
from memory.obsidian import ObsidianBackend


class TestObsidianBackend:
    """Test ObsidianBackend functionality."""

    @pytest.fixture
    def temp_vault(self, tmp_path):
        """Create a temporary vault directory for testing."""
        vault_path = tmp_path / "test_vault"
        return str(vault_path)

    @pytest.fixture
    def obsidian_backend(self, temp_vault):
        """Create an ObsidianBackend with a temporary vault."""
        return ObsidianBackend(temp_vault)

    @pytest.fixture
    def sample_task(self):
        """Create a sample task for testing."""
        return Task(
            task_id=uuid4(),
            intent="Test task",
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            created_at=datetime.now(),
        )

    def test_backend_initialization(self, temp_vault):
        """Test backend initializes and creates vault directory."""
        backend = ObsidianBackend(temp_vault)
        assert backend.vault_path.exists()
        assert backend.vault_path.is_dir()

    def test_fetch_from_empty_vault(self, obsidian_backend, sample_task):
        """Test fetching from an empty vault returns empty list."""
        import asyncio

        memory = asyncio.run(obsidian_backend.fetch(sample_task))
        assert memory == []

    def test_write_creates_markdown_file(self, obsidian_backend):
        """Test writing data creates a markdown file."""
        import asyncio

        data = {"content": "test data", "key": "value"}
        asyncio.run(obsidian_backend.write(data))

        # Check that a .md file was created
        md_files = list(obsidian_backend.vault_path.glob("*.md"))
        assert len(md_files) == 1
        assert md_files[0].suffix == ".md"

    def test_write_content_formatting(self, obsidian_backend):
        """Test that written content is properly formatted as markdown."""
        import asyncio

        data = {"content": "test data", "key": "value", "number": 42}
        asyncio.run(obsidian_backend.write(data))

        md_file = list(obsidian_backend.vault_path.glob("*.md"))[0]
        content = md_file.read_text(encoding="utf-8")

        assert "# Memory Entry" in content
        assert "**content**: test data" in content
        assert "**key**: value" in content
        assert "**number**: 42" in content

    def test_fetch_returns_written_data(self, obsidian_backend, sample_task):
        """Test that fetch returns data that was previously written."""
        import asyncio

        # Write some data
        data = {"content": "test memory", "source": "test"}
        asyncio.run(obsidian_backend.write(data))

        # Fetch it back
        memory = asyncio.run(obsidian_backend.fetch(sample_task))

        assert len(memory) == 1
        assert memory[0]["source"] == "obsidian"
        assert "test memory" in memory[0]["content"]

    def test_fetch_multiple_files(self, obsidian_backend, sample_task):
        """Test fetching multiple markdown files."""
        import asyncio

        # Write multiple entries
        for i in range(3):
            data = {"content": f"memory {i}", "index": i}
            asyncio.run(obsidian_backend.write(data))

        # Fetch all
        memory = asyncio.run(obsidian_backend.fetch(sample_task))

        assert len(memory) == 3

    def test_write_with_complex_data(self, obsidian_backend):
        """Test writing complex data structures (lists, dicts)."""
        import asyncio

        data = {
            "content": "test",
            "tags": ["tag1", "tag2"],
            "metadata": {"key": "value"},
        }
        asyncio.run(obsidian_backend.write(data))

        md_file = list(obsidian_backend.vault_path.glob("*.md"))[0]
        content = md_file.read_text(encoding="utf-8")

        assert "```json" in content
        assert "tags" in content
        assert "metadata" in content

    def test_vault_path_creation(self, tmp_path):
        """Test that vault path is created if it doesn't exist."""
        vault_path = tmp_path / "new_vault" / "nested"
        backend = ObsidianBackend(str(vault_path))

        assert backend.vault_path.exists()
        assert backend.vault_path.is_dir()

