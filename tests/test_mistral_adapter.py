"""
Tests for Mistral adapter.

Unit tests use mocks and run without API key.
Integration tests require MISTRAL_API_KEY environment variable.
"""

import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from core.schemas import Message, MessageRole
from core.worker_base import LLMResponse


# --- Mocked fixtures for unit tests (run always, no API key needed) ---

@pytest.fixture
def mock_mistral_client():
    """Mock AsyncOpenAI client for Mistral unit tests.
    
    Mistral uses AsyncOpenAI with base_url="https://api.mistral.ai/v1" —
    OpenAI-compatible response shape (choices[0].message.content).
    """
    with patch('adapters.mistral.AsyncOpenAI') as mock_class:
        mock_instance = MagicMock()
        mock_instance.chat = MagicMock()
        mock_instance.chat.completions = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Mock response"))],
            model="mistral-large-latest",
            usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ))
        mock_instance.close = AsyncMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_adapter(mock_mistral_client):
    """MistralAdapter with mocked client — for unit tests."""
    from adapters.mistral import MistralAdapter
    adapter = MistralAdapter(api_key="mock-key", model_name="mistral-large-latest")
    adapter._ensure_client()
    return adapter


# --- Unit tests (mocked, run always) ---

class TestMistralAdapterUnit:
    """Unit tests — mocked, no API key required."""

    def test_initialization(self, mock_adapter):
        assert mock_adapter.model_name == "mistral-large-latest"
        assert mock_adapter.is_local is False
        assert mock_adapter.cost_per_token > 0

    def test_model_name_property(self, mock_adapter):
        assert mock_adapter.model_name == "mistral-large-latest"

    def test_is_local_property(self, mock_adapter):
        assert mock_adapter.is_local is False

    def test_cost_per_token_property(self, mock_adapter):
        assert mock_adapter.cost_per_token > 0

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        await mock_adapter.close()


# --- Integration tests (env-conditional, require real API key) ---

class TestMistralAdapterIntegration:
    """Integration tests — require real MISTRAL_API_KEY."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        if not os.getenv("MISTRAL_API_KEY"):
            pytest.skip("MISTRAL_API_KEY environment variable not set")

    @pytest.fixture
    def adapter(self):
        from adapters.mistral import MistralAdapter
        return MistralAdapter(api_key=os.getenv("MISTRAL_API_KEY"), model_name="mistral-large-latest")

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
