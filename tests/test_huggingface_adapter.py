"""
Tests for HuggingFace adapter.

Unit tests use mocks and run without API key.
Integration tests require HUGGINGFACE_API_KEY (or HF_TOKEN) environment variable.
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from core.schemas import Message, MessageRole
from core.worker_base import LLMResponse


# --- Mocked fixtures for unit tests (run always, no API key needed) ---

@pytest.fixture
def mock_hf_client():
    """Mock httpx.AsyncClient for HuggingFace unit tests.
    
    HuggingFace uses httpx.AsyncClient directly (not an SDK class).
    Response shape: [{"generated_text": "..."}] or {"generated_text": "..."}.
    """
    mock_instance = MagicMock()
    # Mock POST response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=[{"generated_text": "Mock response"}])
    mock_response.raise_for_status = MagicMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    mock_instance.aclose = AsyncMock()
    
    with patch('adapters.huggingface.httpx.AsyncClient') as mock_class:
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_adapter(mock_hf_client):
    """HuggingFaceAdapter with mocked client — for unit tests."""
    from adapters.huggingface import HuggingFaceAdapter
    adapter = HuggingFaceAdapter(api_key="mock-key", model_name="meta-llama/Meta-Llama-3-70B-Instruct")
    adapter._ensure_client()
    return adapter


# --- Unit tests (mocked, run always) ---

class TestHuggingFaceAdapterUnit:
    """Unit tests — mocked, no API key required."""

    def test_initialization(self, mock_adapter):
        assert mock_adapter.model_name == "meta-llama/Meta-Llama-3-70B-Instruct"
        assert mock_adapter.is_local is False
        assert mock_adapter.cost_per_token == 0.0

    def test_model_name_property(self, mock_adapter):
        assert mock_adapter.model_name == "meta-llama/Meta-Llama-3-70B-Instruct"

    def test_is_local_property(self, mock_adapter):
        assert mock_adapter.is_local is False

    def test_cost_per_token_property(self, mock_adapter):
        assert mock_adapter.cost_per_token == 0.0

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        await mock_adapter.close()


# --- Integration tests (env-conditional, require real API key) ---

class TestHuggingFaceAdapterIntegration:
    """Integration tests — require real HUGGINGFACE_API_KEY (or HF_TOKEN)."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        if not os.getenv("HUGGINGFACE_API_KEY") and not os.getenv("HF_TOKEN"):
            pytest.skip("HUGGINGFACE_API_KEY (or HF_TOKEN) environment variable not set")

    @pytest.fixture
    def adapter(self):
        from adapters.huggingface import HuggingFaceAdapter
        api_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
        return HuggingFaceAdapter(api_key=api_key, model_name="meta-llama/Meta-Llama-3-70B-Instruct")

    @pytest.mark.asyncio
    async def test_health_check(self, adapter):
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_generate_simple_message(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Hello", timestamp=datetime.now(timezone.utc))]
        response = await adapter.generate(messages)
        assert isinstance(response, LLMResponse)
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_generate_with_system_message(self, adapter):
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are helpful.", timestamp=datetime.now(timezone.utc)),
            Message(role=MessageRole.USER, content="What is 2+2?", timestamp=datetime.now(timezone.utc)),
        ]
        response = await adapter.generate(messages)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_generate_with_temperature(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Say something creative.", timestamp=datetime.now(timezone.utc))]
        response = await adapter.generate(messages, temperature=0.8)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_generate_with_max_tokens(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Tell me a story.", timestamp=datetime.now(timezone.utc))]
        response = await adapter.generate(messages, max_tokens=100)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_consecutive_generations(self, adapter):
        messages1 = [Message(role=MessageRole.USER, content="What is 1+1?", timestamp=datetime.now(timezone.utc))]
        messages2 = [Message(role=MessageRole.USER, content="What is 2+2?", timestamp=datetime.now(timezone.utc))]
        response1 = await adapter.generate(messages1)
        response2 = await adapter.generate(messages2)
        assert isinstance(response1, LLMResponse)
        assert isinstance(response2, LLMResponse)
