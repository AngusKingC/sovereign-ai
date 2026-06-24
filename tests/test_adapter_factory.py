"""Tests for the adapter factory."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from cli.adapter_factory import create_adapter
from core.worker_base import LLMAdapter


class TestAdapterFactory:
    """Tests for adapter factory."""

    def test_create_ollama_adapter(self) -> None:
        """Test creating Ollama adapter."""
        with patch("adapters.ollama.OllamaAdapter") as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter

            adapter = create_adapter("ollama", "llama3")

            assert adapter is mock_adapter
            mock_adapter_class.assert_called_once_with(
                base_url="http://localhost:11434", model_name="llama3"
            )

    def test_create_ollama_adapter_with_custom_url(self) -> None:
        """Test creating Ollama adapter with custom base URL."""
        with patch("adapters.ollama.OllamaAdapter") as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter

            adapter = create_adapter(
                "ollama", "llama2", base_url="http://localhost:9999"
            )

            assert adapter is mock_adapter
            mock_adapter_class.assert_called_once_with(
                base_url="http://localhost:9999", model_name="llama2"
            )

    def test_create_lm_studio_adapter(self) -> None:
        """Test creating LM Studio adapter."""
        with patch("adapters.lm_studio.LMStudioAdapter") as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter

            adapter = create_adapter("lm_studio", "model-name")

            assert adapter is mock_adapter
            mock_adapter_class.assert_called_once_with(
                base_url="http://localhost:1234", model_name="model-name"
            )

    def test_create_lm_studio_adapter_with_custom_url(self) -> None:
        """Test creating LM Studio adapter with custom base URL."""
        with patch("adapters.lm_studio.LMStudioAdapter") as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter

            adapter = create_adapter(
                "lm_studio", "model-name", base_url="http://localhost:8888"
            )

            assert adapter is mock_adapter
            mock_adapter_class.assert_called_once_with(
                base_url="http://localhost:8888", model_name="model-name"
            )

    def test_unknown_adapter_raises_value_error(self) -> None:
        """Test that unknown adapter name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_adapter("unknown", "model")

        assert "Unknown adapter: unknown" in str(exc_info.value)
        assert "Available adapters: ollama, lm_studio" in str(exc_info.value)

    def test_factory_returns_adapter_satisfying_protocol(self) -> None:
        """Test that factory produces object satisfying LLMAdapter Protocol."""
        with patch("adapters.ollama.OllamaAdapter") as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter

            # Add required protocol attributes and methods to mock
            mock_adapter.model_name = "test-model"
            mock_adapter.is_local = True
            mock_adapter.cost_per_token = 0.0
            mock_adapter.generate = AsyncMock()
            mock_adapter.health_check = AsyncMock(return_value=True)
            mock_adapter.close = AsyncMock()

            adapter = create_adapter("ollama", "llama3")

            # Verify it satisfies the protocol by checking required methods exist
            assert hasattr(adapter, "generate")
            assert hasattr(adapter, "health_check")
            assert hasattr(adapter, "close")
            assert hasattr(adapter, "model_name")
            assert hasattr(adapter, "is_local")
            assert hasattr(adapter, "cost_per_token")

    def test_create_prism_llama_adapter(self) -> None:
        """Test that create_adapter('prism_llama', ...) returns a PrismLlamaAdapter."""
        from adapters.prism_llama import PrismLlamaAdapter

        adapter = create_adapter(
            "prism_llama",
            "/fake/models/test.gguf",
            base_url="/fake/bin/llama-server",
            port=9090,
            n_gpu_layers=0,
        )
        assert isinstance(adapter, PrismLlamaAdapter)
        assert adapter._model_path == "/fake/models/test.gguf"
        assert adapter._binary_path == "/fake/bin/llama-server"
        assert adapter._port == 9090
        assert adapter._n_gpu_layers == 0

    def test_create_unknown_adapter_includes_prism_llama(self) -> None:
        """Test that prism_llama appears in the available adapters list."""
        try:
            create_adapter("nonexistent", "model")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "prism_llama" in str(e)
