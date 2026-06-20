"""Tests for System Profiler."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from core.schemas import SystemProfile, GPUInfo, CPUInfo, RAMInfo, StorageInfo, OSInfo, NetworkInfo, OllamaInfo, OllamaModelInfo
from system.profiler import SystemProfiler
from core.memory_router import MemoryRouter


class MockMemoryRouter(MemoryRouter):
    """Mock MemoryRouter for testing."""
    
    def __init__(self) -> None:
        super().__init__()
        self.writes: list[dict] = []
    
    async def write(self, data: dict) -> None:  # type: ignore[override]
        """Mock write."""
        self.writes.append(data)
    
    async def fetch(self, task_id: str, query: str) -> Mock:  # type: ignore[override]
        """Mock fetch."""
        mock_result = Mock()
        mock_result.data = None
        return mock_result
    
    async def fetch_by_filter(self, filter: dict, collection: str | None = None, limit: int | None = None, filter_func=None) -> list:
        """Mock fetch_by_filter."""
        return []
    
    async def write_to_collection(self, data: dict, collection: str, document_id: str | None = None) -> None:
        """Mock write_to_collection."""
        self.writes.append({"data": data, "collection": collection, "document_id": document_id})
    
    async def get_global_context(self, caller_id: str = "orchestrator") -> None:
        """Mock get_global_context."""
        return None
    
    async def set_global_context(self, context: dict, caller_id: str = "orchestrator") -> None:
        """Mock set_global_context."""
        pass


@pytest.mark.asyncio
class TestSystemProfiler:
    """Tests for SystemProfiler."""
    
    async def test_system_profile_schema_validation(self) -> None:
        """Test that SystemProfile schema validates correctly."""
        profile = SystemProfile(
            gpu=GPUInfo(model_name="RTX 4090", total_vram_mb=24576, available_vram_mb=24576),
            cpu=CPUInfo(model_name="Intel i9", physical_cores=16, logical_threads=32),
            ram=RAMInfo(total_mb=32768, available_mb=16384, usage_percent=50.0),
            storage=[StorageInfo(mount_point="/", total_mb=1000000, available_mb=500000)],
            os=OSInfo(name="Linux", version="5.15", python_version="3.11"),
            network=NetworkInfo(internet_available=True, bandwidth_category="high"),
            ollama=OllamaInfo(running=True, models_downloaded=[OllamaModelInfo(name="llama2")]),
        )
        
        assert profile.gpu.model_name == "RTX 4090"
        assert profile.cpu.physical_cores == 16
        assert profile.ram.total_mb == 32768
        assert len(profile.storage) == 1
        assert profile.os.name == "Linux"
        assert profile.network.internet_available is True
        assert profile.ollama.running is True
    
    async def test_profiler_returns_complete_system_profile(self) -> None:
        """Test that profiler returns a complete SystemProfile."""
        mock_router = MockMemoryRouter()
        profiler = SystemProfiler(mock_router)
        
        with patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.cpu_freq') as mock_cpu_freq, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_partitions') as mock_disk_partitions, \
             patch('pynvml.nvmlInit') as mock_nvml_init, \
             patch('pynvml.nvmlDeviceGetHandleByIndex') as mock_nvml_device, \
             patch('pynvml.nvmlDeviceGetName') as mock_nvml_name, \
             patch('pynvml.nvmlDeviceGetMemoryInfo') as mock_nvml_memory, \
             patch('pynvml.nvmlSystemGetDriverVersion') as mock_nvml_driver, \
             patch('pynvml.nvmlShutdown') as mock_nvml_shutdown, \
             patch('platform.processor') as mock_processor, \
             patch('platform.machine') as mock_machine, \
             patch('platform.system') as mock_system, \
             patch('platform.version') as mock_version, \
             patch('platform.release') as mock_release, \
             patch('platform.python_version') as mock_python_version, \
             patch('httpx.AsyncClient') as mock_httpx:
            
            # Mock psutil
            mock_cpu_count.return_value = 8
            mock_cpu_freq.return_value = MagicMock(max=3.5)
            mock_virtual_memory.return_value = MagicMock(total=16*1024*1024*1024, available=8*1024*1024*1024, percent=50.0)
            mock_disk_partitions.return_value = []
            
            # Mock pynvml
            mock_nvml_name.return_value = "RTX 4090"
            mock_nvml_memory.return_value = MagicMock(total=24*1024*1024*1024, free=24*1024*1024*1024)
            mock_nvml_driver.return_value = "535.104"
            
            # Mock platform
            mock_processor.return_value = "Intel i9"
            mock_machine.return_value = "x86_64"
            mock_system.return_value = "Linux"
            mock_version.return_value = "5.15.0"
            mock_release.return_value = "5.15.0-76-generic"
            mock_python_version.return_value = "3.11.9"
            
            # Mock httpx for network and Ollama
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed = MagicMock(total_seconds=lambda: 0.3)
            mock_response.json.return_value = {"models": []}
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            profile = await profiler.profile()
            
            assert isinstance(profile, SystemProfile)
            assert profile.gpu.model_name == "RTX 4090"
            assert profile.cpu.physical_cores == 8
            assert profile.ram.total_mb > 0
    
    async def test_graceful_handling_when_ollama_not_running(self) -> None:
        """Test graceful handling when Ollama is not running."""
        mock_router = MockMemoryRouter()
        profiler = SystemProfiler(mock_router)
        
        with patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.cpu_freq') as mock_cpu_freq, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_partitions') as mock_disk_partitions, \
             patch('pynvml.nvmlInit', side_effect=ImportError), \
             patch('platform.processor') as mock_processor, \
             patch('platform.machine') as mock_machine, \
             patch('platform.system') as mock_system, \
             patch('platform.version') as mock_version, \
             patch('platform.release') as mock_release, \
             patch('platform.python_version') as mock_python_version, \
             patch('httpx.AsyncClient') as mock_httpx:
            
            # Mock psutil
            mock_cpu_count.return_value = 8
            mock_cpu_freq.return_value = None
            mock_virtual_memory.return_value = MagicMock(total=16*1024*1024*1024, available=8*1024*1024*1024, percent=50.0)
            mock_disk_partitions.return_value = []
            
            # Mock platform
            mock_processor.return_value = "Intel i9"
            mock_machine.return_value = "x86_64"
            mock_system.return_value = "Linux"
            mock_version.return_value = "5.15.0"
            mock_release.return_value = "5.15.0-76-generic"
            mock_python_version.return_value = "3.11.9"
            
            # Mock httpx for network (success) and Ollama (failure)
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed = MagicMock(total_seconds=lambda: 0.3)
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[mock_response, Exception("Connection refused")])
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            profile = await profiler.profile()
            
            assert isinstance(profile, SystemProfile)
            assert profile.ollama.running is False
            assert len(profile.ollama.models_downloaded) == 0
    
    async def test_graceful_handling_when_no_nvidia_gpu(self) -> None:
        """Test graceful handling when no NVIDIA GPU is present."""
        mock_router = MockMemoryRouter()
        profiler = SystemProfiler(mock_router)
        
        with patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.cpu_freq') as mock_cpu_freq, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_partitions') as mock_disk_partitions, \
             patch('pynvml.nvmlInit', side_effect=ImportError), \
             patch('platform.processor') as mock_processor, \
             patch('platform.machine') as mock_machine, \
             patch('platform.system') as mock_system, \
             patch('platform.version') as mock_version, \
             patch('platform.release') as mock_release, \
             patch('platform.python_version') as mock_python_version, \
             patch('httpx.AsyncClient') as mock_httpx:
            
            # Mock psutil
            mock_cpu_count.return_value = 8
            mock_cpu_freq.return_value = None
            mock_virtual_memory.return_value = MagicMock(total=16*1024*1024*1024, available=8*1024*1024*1024, percent=50.0)
            mock_disk_partitions.return_value = []
            
            # Mock platform
            mock_processor.return_value = "Intel i9"
            mock_machine.return_value = "x86_64"
            mock_system.return_value = "Linux"
            mock_version.return_value = "5.15.0"
            mock_release.return_value = "5.15.0-76-generic"
            mock_python_version.return_value = "3.11.9"
            
            # Mock httpx
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed = MagicMock(total_seconds=lambda: 0.3)
            mock_response.json.return_value = {"models": []}
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            profile = await profiler.profile()
            
            assert isinstance(profile, SystemProfile)
            assert profile.gpu.model_name == "unknown"
            assert profile.gpu.total_vram_mb == 0
    
    async def test_profile_stored_to_postgres_and_obsidian(self) -> None:
        """Test that profile is stored to Postgres and Obsidian on completion."""
        mock_router = MockMemoryRouter()
        profiler = SystemProfiler(mock_router)
        
        with patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.cpu_freq') as mock_cpu_freq, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_partitions') as mock_disk_partitions, \
             patch('pynvml.nvmlInit', side_effect=ImportError), \
             patch('platform.processor') as mock_processor, \
             patch('platform.machine') as mock_machine, \
             patch('platform.system') as mock_system, \
             patch('platform.version') as mock_version, \
             patch('platform.release') as mock_release, \
             patch('platform.python_version') as mock_python_version, \
             patch('httpx.AsyncClient') as mock_httpx:
            
            # Mock psutil
            mock_cpu_count.return_value = 8
            mock_cpu_freq.return_value = None
            mock_virtual_memory.return_value = MagicMock(total=16*1024*1024*1024, available=8*1024*1024*1024, percent=50.0)
            mock_disk_partitions.return_value = []
            
            # Mock platform
            mock_processor.return_value = "Intel i9"
            mock_machine.return_value = "x86_64"
            mock_system.return_value = "Linux"
            mock_version.return_value = "5.15.0"
            mock_release.return_value = "5.15.0-76-generic"
            mock_python_version.return_value = "3.11.9"
            
            # Mock httpx
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed = MagicMock(total_seconds=lambda: 0.3)
            mock_response.json.return_value = {"models": []}
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            profile = await profiler.profile()
            
            # Verify profile was stored (called twice for Postgres and Obsidian)
            assert len(mock_router.writes) == 2
            assert mock_router.writes[0]["task_id"] == "system_profile"
    
    async def test_cached_profile_returned_without_redetection(self) -> None:
        """Test that cached profile is returned without re-detection."""
        mock_router = MockMemoryRouter()
        profiler = SystemProfiler(mock_router)
        
        # Set a cached profile
        cached = SystemProfile(
            gpu=GPUInfo(model_name="Cached GPU"),
            cpu=CPUInfo(model_name="Cached CPU"),
        )
        profiler._cached_profile = cached
        
        result = await profiler.get_cached()
        
        assert result is cached
        assert result.gpu.model_name == "Cached GPU"
    
    async def test_trace_events_emitted_during_profiling(self) -> None:
        """Test that trace events are emitted during profiling."""
        from core.observability import MemoryTraceEmitter, TraceEventType
        
        mock_router = MockMemoryRouter()
        trace_emitter = MemoryTraceEmitter()
        profiler = SystemProfiler(mock_router, emitter=trace_emitter)
        
        with patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.cpu_freq') as mock_cpu_freq, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_partitions') as mock_disk_partitions, \
             patch('pynvml.nvmlInit', side_effect=ImportError), \
             patch('platform.processor') as mock_processor, \
             patch('platform.machine') as mock_machine, \
             patch('platform.system') as mock_system, \
             patch('platform.version') as mock_version, \
             patch('platform.release') as mock_release, \
             patch('platform.python_version') as mock_python_version, \
             patch('httpx.AsyncClient') as mock_httpx:
            
            # Mock psutil
            mock_cpu_count.return_value = 8
            mock_cpu_freq.return_value = None
            mock_virtual_memory.return_value = MagicMock(total=16*1024*1024*1024, available=8*1024*1024*1024, percent=50.0)
            mock_disk_partitions.return_value = []
            
            # Mock platform
            mock_processor.return_value = "Intel i9"
            mock_machine.return_value = "x86_64"
            mock_system.return_value = "Linux"
            mock_version.return_value = "5.15.0"
            mock_release.return_value = "5.15.0-76-generic"
            mock_python_version.return_value = "3.11.9"
            
            # Mock httpx
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed = MagicMock(total_seconds=lambda: 0.3)
            mock_response.json.return_value = {"models": []}
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            profile = await profiler.profile()
            
            # Verify trace events were emitted
            events = trace_emitter.get_events()
            assert len(events) >= 2
            
            event_types = [str(event.event_type) for event in events]
            assert "operation_start" in event_types
            assert "operation_complete" in event_types
    
    async def test_all_detection_failures_caught_no_exceptions(self) -> None:
        """Test that all detection failures are caught and do not raise exceptions."""
        mock_router = MockMemoryRouter()
        profiler = SystemProfiler(mock_router)
        
        with patch('psutil.cpu_count', side_effect=ImportError), \
             patch('pynvml.nvmlInit', side_effect=ImportError), \
             patch('platform.processor', side_effect=Exception("Platform error")), \
             patch('httpx.AsyncClient', side_effect=ImportError):
            
            # Should not raise exception even if all detections fail
            profile = await profiler.profile()
            
            assert isinstance(profile, SystemProfile)
            # Should have default values
            assert profile.gpu.model_name == "unknown"
            assert profile.cpu.model_name == "unknown"
    
    async def test_refresh_redetects_profile(self) -> None:
        """Test that refresh re-runs detection and updates profile."""
        mock_router = MockMemoryRouter()
        profiler = SystemProfiler(mock_router)
        
        with patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.cpu_freq') as mock_cpu_freq, \
             patch('psutil.virtual_memory') as mock_virtual_memory, \
             patch('psutil.disk_partitions') as mock_disk_partitions, \
             patch('pynvml.nvmlInit', side_effect=ImportError), \
             patch('platform.processor') as mock_processor, \
             patch('platform.machine') as mock_machine, \
             patch('platform.system') as mock_system, \
             patch('platform.version') as mock_version, \
             patch('platform.release') as mock_release, \
             patch('platform.python_version') as mock_python_version, \
             patch('httpx.AsyncClient') as mock_httpx:
            
            # Mock psutil
            mock_cpu_count.return_value = 8
            mock_cpu_freq.return_value = None
            mock_virtual_memory.return_value = MagicMock(total=16*1024*1024*1024, available=8*1024*1024*1024, percent=50.0)
            mock_disk_partitions.return_value = []
            
            # Mock platform
            mock_processor.return_value = "Intel i9"
            mock_machine.return_value = "x86_64"
            mock_system.return_value = "Linux"
            mock_version.return_value = "5.15.0"
            mock_release.return_value = "5.15.0-76-generic"
            mock_python_version.return_value = "3.11.9"
            
            # Mock httpx
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed = MagicMock(total_seconds=lambda: 0.3)
            mock_response.json.return_value = {"models": []}
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()
            
            profile1 = await profiler.profile()
            profile2 = await profiler.refresh()
            
            # Both should be valid SystemProfile instances
            assert isinstance(profile1, SystemProfile)
            assert isinstance(profile2, SystemProfile)
            # refresh should update the cached profile
            assert profile2 is profiler._cached_profile

