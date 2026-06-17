"""Tests for system/profiler.py"""

import pytest

from core.schemas import CPUInfo, GPUInfo, RAMInfo, StorageInfo, OSInfo, NetworkInfo, OllamaInfo
from core.observability import MemoryTraceEmitter, NullTraceEmitter
from system.profiler import SystemProfiler
from core.memory_router import MemoryRouter

pytestmark = pytest.mark.asyncio


class TestSystemProfiler:
    """Test cases for SystemProfiler."""

    @pytest.fixture
    def memory_router(self):
        """Create a mock memory router."""
        from unittest.mock import AsyncMock
        router = AsyncMock(spec=MemoryRouter)
        router.write = AsyncMock()
        return router

    @pytest.fixture
    def profiler(self, memory_router):
        """Create a SystemProfiler instance."""
        return SystemProfiler(memory_router=memory_router, emitter=MemoryTraceEmitter())

    async def test_detect_cpu_returns_cpu_info(self, profiler):
        """Test that CPU detection returns CPUInfo."""
        cpu_info = await profiler._detect_cpu()
        assert isinstance(cpu_info, CPUInfo)

    async def test_detect_ram_returns_ram_info(self, profiler):
        """Test that RAM detection returns RAMInfo."""
        ram_info = await profiler._detect_ram()
        assert isinstance(ram_info, RAMInfo)

    async def test_detect_storage_returns_storage_info_list(self, profiler):
        """Test that storage detection returns list of StorageInfo."""
        storage_info = await profiler._detect_storage()
        assert isinstance(storage_info, list)
        for info in storage_info:
            assert isinstance(info, StorageInfo)

    async def test_detect_os_returns_os_info(self, profiler):
        """Test that OS detection returns OSInfo."""
        os_info = await profiler._detect_os()
        assert isinstance(os_info, OSInfo)

    async def test_detect_network_returns_network_info(self, profiler):
        """Test that network detection returns NetworkInfo."""
        network_info = await profiler._detect_network()
        assert isinstance(network_info, NetworkInfo)

    async def test_detect_ollama_returns_ollama_info(self, profiler):
        """Test that Ollama detection returns OllamaInfo."""
        ollama_info = await profiler._detect_ollama()
        assert isinstance(ollama_info, OllamaInfo)

    async def test_profile_returns_complete_system_profile(self, profiler):
        """Test that profile returns complete SystemProfile."""
        profile = await profiler.profile()
        assert profile.gpu is not None
        assert profile.cpu is not None
        assert profile.ram is not None
        assert profile.storage is not None
        assert profile.os is not None
        assert profile.network is not None
        assert profile.ollama is not None

    async def test_profile_caches_result(self, profiler):
        """Test that profile caches the result."""
        profile1 = await profiler.profile()
        profile2 = await profiler.get_cached()
        assert profile1 is profile2

    async def test_refresh_reruns_detection(self, profiler):
        """Test that refresh re-runs detection."""
        profile1 = await profiler.profile()
        profile2 = await profiler.refresh()
        # Should be a new profile object
        assert profile1 is not profile2

    async def test_get_cached_returns_none_before_first_profile(self, profiler):
        """Test that get_cached returns None before first profile."""
        cached = await profiler.get_cached()
        assert cached is None
