"""Tests for adapters/ollama.py"""

from datetime import datetime

import pytest

from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent, TraceLevel
from core.schemas import Message, MessageRole
from adapters.ollama import OllamaAdapter

pytestmark = pytest.mark.asyncio


class TestThinkingExtraction:
    """Test <thought> tag extraction from Ollama responses."""

    async def test_response_with_thinking_tags_emits_event_and_strips_tags(self) -> None:
        """Response with <thought> tags should emit event and strip tags from content."""
        emitter = MemoryTraceEmitter()
        adapter = OllamaAdapter(emitter=emitter)
        
        # Mock the HTTP client to return response with <thought> tags
        import httpx
        from unittest.mock import AsyncMock, Mock, patch
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": "<thought>\nLet me reason through this.\n</thought>\nThe answer is 42."
            },
            "eval_count": 10,
            "prompt_eval_count": 5,
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        adapter._client = mock_client
        
        messages = [Message(role=MessageRole.USER, content="What is the meaning of life?", timestamp=datetime.now())]
        
        response = await adapter.generate(messages)
        
        # Assert event was emitted
        events = emitter.get_events()
        thinking_events = [e for e in events if e.event_type == TraceEventType.MODEL_THINKING_CAPTURED]
        assert len(thinking_events) == 1
        assert thinking_events[0].component == TraceComponent.ADAPTER
        assert thinking_events[0].level == TraceLevel.DEBUG
        assert "Let me reason through this." in thinking_events[0].data["thinking"]
        assert thinking_events[0].data["thinking_length"] == len(thinking_events[0].data["thinking"])
        
        # Assert tags were stripped from response
        assert "<thought>" not in response.content
        assert "</thought>" not in response.content
        assert "The answer is 42." in response.content

    async def test_response_without_thinking_tags_no_event_emitted(self) -> None:
        """Response without <thought> tags should not emit event and content unchanged."""
        emitter = MemoryTraceEmitter()
        adapter = OllamaAdapter(emitter=emitter)
        
        # Mock the HTTP client to return response without <thought> tags
        import httpx
        from unittest.mock import AsyncMock, Mock, patch
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": "The answer is 42."
            },
            "eval_count": 10,
            "prompt_eval_count": 5,
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        adapter._client = mock_client
        
        messages = [Message(role=MessageRole.USER, content="What is the meaning of life?", timestamp=datetime.now())]
        
        response = await adapter.generate(messages)
        
        # Assert no thinking event was emitted
        events = emitter.get_events()
        thinking_events = [e for e in events if e.event_type == TraceEventType.MODEL_THINKING_CAPTURED]
        assert len(thinking_events) == 0
        
        # Assert content unchanged
        assert response.content == "The answer is 42."

    async def test_multiline_thinking_block_captured_fully(self) -> None:
        """Multi-line <thought> block should be captured fully in event data."""
        emitter = MemoryTraceEmitter()
        adapter = OllamaAdapter(emitter=emitter)
        
        # Mock the HTTP client to return response with multi-line thinking
        import httpx
        from unittest.mock import AsyncMock, Mock, patch
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": "<thought>\nLine 1 of reasoning\nLine 2 of reasoning\nLine 3 of reasoning\n</thought>\nThe answer is 42."
            },
            "eval_count": 10,
            "prompt_eval_count": 5,
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        adapter._client = mock_client
        
        messages = [Message(role=MessageRole.USER, content="What is the meaning of life?", timestamp=datetime.now())]
        
        response = await adapter.generate(messages)
        
        # Assert event was emitted with full multi-line content
        events = emitter.get_events()
        thinking_events = [e for e in events if e.event_type == TraceEventType.MODEL_THINKING_CAPTURED]
        assert len(thinking_events) == 1
        thinking_content = thinking_events[0].data["thinking"]
        assert "Line 1 of reasoning" in thinking_content
        assert "Line 2 of reasoning" in thinking_content
        assert "Line 3 of reasoning" in thinking_content

    async def test_empty_thinking_block_emits_event_with_empty_string(self) -> None:
        """Empty <thought></thought> block should emit event with empty thinking string."""
        emitter = MemoryTraceEmitter()
        adapter = OllamaAdapter(emitter=emitter)
        
        # Mock the HTTP client to return response with empty thinking block
        import httpx
        from unittest.mock import AsyncMock, Mock, patch
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": "<thought></thought>The answer is 42."
            },
            "eval_count": 10,
            "prompt_eval_count": 5,
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        adapter._client = mock_client
        
        messages = [Message(role=MessageRole.USER, content="What is the meaning of life?", timestamp=datetime.now())]
        
        response = await adapter.generate(messages)
        
        # Assert event was emitted with empty thinking string
        events = emitter.get_events()
        thinking_events = [e for e in events if e.event_type == TraceEventType.MODEL_THINKING_CAPTURED]
        assert len(thinking_events) == 1
        assert thinking_events[0].data["thinking"] == ""
        assert thinking_events[0].data["thinking_length"] == 0
        
        # Assert tags were stripped from response
        assert "<thinking>" not in response.content
        assert "</thinking>" not in response.content
