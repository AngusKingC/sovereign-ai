"""Tests for the adapter factory."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from cli.adapter_factory import create_adapter
from core.worker_base import LLMAdapter


class TestAdapterFactory:
    """Tests for adapter factory."""
    
    def test_create_ollama_adapter(self) -> None:
        """Test creating Ollama adapter."""
        with patch('adapters.ollama.OllamaAdapter') as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter
            
            adapter = create_adapter("ollama", "llama3")
            
            assert adapter is mock_adapter
            mock_adapter_class.assert_called_once_with(
                base_url="http://localhost:11434",
                model_name="llama3"
            )
    
    def test_create_ollama_adapter_with_custom_url(self) -> None:
        """Test creating Ollama adapter with custom base URL."""
        with patch('adapters.ollama.OllamaAdapter') as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter
            
            adapter = create_adapter("ollama", "llama2", base_url="http://localhost:9999")
            
            assert adapter is mock_adapter
            mock_adapter_class.assert_called_once_with(
                base_url="http://localhost:9999",
                model_name="llama2"
            )
    
    def test_create_lm_studio_adapter(self) -> None:
        """Test creating LM Studio adapter."""
        with patch('adapters.lm_studio.LMStudioAdapter') as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter
            
            adapter = create_adapter("lm_studio", "model-name")
            
            assert adapter is mock_adapter
            mock_adapter_class.assert_called_once_with(
                base_url="http://localhost:1234",
                model_name="model-name"
            )
    
    def test_create_lm_studio_adapter_with_custom_url(self) -> None:
        """Test creating LM Studio adapter with custom base URL."""
        with patch('adapters.lm_studio.LMStudioAdapter') as mock_adapter_class:
            mock_adapter = Mock(spec=LLMAdapter)
            mock_adapter_class.return_value = mock_adapter
            
            adapter = create_adapter("lm_studio", "model-name", base_url="http://localhost:8888")
            
            assert adapter is mock_adapter
            mock_adapter_class.assert_called_once_with(
                base_url="http://localhost:8888",
                model_name="model-name"
            )
    
    def test_unknown_adapter_raises_value_error(self) -> None:
        """Test that unknown adapter name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_adapter("unknown", "model")
        
        assert "Unknown adapter: unknown" in str(exc_info.value)
        assert "Available adapters: ollama, lm_studio" in str(exc_info.value)
    
    def test_factory_returns_adapter_satisfying_protocol(self) -> None:
        """Test that factory produces object satisfying LLMAdapter Protocol."""
        with patch('adapters.ollama.OllamaAdapter') as mock_adapter_class:
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
            assert hasattr(adapter, 'generate')
            assert hasattr(adapter, 'health_check')
            assert hasattr(adapter, 'close')
            assert hasattr(adapter, 'model_name')
            assert hasattr(adapter, 'is_local')
            assert hasattr(adapter, 'cost_per_token')

