"""
Tests for DeepSeek adapter.

Unit tests use mocks and run without API key.
Integration tests require DEEPSEEK_API_KEY environment variable.
"""

import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from core.schemas import Message, MessageRole
from core.worker_base import LLMResponse


# --- Mocked fixtures for unit tests (run always, no API key needed) ---

@pytest.fixture
def mock_deepseek_client():
    """Mock AsyncOpenAI client for DeepSeek unit tests.
    
    DeepSeek uses AsyncOpenAI with base_url="https://api.deepseek.com/v1" —
    OpenAI-compatible response shape (choices[0].message.content).
    """
    with patch('adapters.deepseek.AsyncOpenAI') as mock_class:
        mock_instance = MagicMock()
        mock_instance.chat = MagicMock()
        mock_instance.chat.completions = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Mock response"))],
            model="deepseek-chat",
            usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ))
        mock_instance.close = AsyncMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_adapter(mock_deepseek_client):
    """DeepSeekAdapter with mocked client — for unit tests."""
    from adapters.deepseek import DeepSeekAdapter
    adapter = DeepSeekAdapter(api_key="mock-key", model_name="deepseek-chat")
    adapter._ensure_client()
    return adapter


# --- Unit tests (mocked, run always) ---

class TestDeepSeekAdapterUnit:
    """Unit tests — mocked, no API key required."""

    def test_initialization(self, mock_adapter):
        assert mock_adapter.model_name == "deepseek-chat"
        assert mock_adapter.is_local is False
        assert mock_adapter.cost_per_token > 0

    def test_model_name_property(self, mock_adapter):
        assert mock_adapter.model_name == "deepseek-chat"

    def test_is_local_property(self, mock_adapter):
        assert mock_adapter.is_local is False

    def test_cost_per_token_property(self, mock_adapter):
        assert mock_adapter.cost_per_token > 0

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        await mock_adapter.close()


# --- Integration tests (env-conditional, require real API key) ---

class TestDeepSeekAdapterIntegration:
    """Integration tests — require real DEEPSEEK_API_KEY."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        if not os.getenv("DEEPSEEK_API_KEY"):
            pytest.skip("DEEPSEEK_API_KEY environment variable not set")

    @pytest.fixture
    def adapter(self):
        from adapters.deepseek import DeepSeekAdapter
        return DeepSeekAdapter(api_key=os.getenv("DEEPSEEK_API_KEY"), model_name="deepseek-chat")

    @pytest.mark.asyncio
    async def test_health_check(self, adapter):
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_generate_simple_message(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Hello", timestamp=datetime.now())]
        response = await adapter.generate(messages)
        assert isinstance(response, LLMResponse)
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_generate_with_system_message(self, adapter):
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are helpful.", timestamp=datetime.now()),
            Message(role=MessageRole.USER, content="What is 2+2?", timestamp=datetime.now()),
        ]
        response = await adapter.generate(messages)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_generate_with_temperature(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Say something creative.", timestamp=datetime.now())]
        response = await adapter.generate(messages, temperature=0.8)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_generate_with_max_tokens(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Tell me a story.", timestamp=datetime.now())]
        response = await adapter.generate(messages, max_tokens=100)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_consecutive_generations(self, adapter):
        messages1 = [Message(role=MessageRole.USER, content="What is 1+1?", timestamp=datetime.now())]
        messages2 = [Message(role=MessageRole.USER, content="What is 2+2?", timestamp=datetime.now())]
        response1 = await adapter.generate(messages1)
        response2 = await adapter.generate(messages2)
        assert isinstance(response1, LLMResponse)
        assert isinstance(response2, LLMResponse)
