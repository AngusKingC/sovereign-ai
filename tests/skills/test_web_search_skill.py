"""
Tests for Web Search Skill.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from skills.web_search.skill import WebSearchSkill
from core.observability import (
    TraceEventType,
    TraceLevel,
    TraceComponent,
    MemoryTraceEmitter,
)


class TestWebSearchSkill:
    """Test suite for WebSearchSkill."""

    @pytest.fixture
    def emitter(self):
        """Create a memory trace emitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def skill(self, emitter):
        """Create a WebSearchSkill instance for testing."""
        return WebSearchSkill(emitter=emitter, searxng_url="http://localhost:8080")

    @pytest.fixture
    def skill_brave(self, emitter):
        """Create a WebSearchSkill instance with Brave API key."""
        return WebSearchSkill(emitter=emitter, brave_api_key="test_key")

    @pytest.fixture
    def skill_no_backend(self, emitter):
        """Create a WebSearchSkill instance with no backend."""
        return WebSearchSkill(emitter=emitter)

    @pytest.mark.asyncio
    async def test_searxng_backend_returns_structured_results(self, skill):
        """Test that SearXNG backend returns structured results."""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "results": [
                {"title": "Test Title", "url": "http://example.com", "content": "Test content"}
            ]
        })
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await skill.execute("test query")

        assert result["success"] is True
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Test Title"
        assert result["results"][0]["url"] == "http://example.com"
        assert result["results"][0]["snippet"] == "Test content"
        assert result["results"][0]["source"] == "searxng"

    @pytest.mark.asyncio
    async def test_brave_search_fallback_used_when_searxng_unavailable(self, skill_brave):
        """Test that Brave Search fallback is used when SearXNG is unavailable."""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "web": {
                "results": [
                    {"title": "Brave Result", "url": "http://brave.com", "description": "Brave description"}
                ]
            }
        })
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            result = await skill_brave.execute("test query")

        assert result["success"] is True
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Brave Result"
        assert result["results"][0]["source"] == "brave"

    @pytest.mark.asyncio
    async def test_no_backend_configured_returns_success_false(self, skill_no_backend):
        """Test that no backend configured returns success=False."""
        result = await skill_no_backend.execute("test query")

        assert result["success"] is False
        assert result["error"] == "No search backend configured"
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_max_results_is_respected(self, emitter):
        """Test that max_results is respected."""
        skill = WebSearchSkill(emitter=emitter, searxng_url="http://localhost:8080", max_results=5)
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "results": [
                {"title": f"Title {i}", "url": f"http://example.com/{i}", "content": f"Content {i}"}
                for i in range(10)
            ]
        })
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await skill.execute("test query")

        assert result["success"] is True
        assert len(result["results"]) == 5

    @pytest.mark.asyncio
    async def test_http_error_returns_success_false_with_error_message(self, skill):
        """Test that HTTP error returns success=False with error message."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Connection error")
            )
            result = await skill.execute("test query")

        assert result["success"] is False
        assert "SearXNG error" in result["error"]
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_results_contain_required_fields(self, skill):
        """Test that results contain required fields (title, url, snippet, source)."""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "results": [
                {"title": "Test", "url": "http://example.com", "content": "Snippet"}
            ]
        })
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await skill.execute("test query")

        assert result["success"] is True
        for res in result["results"]:
            assert "title" in res
            assert "url" in res
            assert "snippet" in res
            assert "source" in res

    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_search_start_and_complete(self, skill, emitter):
        """Test that trace events are emitted on search start and complete."""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={"results": []})
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            await skill.execute("test query")

        events = emitter.get_events()
        assert len(events) >= 2

        start_events = [e for e in events if e.event_type == TraceEventType.COMPONENT_START]
        assert len(start_events) >= 1
        assert start_events[0].component == TraceComponent.WORKER
        assert "Web search started" in start_events[0].message

        complete_events = [e for e in events if e.event_type == TraceEventType.OPERATION_COMPLETE]
        assert len(complete_events) >= 1
        assert complete_events[0].component == TraceComponent.WORKER
        assert "Web search completed" in complete_events[0].message

    @pytest.mark.asyncio
    async def test_trace_events_emitted_on_error(self, skill_no_backend, emitter):
        """Test that trace events are emitted on error."""
        await skill_no_backend.execute("test query")

        events = emitter.get_events()
        error_events = [e for e in events if e.event_type == TraceEventType.OPERATION_ERROR]
        assert len(error_events) >= 1
        assert error_events[0].component == TraceComponent.WORKER
        assert "Web search failed" in error_events[0].message
        assert error_events[0].level == TraceLevel.ERROR

    @pytest.mark.asyncio
    async def test_empty_query_raises_value_error(self, skill):
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            await skill.execute("")

    @pytest.mark.asyncio
    async def test_non_string_query_raises_value_error(self, skill):
        """Test that non-string query raises ValueError."""
        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            await skill.execute(123)

    @pytest.mark.asyncio
    async def test_trace_event_fields_are_correct(self, skill, emitter):
        """Test that TraceEvent fields are correct (event_type, component, level, message, data, duration_ms)."""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={"results": []})
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            await skill.execute("test query")

        events = emitter.get_events()
        for event in events:
            assert hasattr(event, "event_type")
            assert hasattr(event, "component")
            assert hasattr(event, "level")
            assert hasattr(event, "message")
            assert hasattr(event, "data")
            assert hasattr(event, "duration_ms")
            # Should NOT have these fields from the incorrect schema
            assert not hasattr(event, "layer")
            assert not hasattr(event, "payload")
            assert not hasattr(event, "success")
