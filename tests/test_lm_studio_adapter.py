"""
LM Studio adapter tests.

Single responsibility: Test LM Studio adapter functionality,
server communication, and LLM generation.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from adapters.lm_studio import LMStudioAdapter
from core.schemas import Message, MessageRole


class TestLMStudioAdapter:
    """Test LMStudioAdapter functionality."""

    @pytest.fixture
    def lm_studio_adapter(self):
        """Create an LM Studio adapter with test configuration."""
        return LMStudioAdapter(
            base_url="http://localhost:1234/v1",
            model_name="local-model",
            temperature=0.1,
        )

    def test_adapter_initialization(self, lm_studio_adapter):
        """Test adapter initializes with correct configuration."""
        assert lm_studio_adapter.base_url == "http://localhost:1234/v1"
        assert lm_studio_adapter.model_name == "local-model"
        assert lm_studio_adapter.temperature == 0.1
        assert lm_studio_adapter._client is None

    def test_model_name_property(self, lm_studio_adapter):
        """Test model_name property returns correct value."""
        assert lm_studio_adapter.model_name == "local-model"

    def test_is_local_property(self, lm_studio_adapter):
        """Test is_local property returns True."""
        assert lm_studio_adapter.is_local is True

    def test_cost_per_token_property(self, lm_studio_adapter):
        """Test cost_per_token returns 0 for local model."""
        assert lm_studio_adapter.cost_per_token == 0.0

    def test_messages_to_openai_format(self, lm_studio_adapter):
        """Test message to OpenAI format conversion."""
        messages = [
            Message(role=MessageRole.SYSTEM, content="System message", timestamp=datetime.now()),
            Message(role=MessageRole.USER, content="User message", timestamp=datetime.now()),
        ]

        openai_format = lm_studio_adapter._messages_to_openai_format(messages)

        assert len(openai_format) == 2
        assert openai_format[0] == {"role": "system", "content": "System message"}
        assert openai_format[1] == {"role": "user", "content": "User message"}

    def test_health_check_without_server(self, lm_studio_adapter):
        """Test health check returns False when server not available."""
        import asyncio

        result = asyncio.run(lm_studio_adapter.health_check())
        assert result is False

    def test_generate_without_server_raises_error(self, lm_studio_adapter):
        """Test generate raises error when server not available."""
        import asyncio

        messages = [Message(role=MessageRole.USER, content="test", timestamp=datetime.now())]

        with pytest.raises(RuntimeError, match="LM Studio generation failed"):
            asyncio.run(lm_studio_adapter.generate(messages))

    def test_adapter_implements_interface(self, lm_studio_adapter):
        """Test that adapter implements LLMAdapter interface."""
        from core.worker_base import LLMAdapter

        assert isinstance(lm_studio_adapter, LLMAdapter)
        assert hasattr(lm_studio_adapter, "generate")
        assert hasattr(lm_studio_adapter, "health_check")

    def test_base_url_configuration(self, lm_studio_adapter):
        """Test base_url is configurable."""
        custom_adapter = LMStudioAdapter(base_url="http://localhost:5678/v1")
        assert custom_adapter.base_url == "http://localhost:5678/v1"

    def test_close_without_client(self, lm_studio_adapter):
        """Test close works even without client."""
        import asyncio

        # Should not raise error
        asyncio.run(lm_studio_adapter.close())
        assert lm_studio_adapter._client is None

