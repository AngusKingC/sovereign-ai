"""
PrismLlama adapter — adapter-managed llama-server subprocess.

Single responsibility: Manage a modified llama-server binary lifecycle
and expose it as an LLMAdapter via its OpenAI-compatible HTTP API.

Supports quantization formats not in stock llama-cpp-python (e.g., Q1_0
ternary weights from PrismML's fork). The user provides the binary and
model paths; this adapter does NOT download them. See AR20.
"""

import asyncio
import logging
import os
import socket
import time

import httpx

from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)
from core.schemas import Message
from core.worker_base import LLMAdapter, LLMResponse

logger = logging.getLogger(__name__)


class PrismLlamaAdapter(LLMAdapter):
    """Adapter for modified llama.cpp builds via llama-server subprocess.

    The user provides paths to:
    - binary_path: A modified llama-server executable (e.g., PrismML's fork)
    - model_path: A .gguf model file the binary can load

    The adapter does NOT download either. If they're missing at runtime,
    FileNotFoundError is raised with a clear message.
    """

    def __init__(
        self,
        model_path: str,
        binary_path: str = "llama-server",
        port: int = 8081,
        host: str = "127.0.0.1",
        n_gpu_layers: int = -1,
        n_threads: int = 4,
        context_size: int = 4096,
        temperature: float = 0.1,
        emitter: TraceEmitter | None = None,
        startup_timeout: int = 60,
        extra_args: list[str] | None = None,
    ) -> None:
        """Initialize the PrismLlamaAdapter.

        Args:
            model_path: Path to the .gguf model file (user-provided)
            binary_path: Path to the modified llama-server executable (user-provided)
            port: Port for the local HTTP server (default: 8081)
            host: Host to bind (default: 127.0.0.1 — localhost only)
            n_gpu_layers: GPU layers to offload (-1 = all, 0 = CPU only)
            n_threads: CPU threads
            context_size: Context window size (default: 4096)
            temperature: Sampling temperature
            emitter: Trace emitter
            startup_timeout: Seconds to wait for server health check (overridable via PRISM_STARTUP_TIMEOUT env var)
            extra_args: Additional CLI args to pass to llama-server (e.g., ["--mlock"])
        """
        self._model_path = model_path
        self._binary_path = binary_path
        self._port = port
        self._host = host
        self._n_gpu_layers = n_gpu_layers
        self._n_threads = n_threads
        self._context_size = context_size
        self._temperature = temperature
        self._emitter = emitter or MemoryTraceEmitter()
        self._startup_timeout = startup_timeout
        self._extra_args = extra_args or []
        self._model_name = os.path.basename(model_path).replace(".gguf", "")
        self._process: asyncio.subprocess.Process | None = None
        self._client: httpx.AsyncClient | None = None
        self._cost_per_token = 0.0  # local model — no API cost

    @property
    def model_name(self) -> str:
        """Name of the model this adapter uses."""
        return self._model_name

    @property
    def cost_per_token(self) -> float:
        """Cost per token — 0.0 for local models (no API cost)."""
        return self._cost_per_token

    @property
    def is_local(self) -> bool:
        """True — this adapter always runs locally."""
        return True

    async def _ensure_server(self) -> None:
        """Launch llama-server subprocess if not running, wait for health check.

        Raises:
            FileNotFoundError: If binary_path or model_path doesn't exist.
            RuntimeError: If the subprocess exits during startup.
            TimeoutError: If the server doesn't become healthy within timeout.
        """
        if self._process is not None and self._process.returncode is None:
            return  # already running

        # Validate paths — user must provide both
        if not os.path.exists(self._binary_path):
            raise FileNotFoundError(
                f"Modified llama-server binary not found at {self._binary_path}. "
                f"Install the binary (e.g., PrismML's fork) and provide its path via binary_path. "
                f"This adapter does NOT download binaries — see AR20."
            )

        if not os.path.exists(self._model_path):
            raise FileNotFoundError(
                f"Model file not found at {self._model_path}. "
                f"Provide a .gguf model path via model_path. "
                f"This adapter does NOT download models — see AR20."
            )

        # Find available port if default is taken
        port = self._find_available_port()

        # Launch llama-server
        cmd = [
            self._binary_path,
            "--model",
            self._model_path,
            "--host",
            self._host,
            "--port",
            str(port),
            "--n-gpu-layers",
            str(self._n_gpu_layers),
            "--threads",
            str(self._n_threads),
            "--ctx-size",
            str(self._context_size),
            "--verbosity",
            "warning",
            *self._extra_args,
        ]

        # AR18: subprocess launch failure is logged, re-raised so caller knows
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as e:
            logger.error("AR18: llama-server launch failed: %s", e, exc_info=True)
            raise

        # Health check — wait for /health endpoint
        await self._wait_for_health(port)

        # Initialize HTTP client
        self._client = httpx.AsyncClient(
            base_url=f"http://{self._host}:{port}",
            timeout=120.0,  # long timeout for inference
        )

    def _find_available_port(self) -> int:
        """Find an available port if the default is taken."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((self._host, self._port))
                return self._port
            except OSError:
                # Port taken — let OS assign
                s.bind((self._host, 0))
                return s.getsockname()[1]

    async def _wait_for_health(self, port: int) -> None:
        """Wait for llama-server /health endpoint to return 200.

        Timeout is configurable via PRISM_STARTUP_TIMEOUT env var (default: 60s).
        For large models on HDD, user can set PRISM_STARTUP_TIMEOUT=120 or higher.
        """
        url = f"http://{self._host}:{port}/health"
        timeout_seconds = int(
            os.getenv("PRISM_STARTUP_TIMEOUT", str(self._startup_timeout))
        )
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            # AR18: subprocess may have crashed during startup
            if self._process is not None and self._process.returncode is not None:
                stderr = ""
                if self._process.stderr:
                    stderr = (await self._process.stderr.read()).decode(
                        "utf-8", errors="replace"
                    )
                raise RuntimeError(
                    f"llama-server exited during startup. stderr: {stderr}"
                )

            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass  # server not ready yet

            await asyncio.sleep(0.5)

        raise TimeoutError(
            f"llama-server did not become healthy within {timeout_seconds}s. "
            f"Set PRISM_STARTUP_TIMEOUT env var higher if loading a large model."
        )

    def _messages_to_openai_format(
        self, messages: list[Message]
    ) -> list[dict[str, str]]:
        """Convert Sovereign AI messages to OpenAI chat format."""
        return [{"role": msg.role.value, "content": msg.content} for msg in messages]

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Generate a response from the model."""
        start_time = time.perf_counter()

        await self._ensure_server()

        if self._client is None:
            raise RuntimeError("HTTP client failed to initialize")

        try:
            response = await self._client.post(
                "/v1/chat/completions",
                json={
                    "model": self._model_name,
                    "messages": self._messages_to_openai_format(messages),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
            )
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens_in = data.get("usage", {}).get("prompt_tokens", 0)
            tokens_out = data.get("usage", {}).get("completion_tokens", 0)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit trace
            try:
                await self._emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="PrismLlamaAdapter generate completed",
                        data={
                            "model": self._model_name,
                            "tokens_in": tokens_in,
                            "tokens_out": tokens_out,
                            "duration_ms": duration_ms,
                            "cost_usd": 0.0,  # local model
                        },
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                # AR18: trace emission failure is non-critical
                pass

            return LLMResponse(
                content=content,
                raw={"model": self._model_name, "usage": data.get("usage", {})},
                model=self._model_name,
                tokens_used=tokens_in + tokens_out,
                duration_ms=duration_ms,
            )

        except httpx.HTTPStatusError as e:
            # AR18: API error — return error response, don't crash adapter
            logger.error("AR18: PrismLlama API error: %s", e, exc_info=True)
            return LLMResponse(
                content="",
                raw={"error": str(e)},
                model=self._model_name,
                tokens_used=0,
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )

    async def health_check(self) -> bool:
        """Check if the server is running and healthy."""
        if self._process is None or self._process.returncode is not None:
            return False
        if self._client is None:
            return False
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except Exception:
            # AR18: health check failure means server isn't ready
            return False

    async def close(self) -> None:
        """Gracefully shut down the llama-server subprocess."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

        if self._process is not None and self._process.returncode is None:
            # AR18: graceful shutdown, but don't hang if process won't exit
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                # AR18: process didn't exit on SIGTERM — force kill
                logger.warning("AR18: llama-server didn't exit on SIGTERM, killing")
                self._process.kill()
                await self._process.wait()
            except Exception as e:
                # AR18: cleanup failure logged, don't raise
                logger.error("AR18: llama-server cleanup failed: %s", e, exc_info=True)
            self._process = None

    async def __aenter__(self) -> "PrismLlamaAdapter":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
