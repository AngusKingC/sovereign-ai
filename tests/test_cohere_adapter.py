"""
Tests for Cohere adapter.

Unit tests use mocks and run without API key.
Integration tests require COHERE_API_KEY environment variable.
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from adapters.cohere import CohereAdapter
from core.schemas import Message, MessageRole
from core.worker_base import LLMResponse


# --- Mocked fixtures for unit tests (run always, no API key needed) ---

@pytest.fixture
def mock_cohere_client():
    """Mock cohere.AsyncClient for unit tests.
    
    The adapter uses response.text for content and response.meta.billed_units
    for token usage (see adapters/cohere.py:114, 128, 137, 140).
    """
    with patch('adapters.cohere.cohere.AsyncClient') as mock_class:
        mock_instance = MagicMock()
        # Cohere v5+ SDK: client.chat() is a top-level async method
        mock_instance.chat = AsyncMock(return_value=MagicMock(
            text="Mock response",
            meta=MagicMock(
                billed_units=MagicMock(input_tokens=10, output_tokens=5),
                model_dump=MagicMock(return_value={"billed_units": {"input_tokens": 10, "output_tokens": 5}})
            ),
        ))
        mock_instance.close = AsyncMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_adapter(mock_cohere_client):
    """Cohere adapter with mocked client — for unit tests."""
    adapter = CohereAdapter(api_key="mock-key", model_name="command")
    # Force eager client creation so test_close has something to close
    # (CohereAdapter.__init__ sets _client=None lazily; close() does
    # nothing if _client was never populated)
    adapter._ensure_client()
    return adapter


# --- Unit tests (mocked, run always) ---

class TestCohereAdapterUnit:
    """Unit tests for CohereAdapter — mocked, no API key required."""

    def test_initialization(self, mock_adapter):
        """Test adapter initialization."""
        assert mock_adapter.model_name == "command"
        assert mock_adapter.is_local is False
        assert mock_adapter.cost_per_token == 0.0015

    def test_model_name_property(self, mock_adapter):
        """Test model name property."""
        assert mock_adapter.model_name == "command"

    def test_is_local_property(self, mock_adapter):
        """Test is_local property."""
        assert mock_adapter.is_local is False

    def test_cost_per_token_property(self, mock_adapter):
        """Test cost per token property."""
        assert mock_adapter.cost_per_token == 0.0015

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        """Test closing the adapter doesn't raise."""
        await mock_adapter.close()


# --- Integration tests (env-conditional, require real API key) ---

@pytest.fixture
def api_key():
    """Get Cohere API key from environment."""
    key = os.getenv("COHERE_API_KEY")
    if not key:
        pytest.skip("COHERE_API_KEY environment variable not set")
    return key


@pytest.fixture
def adapter(api_key):
    """Create Cohere adapter with real API key — for integration tests."""
    return CohereAdapter(api_key=api_key, model_name="command")


class TestCohereAdapterIntegration:
    """Integration tests for CohereAdapter — require real COHERE_API_KEY."""

    @pytest.mark.asyncio
    async def test_health_check(self, adapter):
        """Test health check."""
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_generate_simple_message(self, adapter):
        """Test generating a response with a simple message."""
        messages = [
            Message(role=MessageRole.USER, content="Hello, how are you?", timestamp=datetime.now(timezone.utc))
        ]

        response = await adapter.generate(messages)

        assert isinstance(response, LLMResponse)
        assert response.content is not None
        assert len(response.content) > 0
        assert response.model == "command"
        assert response.duration_ms > 0

    @pytest.mark.asyncio
    async def test_generate_with_system_message(self, adapter):
        """Test generating with a system message."""
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are a helpful assistant.", timestamp=datetime.now(timezone.utc)),
            Message(role=MessageRole.USER, content="What is 2+2?", timestamp=datetime.now(timezone.utc))
        ]

        response = await adapter.generate(messages)

        assert isinstance(response, LLMResponse)
        assert response.content is not None
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_generate_with_temperature(self, adapter):
        """Test generating with custom temperature."""
        messages = [
            Message(role=MessageRole.USER, content="Say something creative.", timestamp=datetime.now(timezone.utc))
        ]

        response = await adapter.generate(messages, temperature=0.8)

        assert isinstance(response, LLMResponse)
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_generate_with_max_tokens(self, adapter):
        """Test generating with max tokens limit."""
        messages = [
            Message(role=MessageRole.USER, content="Tell me a short story.", timestamp=datetime.now(timezone.utc))
        ]

        response = await adapter.generate(messages, max_tokens=100)

        assert isinstance(response, LLMResponse)
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_consecutive_generations(self, adapter):
        """Test multiple consecutive generations."""
        messages1 = [Message(role=MessageRole.USER, content="What is 1+1?", timestamp=datetime.now(timezone.utc))]
        messages2 = [Message(role=MessageRole.USER, content="What is 2+2?", timestamp=datetime.now(timezone.utc))]

        response1 = await adapter.generate(messages1)
        response2 = await adapter.generate(messages2)

        assert isinstance(response1, LLMResponse)
        assert isinstance(response2, LLMResponse)
        assert response1.content is not None
        assert response2.content is not None
