"""Tests for OllamaEmbedder."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.embedder import OllamaEmbedder


class TestOllamaEmbedder:
    """Tests for OllamaEmbedder class."""
    
    @pytest.mark.asyncio
    async def test_successful_embed_returns_correct_length_float_list(self) -> None:
        """Test that successful embed call returns correct-length float list."""
        with patch('core.embedder.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3] * 256}  # 768 dimensions
            mock_client.post.return_value = mock_response
            
            embedder = OllamaEmbedder()
            result = await embedder.embed("test text")
            
            assert isinstance(result, list)
            assert len(result) == 768
            assert all(isinstance(x, float) for x in result)
    
    @pytest.mark.asyncio
    async def test_correct_json_payload_sent_to_ollama_endpoint(self) -> None:
        """Test that correct JSON payload is sent to Ollama endpoint."""
        with patch('core.embedder.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"embedding": [0.1] * 768}
            mock_client.post.return_value = mock_response
            
            embedder = OllamaEmbedder(model="custom-model")
            await embedder.embed("test text")
            
            # Verify the POST call was made with correct payload
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://localhost:11434/api/embeddings"
            assert call_args[1]["json"] == {
                "model": "custom-model",
                "prompt": "test text"
            }
    
    @pytest.mark.asyncio
    async def test_http_error_raises_runtime_error(self) -> None:
        """Test that HTTP error raises RuntimeError."""
        with patch('core.embedder.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock HTTP error
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = Exception("HTTP 500")
            mock_client.post.return_value = mock_response
            
            embedder = OllamaEmbedder()
            
            with pytest.raises(RuntimeError) as exc_info:
                await embedder.embed("test text")
            
            assert "Ollama embed failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_connection_failure_raises_runtime_error(self) -> None:
        """Test that connection failure raises RuntimeError."""
        with patch('core.embedder.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock connection error
            from httpx import ConnectError
            mock_client.post.side_effect = ConnectError("Connection refused")
            
            embedder = OllamaEmbedder()
            
            with pytest.raises(RuntimeError) as exc_info:
                await embedder.embed("test text")
            
            assert "connection error" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self) -> None:
        """Test that health_check returns True on success."""
        with patch('core.embedder.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock successful health check
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            
            embedder = OllamaEmbedder()
            result = await embedder.health_check()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_connection_failure(self) -> None:
        """Test that health_check returns False on connection failure."""
        with patch('core.embedder.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock connection error
            from httpx import ConnectError
            mock_client.get.side_effect = ConnectError("Connection refused")
            
            embedder = OllamaEmbedder()
            result = await embedder.health_check()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_custom_base_url_and_model_are_used_correctly(self) -> None:
        """Test that custom base_url and model are used correctly."""
        with patch('core.embedder.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"embedding": [0.1] * 768}
            mock_client.post.return_value = mock_response
            
            embedder = OllamaEmbedder(base_url="http://custom:9999", model="custom-model")
            await embedder.embed("test")
            
            # Verify custom base URL is used
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://custom:9999/api/embeddings"
            assert call_args[1]["json"]["model"] == "custom-model"
    
    @pytest.mark.asyncio
    async def test_empty_string_input_is_handled_without_error(self) -> None:
        """Test that empty string input is handled without error."""
        with patch('core.embedder.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"embedding": [0.1] * 768}
            mock_client.post.return_value = mock_response
            
            embedder = OllamaEmbedder()
            result = await embedder.embed("")
            
            assert isinstance(result, list)
            assert len(result) == 768

