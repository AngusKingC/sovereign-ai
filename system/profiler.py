"""
System Profiler - Hardware and Software Environment Detection

Single responsibility: Detect and profile the full hardware and software environment
including GPU, CPU, RAM, storage, OS, network, and Ollama service status.
"""

import asyncio
import platform
from datetime import datetime
from typing import TYPE_CHECKING

import httpx

from core.schemas import (
    CPUInfo,
    GPUInfo,
    NetworkInfo,
    OllamaInfo,
    OllamaModelInfo,
    OSInfo,
    RAMInfo,
    StorageInfo,
    SystemProfile,
)
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEmitter,
    NullTraceEmitter,
    TraceEvent,
)

if TYPE_CHECKING:
    from core.memory_router import MemoryRouter


class SystemProfiler:
    """Persistent system profiler for hardware and software environment detection."""

    def __init__(self, memory_router: "MemoryRouter", emitter: TraceEmitter | None = None) -> None:
        """Initialize the system profiler with memory router for persistence."""
        self.memory_router = memory_router
        self.emitter = emitter or NullTraceEmitter()
        self._cached_profile: SystemProfile | None = None

    async def _detect_gpu(self) -> GPUInfo:
        """Detect GPU information using pynvml if available."""
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_vram_mb = int(memory_info.total / 1024 / 1024)
            available_vram_mb = int(memory_info.free / 1024 / 1024)
            
            driver_version = pynvml.nvmlSystemGetDriverVersion()
            
            pynvml.nvmlShutdown()
            
            return GPUInfo(
                model_name=name,
                total_vram_mb=total_vram_mb,
                available_vram_mb=available_vram_mb,
                cuda_support=True,
                rocm_support=False,
                metal_support=False,
                driver_version=driver_version,
            )
        except ImportError:
            # pynvml not available
            return GPUInfo()
        except Exception as e:
            # NVML detection failed
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="GPU detection failed",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                    )
                )
            except Exception:
                pass
            return GPUInfo()

    async def _detect_cpu(self) -> CPUInfo:
        """Detect CPU information using psutil."""
        try:
            import psutil

            loop = asyncio.get_event_loop()

            def get_cpu_info() -> tuple:
                return (
                    platform.processor() or "unknown",
                    psutil.cpu_count(logical=False),
                    psutil.cpu_count(logical=True),
                    platform.machine() or "unknown",
                    psutil.cpu_freq().max if psutil.cpu_freq() else 0.0,
                )

            model_name, physical_cores, logical_threads, architecture, base_clock_ghz = await loop.run_in_executor(None, get_cpu_info)

            return CPUInfo(
                model_name=model_name,
                physical_cores=physical_cores,
                logical_threads=logical_threads,
                architecture=architecture,
                base_clock_ghz=base_clock_ghz,
            )
        except ImportError:
            return CPUInfo()
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="CPU detection failed",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                    )
                )
            except Exception:
                pass
            return CPUInfo()

    async def _detect_ram(self) -> RAMInfo:
        """Detect RAM information using psutil."""
        try:
            import psutil

            loop = asyncio.get_event_loop()

            def get_ram_info() -> tuple:
                mem = psutil.virtual_memory()
                return (
                    int(mem.total / 1024 / 1024),
                    int(mem.available / 1024 / 1024),
                    mem.percent,
                )

            total_mb, available_mb, usage_percent = await loop.run_in_executor(None, get_ram_info)

            return RAMInfo(
                total_mb=total_mb,
                available_mb=available_mb,
                usage_percent=usage_percent,
            )
        except ImportError:
            return RAMInfo()
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="RAM detection failed",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                    )
                )
            except Exception:
                pass
            return RAMInfo()

    async def _detect_storage(self) -> list[StorageInfo]:
        """Detect storage partition information using psutil."""
        storage_info = []
        try:
            import psutil

            loop = asyncio.get_event_loop()

            def get_partitions() -> list:
                return list(psutil.disk_partitions())

            partitions = await loop.run_in_executor(None, get_partitions)

            for partition in partitions:
                try:
                    def get_usage(mountpoint: str) -> tuple:
                        usage = psutil.disk_usage(mountpoint)
                        return (
                            int(usage.total / 1024 / 1024),
                            int(usage.free / 1024 / 1024),
                        )

                    total_mb, available_mb = await loop.run_in_executor(None, get_usage, partition.mountpoint)

                    storage_info.append(
                        StorageInfo(
                            mount_point=partition.mountpoint,
                            total_mb=total_mb,
                            available_mb=available_mb,
                            filesystem_type=partition.fstype,
                        )
                    )
                except Exception:
                    # Skip partitions that can't be accessed
                    pass
        except ImportError:
            pass
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Storage detection failed",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                    )
                )
            except Exception:
                pass
        return storage_info

    async def _detect_os(self) -> OSInfo:
        """Detect operating system information."""
        try:
            import shutil

            docker_available = shutil.which("docker") is not None
        except Exception:
            docker_available = False

        # Check for NVIDIA drivers
        nvidia_drivers_present = False
        try:
            import shutil

            nvidia_drivers_present = shutil.which("nvidia-smi") is not None
        except Exception:
            pass

        return OSInfo(
            name=platform.system(),
            version=platform.version(),
            kernel_build=platform.release(),
            python_version=platform.python_version(),
            docker_available=docker_available,
            nvidia_drivers_present=nvidia_drivers_present,
        )

    async def _detect_network(self) -> NetworkInfo:
        """Detect network connectivity with lightweight check."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("https://www.google.com")
                if response.status_code == 200:
                    # Simple bandwidth estimation based on response time
                    if response.elapsed.total_seconds() < 0.5:
                        bandwidth = "high"
                    elif response.elapsed.total_seconds() < 2.0:
                        bandwidth = "medium"
                    else:
                        bandwidth = "low"
                    return NetworkInfo(internet_available=True, bandwidth_category=bandwidth)
        except Exception:
            pass
        return NetworkInfo(internet_available=False, bandwidth_category="none")

    async def _detect_ollama(self) -> OllamaInfo:
        """Detect Ollama service and query available models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check if Ollama is running
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    
                    model_infos = []
                    models_loaded = []
                    
                    for model in models:
                        model_name = model.get("name", "unknown")
                        size_mb = model.get("size", 0) // (1024 * 1024)
                        
                        # Check if model is loaded (has details field)
                        if "details" in model:
                            models_loaded.append(model_name)
                        
                        model_infos.append(
                            OllamaModelInfo(
                                name=model_name,
                                size_on_disk_mb=size_mb,
                                loaded_in_vram=model_name in models_loaded,
                            )
                        )
                    
                    return OllamaInfo(
                        running=True,
                        models_downloaded=model_infos,
                        models_loaded=models_loaded,
                    )
        except Exception:
            pass
        return OllamaInfo(running=False)

    async def profile(self) -> SystemProfile:
        """Run full detection and return complete system profile."""
        await self.emitter.emit(
            TraceEvent(
                event_type=TraceEventType.OPERATION_START,
                component=TraceComponent.SYSTEM,
                message="System profiling started",
                level=TraceLevel.INFO,
            )
        )

        try:
            # Run all detections in parallel for speed
            gpu, cpu, ram, storage, os, network, ollama = await asyncio.gather(
                self._detect_gpu(),
                self._detect_cpu(),
                self._detect_ram(),
                self._detect_storage(),
                self._detect_os(),
                self._detect_network(),
                self._detect_ollama(),
                return_exceptions=True,
            )

            # Handle exceptions from individual detections
            gpu = gpu if isinstance(gpu, GPUInfo) else GPUInfo()
            cpu = cpu if isinstance(cpu, CPUInfo) else CPUInfo()
            ram = ram if isinstance(ram, RAMInfo) else RAMInfo()
            storage = storage if isinstance(storage, list) else []
            os = os if isinstance(os, OSInfo) else OSInfo()
            network = network if isinstance(network, NetworkInfo) else NetworkInfo()
            ollama = ollama if isinstance(ollama, OllamaInfo) else OllamaInfo()

            profile = SystemProfile(
                gpu=gpu,
                cpu=cpu,
                ram=ram,
                storage=storage,
                os=os,
                network=network,
                ollama=ollama,
                profiled_at=datetime.now(),
            )

            self._cached_profile = profile

            # Store to memory backends
            await self._store_profile(profile)

            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message="System profiling completed",
                    level=TraceLevel.INFO,
                    data={
                        "gpu_model": profile.gpu.model_name,
                        "cpu_cores": profile.cpu.physical_cores,
                        "ram_total_mb": profile.ram.total_mb,
                        "ollama_running": profile.ollama.running,
                    },
                )
            )

            return profile
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="System profiling failed",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                pass
            raise

    async def refresh(self) -> SystemProfile:
        """Re-run detection and update stored profile."""
        return await self.profile()

    async def get_cached(self) -> SystemProfile | None:
        """Return last stored profile without re-detecting."""
        return self._cached_profile

    async def _store_profile(self, profile: SystemProfile) -> None:
        """Store profile to Postgres and Obsidian backends."""
        try:
            # Store to Postgres
            await self.memory_router.write(
                {
                    "content": profile.model_dump_json(),
                    "task_id": "system_profile",
                    "metadata": {"type": "system_profile"},
                }
            )
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to store profile to Postgres",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                    )
                )
            except Exception:
                pass

        try:
            # Store to Obsidian
            await self.memory_router.write(
                {
                    "content": profile.model_dump_json(),
                    "task_id": "system_profile",
                    "metadata": {"type": "system_profile"},
                }
            )
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to store profile to Obsidian",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                    )
                )
            except Exception:
                pass
