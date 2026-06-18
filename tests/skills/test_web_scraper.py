"""
Tests for Web Scraper Skill.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock

from skills.web_scraper.skill import WebScraperSkill
from core.observability import MemoryTraceEmitter


class TestWebScraperSkill:
    """Test cases for WebScraperSkill."""

    @pytest.fixture
    def skill(self):
        """Create a WebScraperSkill instance."""
        return WebScraperSkill(emitter=MemoryTraceEmitter())

    @pytest.mark.asyncio
    async def test_execute_with_valid_url(self, skill):
        """Test successful scraping with valid URL."""
        mock_response = AsyncMock()
        mock_response.text = "<html><body><h1>Test Content</h1></body></html>"
        mock_response.raise_for_status = Mock()

        with patch("skills.web_scraper.skill.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.__aexit__ = AsyncMock()

            result = await skill.execute("https://example.com")

            assert "Test Content" in result
            mock_client.return_value.__aenter__.return_value.get.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_execute_with_selector(self, skill):
        """Test scraping with CSS selector."""
        mock_response = AsyncMock()
        mock_response.text = "<html><body><p class='target'>Target Text</p><p>Other Text</p></body></html>"
        mock_response.raise_for_status = Mock()

        with patch("skills.web_scraper.skill.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.__aexit__ = AsyncMock()

            result = await skill.execute("https://example.com", selector=".target")

            assert "Target Text" in result
            assert "Other Text" not in result

        # Give event loop time to clean up transports
        import asyncio
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_execute_with_invalid_url(self, skill):
        """Test that invalid URL raises ValueError."""
        with pytest.raises(ValueError, match="URL must be a non-empty string"):
            await skill.execute("")

    @pytest.mark.asyncio
    async def test_execute_with_non_string_url(self, skill):
        """Test that non-string URL raises ValueError."""
        with pytest.raises(ValueError, match="URL must be a non-empty string"):
            await skill.execute(123)

    @pytest.mark.asyncio
    async def test_execute_http_error(self, skill):
        """Test that HTTP errors are propagated."""
        with patch("skills.web_scraper.skill.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = Exception("HTTP Error")
            mock_client.return_value.__aenter__.return_value.__aexit__ = AsyncMock()

            with pytest.raises(Exception, match="HTTP Error"):
                await skill.execute("https://example.com")

    def test_skill_metadata_parsing(self):
        """Test that SKILL.md can be parsed correctly."""
        import os
        skill_md_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills", "web_scraper", "SKILL.md")

        assert os.path.exists(skill_md_path), "SKILL.md must exist"

        with open(skill_md_path, "r") as f:
            content = f.read()

        assert "## Description" in content
        assert "## Parameters" in content
        assert "## Output" in content
        assert "## Dependencies" in content
        assert "## Hardware" in content
        assert "## Tags" in content
