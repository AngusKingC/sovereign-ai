"""
Tests for Google Gemini adapter.

Unit tests use mocks and run without API key.
Integration tests require GEMINI_API_KEY environment variable.
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from adapters.gemini import GeminiAdapter
from core.schemas import Message, MessageRole
from core.worker_base import LLMResponse


# --- Mocked fixtures for unit tests (run always, no API key needed) ---

@pytest.fixture
def mock_genai_client():
    """Mock google.genai.Client for unit tests."""
    with patch('adapters.gemini.genai.Client') as mock_client_class:
        mock_client = MagicMock()
        # Mock the async generate_content path: client.aio.models.generate_content
        mock_client.aio = MagicMock()
        mock_client.aio.models = MagicMock()
        mock_generate = AsyncMock(return_value=MagicMock(
            text="Mock response",
            usage_metadata=MagicMock(input_token_count=10, output_token_count=5),
        ))
        mock_client.aio.models.generate_content = mock_generate
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_adapter(mock_genai_client):
    """GeminiAdapter with mocked client — for unit tests."""
    adapter = GeminiAdapter(api_key="mock-key", model_name="gemini-1.5-flash")
    # Force eager client creation so test_close has a mock client to close
    adapter._ensure_client()
    return adapter


# --- Unit tests (mocked, run always) ---

class TestGeminiAdapterUnit:
    """Unit tests for GeminiAdapter — mocked, no API key required."""

    def test_initialization(self, mock_adapter):
        """Test adapter initialization."""
        assert mock_adapter.model_name == "gemini-1.5-flash"
        assert mock_adapter.is_local is False
        assert mock_adapter.cost_per_token == 0.0  # Free tier

    def test_model_name_property(self, mock_adapter):
        """Test model name property."""
        assert mock_adapter.model_name == "gemini-1.5-flash"

    def test_is_local_property(self, mock_adapter):
        """Test is_local property."""
        assert mock_adapter.is_local is False

    def test_cost_per_token_property(self, mock_adapter):
        """Test cost per token property."""
        assert mock_adapter.cost_per_token == 0.0

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        """Test closing the adapter doesn't raise."""
        await mock_adapter.close()


# --- Integration tests (env-conditional, require real API key) ---

@pytest.fixture
def api_key():
    """Get Gemini API key from environment."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY environment variable not set")
    return key


@pytest.fixture
def adapter(api_key):
    """Create Gemini adapter with real API key — for integration tests."""
    return GeminiAdapter(api_key=api_key)


class TestGeminiAdapterIntegration:
    """Integration tests for GeminiAdapter — require real GEMINI_API_KEY."""

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
        assert response.model == "gemini-3.5-flash"
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

