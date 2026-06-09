"""
llama.cpp adapter tests.

Single responsibility: Test llama.cpp adapter functionality,
hardware configuration, and LLM generation.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from adapters.llama_cpp import LlamaCppAdapter
from core.schemas import Message, MessageRole


class TestLlamaCppAdapter:
    """Test LlamaCppAdapter functionality."""

    @pytest.fixture
    def llama_adapter(self):
        """Create a llama.cpp adapter with test configuration."""
        return LlamaCppAdapter(
            model_path="test_model.gguf",
            n_ctx=2048,
            n_gpu_layers=-1,
            n_threads=4,
            temperature=0.1,
        )

    def test_adapter_initialization(self, llama_adapter):
        """Test adapter initializes with correct configuration."""
        assert llama_adapter.model_path == "test_model.gguf"
        assert llama_adapter.n_ctx == 2048
        assert llama_adapter.n_gpu_layers == -1
        assert llama_adapter.n_threads == 4
        assert llama_adapter.temperature == 0.1
        assert llama_adapter._model is None

    def test_model_name_property(self, llama_adapter):
        """Test model_name property returns correct value."""
        assert llama_adapter.model_name == "test_model.gguf"

    def test_is_local_property(self, llama_adapter):
        """Test is_local property returns True."""
        assert llama_adapter.is_local is True

    def test_cost_per_token_property(self, llama_adapter):
        """Test cost_per_token returns 0 for local model."""
        assert llama_adapter.cost_per_token == 0.0

    def test_messages_to_prompt(self, llama_adapter):
        """Test message to prompt conversion."""
        messages = [
            Message(role=MessageRole.SYSTEM, content="System message", timestamp=datetime.now()),
            Message(role=MessageRole.USER, content="User message", timestamp=datetime.now()),
        ]

        prompt = llama_adapter._messages_to_prompt(messages)

        assert "System: System message" in prompt
        assert "User: User message" in prompt
        assert "Assistant:" in prompt

    def test_health_check_without_model(self, llama_adapter):
        """Test health check returns False when model not loaded."""
        import asyncio

        result = asyncio.run(llama_adapter.health_check())
        assert result is False

    def test_generate_without_model_raises_error(self, llama_adapter):
        """Test generate raises error when model not available."""
        import asyncio

        messages = [Message(role=MessageRole.USER, content="test", timestamp=datetime.now())]

        with pytest.raises(RuntimeError, match="llama.cpp generation failed"):
            asyncio.run(llama_adapter.generate(messages))

    def test_adapter_implements_interface(self, llama_adapter):
        """Test that adapter implements LLMAdapter interface."""
        from adapters.base import LLMAdapter

        assert isinstance(llama_adapter, LLMAdapter)
        assert hasattr(llama_adapter, "generate")
        assert hasattr(llama_adapter, "health_check")

    def test_hardware_configuration(self, llama_adapter):
        """Test hardware configuration parameters."""
        custom_adapter = LlamaCppAdapter(
            model_path="custom.gguf",
            n_gpu_layers=0,  # CPU only
            n_threads=8,
        )
        assert custom_adapter.n_gpu_layers == 0
        assert custom_adapter.n_threads == 8


