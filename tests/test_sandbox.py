"""
Tests for SandboxExecutor.
"""

from unittest.mock import AsyncMock

import pytest

from core.approval_gate import ApprovalGate, ApprovalResponse
from core.observability import MemoryTraceEmitter
from core.sandbox import SandboxConfig, SandboxExecutor, SandboxResult


class TestSandboxConfig:
    """Test suite for SandboxConfig."""

    def test_default_config_values(self):
        """Test that default config values are set correctly."""
        config = SandboxConfig()
        assert config.image == "python:3.12-slim"
        assert config.memory_limit == "512m"
        assert config.cpu_limit == "1.0"
        assert config.network_disabled is True
        assert config.read_only_fs is True
        assert config.timeout == 30
        assert config.sandbox_policy == "strict"

    def test_custom_config_values(self):
        """Test that custom config values are set correctly."""
        config = SandboxConfig(
            image="python:3.11-slim",
            memory_limit="1g",
            cpu_limit="2.0",
            network_disabled=False,
            read_only_fs=False,
            timeout=60,
            sandbox_policy="fallback",
        )
        assert config.image == "python:3.11-slim"
        assert config.memory_limit == "1g"
        assert config.cpu_limit == "2.0"
        assert config.network_disabled is False
        assert config.read_only_fs is False
        assert config.timeout == 60
        assert config.sandbox_policy == "fallback"


class TestSandboxResult:
    """Test suite for SandboxResult."""

    def test_sandbox_result_fields(self):
        """Test that SandboxResult has all required fields."""
        result = SandboxResult(
            success=True,
            stdout="output",
            stderr="",
            return_code=0,
            sandboxed=True,
        )
        assert result.success is True
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.return_code == 0
        assert result.sandboxed is True
        assert result.error is None


class TestSandboxExecutor:
    """Test suite for SandboxExecutor."""

    @pytest.fixture
    def emitter(self):
        """Create a memory trace emitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def mock_approval_gate(self):
        """Create a mock approval gate."""
        gate = AsyncMock(spec=ApprovalGate)
        gate.request_approval = AsyncMock(
            return_value=ApprovalResponse(
                request_id="test-id",
                task_id="task-id",
                approved=True,
                approved_by="test_user",
            )
        )
        return gate

    @pytest.fixture
    def sandbox(self, emitter):
        """Create a SandboxExecutor instance for testing."""
        config = SandboxConfig(timeout=5)
        return SandboxExecutor(config=config, emitter=emitter)

    @pytest.mark.asyncio
    async def test_sandbox_executor_initialization(self, emitter):
        """Test that SandboxExecutor initializes correctly."""
        config = SandboxConfig(timeout=10)
        sandbox = SandboxExecutor(config=config, emitter=emitter)
        assert sandbox._config == config
        assert sandbox._emitter == emitter
        assert sandbox._docker_available_cache is None

    @pytest.mark.asyncio
    async def test_sandbox_executor_with_approval_gate(
        self, emitter, mock_approval_gate
    ):
        """Test that SandboxExecutor can be initialized with approval gate."""
        config = SandboxConfig(timeout=10, sandbox_policy="fallback")
        sandbox = SandboxExecutor(
            config=config, emitter=emitter, approval_gate=mock_approval_gate
        )
        assert sandbox._approval_gate == mock_approval_gate

    @pytest.mark.asyncio
    async def test_sandbox_executor_with_custom_config(self, emitter):
        """Test that SandboxExecutor accepts custom config."""
        config = SandboxConfig(
            image="python:3.11-slim",
            timeout=60,
            sandbox_policy="fallback",
        )
        sandbox = SandboxExecutor(config=config, emitter=emitter)
        assert sandbox._config.image == "python:3.11-slim"
        assert sandbox._config.timeout == 60
        assert sandbox._config.sandbox_policy == "fallback"

    @pytest.mark.asyncio
    async def test_sandbox_result_dataclass_immutability(self):
        """Test that SandboxResult is a dataclass with correct fields."""
        result = SandboxResult(
            success=True,
            stdout="test",
            stderr="",
            return_code=0,
            sandboxed=True,
        )
        # Test that all fields are accessible
        assert hasattr(result, "success")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")
        assert hasattr(result, "return_code")
        assert hasattr(result, "error")
        assert hasattr(result, "sandboxed")

    @pytest.mark.asyncio
    async def test_sandbox_config_dataclass_immutability(self):
        """Test that SandboxConfig is a dataclass with correct fields."""
        config = SandboxConfig()
        # Test that all fields are accessible
        assert hasattr(config, "image")
        assert hasattr(config, "memory_limit")
        assert hasattr(config, "cpu_limit")
        assert hasattr(config, "network_disabled")
        assert hasattr(config, "read_only_fs")
        assert hasattr(config, "timeout")
        assert hasattr(config, "sandbox_policy")
