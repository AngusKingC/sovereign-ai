"""Tests for PrismLlamaAdapter — mirrors test_lm_studio_adapter.py pattern.

Mocks subprocess launch and httpx calls. Does NOT require a real
modified llama-server binary or model file — those are user-managed.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from adapters.prism_llama import PrismLlamaAdapter
from core.schemas import Message, MessageRole


class TestPrismLlamaAdapter:
    """Tests for PrismLlamaAdapter — mirrors TestLMStudioAdapter pattern."""

    @pytest.fixture
    def prism_adapter(self):
        """Create a PrismLlamaAdapter with test config."""
        return PrismLlamaAdapter(
            model_path="/fake/models/test.gguf",
            binary_path="/fake/bin/llama-server",
            port=8081,
            emitter=MagicMock(),
        )

    @pytest.fixture
    def mock_messages(self):
        """Create test messages."""
        return [
            Message(
                role=MessageRole.SYSTEM,
                content="You are helpful.",
                timestamp=datetime.now(timezone.utc),
            ),
            Message(
                role=MessageRole.USER,
                content="Hello",
                timestamp=datetime.now(timezone.utc),
            ),
        ]

    def test_adapter_initialization(self, prism_adapter):
        """Test that adapter initializes with correct config."""
        assert prism_adapter._model_path == "/fake/models/test.gguf"
        assert prism_adapter._binary_path == "/fake/bin/llama-server"
        assert prism_adapter._port == 8081
        assert prism_adapter._host == "127.0.0.1"

    def test_model_name_property(self, prism_adapter):
        """Test model_name returns basename without .gguf."""
        assert prism_adapter.model_name == "test"

    def test_is_local_property(self, prism_adapter):
        """Test is_local returns True."""
        assert prism_adapter.is_local is True

    def test_cost_per_token_property(self, prism_adapter):
        """Test cost_per_token is 0.0 for local model."""
        assert prism_adapter.cost_per_token == 0.0

    def test_messages_to_openai_format(self, prism_adapter, mock_messages):
        """Test message format conversion."""
        result = prism_adapter._messages_to_openai_format(mock_messages)
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1] == {"role": "user", "content": "Hello"}

    @patch("adapters.prism_llama.os.path.exists", return_value=False)
    @pytest.mark.asyncio
    async def test_ensure_server_raises_if_binary_missing(
        self, mock_exists, prism_adapter
    ):
        """Test FileNotFoundError when binary doesn't exist."""
        with pytest.raises(FileNotFoundError, match="binary not found"):
            await prism_adapter._ensure_server()

    @patch("adapters.prism_llama.os.path.exists", side_effect=[True, False])
    @pytest.mark.asyncio
    async def test_ensure_server_raises_if_model_missing(
        self, mock_exists, prism_adapter
    ):
        """Test FileNotFoundError when model doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Model file not found"):
            await prism_adapter._ensure_server()

    @patch("adapters.prism_llama.os.path.exists", return_value=True)
    @patch("adapters.prism_llama.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_ensure_server_launches_subprocess(
        self, mock_exec, mock_exists, prism_adapter
    ):
        """Test that _ensure_server calls create_subprocess_exec with correct args."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_exec.return_value = mock_process

        # Mock health check to succeed immediately
        async def mock_get(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        with patch("adapters.prism_llama.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.get = mock_get
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            await prism_adapter._ensure_server()

        # Verify subprocess was launched
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert "/fake/bin/llama-server" in args
        assert "--model" in args
        assert "/fake/models/test.gguf" in args

    @patch("adapters.prism_llama.os.path.exists", return_value=True)
    @patch("adapters.prism_llama.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_wait_for_health_raises_on_subprocess_exit(
        self, mock_exec, mock_exists, prism_adapter
    ):
        """Test RuntimeError when subprocess exits during startup."""
        mock_process = AsyncMock()
        mock_process.returncode = 1  # exited
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"binary crashed")
        mock_exec.return_value = mock_process

        with pytest.raises(RuntimeError, match="exited during startup"):
            await prism_adapter._ensure_server()

    @patch("adapters.prism_llama.os.path.exists", return_value=True)
    @patch("adapters.prism_llama.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_generate_calls_openai_api(
        self, mock_exec, mock_exists, prism_adapter, mock_messages
    ):
        """Test that generate() calls /v1/chat/completions."""
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_exec.return_value = mock_process

        # Mock health check + generate
        async def mock_get(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        async def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "choices": [
                        {"message": {"content": "Hi there"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                }
            )
            return mock_response

        with patch("adapters.prism_llama.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.get = mock_get
            mock_client_instance.post = mock_post
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            result = await prism_adapter.generate(mock_messages)

        # Verify post was called with correct payload
        assert result.content == "Hi there"

    @patch("adapters.prism_llama.os.path.exists", return_value=True)
    @patch("adapters.prism_llama.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_generate_returns_llm_response(
        self, mock_exec, mock_exists, prism_adapter, mock_messages
    ):
        """Test generate() returns LLMResponse with content and tokens."""
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_exec.return_value = mock_process

        # Mock health check + generate
        async def mock_get(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        async def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "choices": [
                        {"message": {"content": "Hi there"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                }
            )
            return mock_response

        with patch("adapters.prism_llama.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.get = mock_get
            mock_client_instance.post = mock_post
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            result = await prism_adapter.generate(mock_messages)

        assert result.content == "Hi there"
        assert result.tokens_used == 8
        assert result.model == "test"

    @patch("adapters.prism_llama.os.path.exists", return_value=True)
    @patch("adapters.prism_llama.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_generate_handles_api_error(
        self, mock_exec, mock_exists, prism_adapter, mock_messages
    ):
        """Test generate() returns error LLMResponse on HTTP 500."""
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_exec.return_value = mock_process

        # Mock health check + generate error
        async def mock_get(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        async def mock_post(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "500 error",
                request=MagicMock(),
                response=MagicMock(status_code=500, text=b"Internal error"),
            )

        with patch("adapters.prism_llama.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_instance.get = mock_get
            mock_client_instance.post = mock_post
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client_instance

            result = await prism_adapter.generate(mock_messages)

        assert result.content == ""
        assert result.tokens_used == 0

    @pytest.mark.asyncio
    async def test_close_terminates_subprocess(self, prism_adapter):
        """Test close() sends SIGTERM and waits."""
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.terminate = MagicMock()

        async def mock_wait():
            return None

        mock_process.wait = mock_wait
        prism_adapter._process = mock_process
        prism_adapter._client = AsyncMock()
        prism_adapter._client.aclose = AsyncMock()

        await prism_adapter.close()

        mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_force_kills_on_timeout(self, prism_adapter):
        """Test close() sends SIGKILL if SIGTERM times out."""
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.terminate = MagicMock()

        call_count = [0]

        async def mock_wait():
            call_count[0] += 1
            if call_count[0] == 1:
                raise asyncio.TimeoutError
            return None

        mock_process.wait = mock_wait
        mock_process.kill = MagicMock()
        prism_adapter._process = mock_process
        prism_adapter._client = AsyncMock()
        prism_adapter._client.aclose = AsyncMock()

        await prism_adapter.close()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_not_started(self, prism_adapter):
        """Test health_check() returns False before _ensure_server."""
        assert await prism_adapter.health_check() is False

    def test_adapter_implements_interface(self, prism_adapter):
        """Test PrismLlamaAdapter implements LLMAdapter interface."""
        from core.worker_base import LLMAdapter

        assert isinstance(prism_adapter, LLMAdapter)

    def test_extra_args_passed_to_subprocess(self):
        """Test that extra_args are included in subprocess launch."""
        adapter = PrismLlamaAdapter(
            model_path="/fake/test.gguf",
            binary_path="/fake/llama-server",
            extra_args=["--mlock", "--no-mmap"],
        )
        assert "--mlock" in adapter._extra_args
        assert "--no-mmap" in adapter._extra_args
