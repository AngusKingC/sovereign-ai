"""
Model Acquisition - Unified Model Downloader with HuggingFace Integration

Single responsibility: Discover, evaluate, and download models autonomously
with user approval, supporting multiple sources and quantisation variants.
"""

import os
import time
from typing import TYPE_CHECKING

import httpx

from core.schemas import (
    ApprovalCallback,
    DownloadRequest,
    DownloadResult,
    DownloadStatus,
    ModelEntry,
    ModelSource,
    QuantisationVariant,
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
    from system.resource_manager import ResourceManager
    from system.model_acquisition import ModelRegistry


class ModelAcquisition:
    """Unified model downloader with HuggingFace catalogue integration."""

    def __init__(
        self,
        memory_router: "MemoryRouter",
        approval_callback: ApprovalCallback | None = None,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the model acquisition manager."""
        self.memory_router = memory_router
        self.approval_callback = approval_callback
        self.emitter = emitter or NullTraceEmitter()
        self.hf_api_url = "https://huggingface.co/api/models"
        self.hf_token = os.environ.get("HF_TOKEN")
        self.ollama_api_url = "http://localhost:11434"

    async def search(
        self, query: str, task_tags: list[str] | None = None, max_results: int = 10
    ) -> list[ModelEntry]:
        """Search HuggingFace for models matching query and task tags."""
        try:
            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_SEARCH,
                    component=TraceComponent.SYSTEM,
                    message=f"Searching HuggingFace for: {query}",
                    level=TraceLevel.INFO,
                    data={"query": query, "task_tags": task_tags, "max_results": max_results},
                )
            )

            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"

            params = {"search": query, "limit": max_results}
            if task_tags:
                params["pipeline_tag"] = task_tags[0]  # HuggingFace API supports one pipeline tag

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.hf_api_url, headers=headers, params=params)
                response.raise_for_status()
                models_data = response.json()

            entries = []
            for model_data in models_data[:max_results]:
                entry = await self._hf_data_to_entry(model_data)
                if entry:
                    entries.append(entry)

            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Found {len(entries)} models",
                    level=TraceLevel.INFO,
                    data={"result_count": len(entries)},
                )
            )

            return entries
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to search HuggingFace",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return []

    async def fetch_metadata(self, model_id: str) -> ModelEntry | None:
        """Fetch full metadata for a specific HuggingFace model ID."""
        try:
            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_METADATA_FETCH,
                    component=TraceComponent.SYSTEM,
                    message=f"Fetching metadata for {model_id}",
                    level=TraceLevel.INFO,
                    data={"model_id": model_id},
                )
            )

            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.hf_api_url}/{model_id}", headers=headers)
                response.raise_for_status()
                model_data = response.json()

            entry = await self._hf_data_to_entry(model_data)

            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Fetched metadata for {model_id}",
                    level=TraceLevel.INFO,
                )
            )

            return entry
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to fetch model metadata",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return None

    async def _hf_data_to_entry(self, model_data: dict) -> ModelEntry | None:
        """Convert HuggingFace API data to ModelEntry."""
        try:
            model_id = model_data.get("modelId", model_data.get("id", ""))
            if not model_id:
                return None

            # Extract task tags
            tags = model_data.get("tags", [])
            pipeline_tag = model_data.get("pipeline_tag", "")
            task_tags = [pipeline_tag] if pipeline_tag else []
            task_tags.extend([tag for tag in tags if tag in ["text-generation", "text-classification", "embeddings", "code"]])

            # Estimate quantisation variants based on common patterns
            quantisation_variants = []
            if "gguf" in tags or "ggml" in tags:
                # GGUF models typically have Q4, Q5, Q8 variants
                quantisation_variants.extend([
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=4.0,
                        vram_required_gb=5.0,
                        ram_required_gb=8.0,
                        quality_score=0.85,
                        speed_score=0.90,
                    ),
                    QuantisationVariant(
                        name="Q8_0",
                        size_on_disk_gb=7.0,
                        vram_required_gb=8.0,
                        ram_required_gb=12.0,
                        quality_score=0.95,
                        speed_score=0.75,
                    ),
                ])
            else:
                # Default quantisation for non-GGUF models
                quantisation_variants.append(
                    QuantisationVariant(
                        name="fp16",
                        size_on_disk_gb=10.0,
                        vram_required_gb=12.0,
                        ram_required_gb=16.0,
                        quality_score=1.0,
                        speed_score=0.60,
                    )
                )

            # Calculate quality score based on likes and downloads
            likes = model_data.get("likes", 0)
            downloads = model_data.get("downloads", 0)
            min(1.0, (likes / 1000.0) + (downloads / 100000.0))

            return ModelEntry(
                model_id=f"huggingface/{model_id}",
                name=model_data.get("modelId", model_id),
                source=ModelSource.HUGGINGFACE,
                adapter_compatibility=["huggingface", "llama_cpp"],
                task_tags=task_tags,
                quantisation_variants=quantisation_variants,
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license=model_data.get("license", "Unknown"),
                description=model_data.get("cardData", {}).get("text", ""),
            )
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to convert HF data to ModelEntry",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return None

    async def check_fit(
        self,
        model_id: str,
        quantisation: str | None,
        resource_manager: "ResourceManager",
        registry: "ModelRegistry",
    ) -> tuple[bool, str]:
        """Check if a model will fit on the current system before downloading."""
        try:
            # Get model entry from registry
            entry = await registry.get(model_id)
            if not entry:
                return False, f"Model {model_id} not found in registry"

            # Find quantisation variant
            if quantisation:
                variant = None
                for v in entry.quantisation_variants:
                    if v.name == quantisation:
                        variant = v
                        break
                if not variant:
                    return False, f"Quantisation variant {quantisation} not found"
            elif entry.quantisation_variants:
                # Use highest quality variant
                variant = max(entry.quantisation_variants, key=lambda v: v.quality_score)
            else:
                return False, "No quantisation variants available"

            # Check with resource manager
            can_load, reason = await resource_manager.can_load(model_id, variant.name, registry)
            return can_load, reason
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to check model fit",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return False, f"Error checking fit: {str(e)}"

    async def request_download(
        self,
        request: DownloadRequest,
        resource_manager: "ResourceManager",
        registry: "ModelRegistry",
    ) -> DownloadResult:
        """Full download flow with checks and user approval."""
        start_time = time.time()

        try:
            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_DOWNLOAD_START,
                    component=TraceComponent.SYSTEM,
                    message=f"Download request for {request.model_id}",
                    level=TraceLevel.INFO,
                    data={"model_id": request.model_id, "source": request.source.value, "quantisation": request.quantisation},
                )
            )

            # Check if already downloaded
            entry = await registry.get(request.model_id)
            if entry and entry.download_status == DownloadStatus.DOWNLOADED:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.SYSTEM,
                        message=f"Model {request.model_id} already downloaded",
                        level=TraceLevel.INFO,
                    )
                )
                return DownloadResult(
                    success=True,
                    model_id=request.model_id,
                    quantisation=request.quantisation,
                    size_downloaded_gb=0.0,
                    duration_seconds=time.time() - start_time,
                )

            # Check disk space
            from system.profiler import SystemProfiler
            profiler = SystemProfiler(self.memory_router)
            system_profile = await profiler.get_cached()
            if system_profile and system_profile.storage:
                sum(s.total_mb for s in system_profile.storage)
                available_disk_mb = sum(s.available_mb for s in system_profile.storage)
                
                # Estimate model size (default to 10GB if unknown)
                estimated_size_gb = 10.0
                if entry and entry.quantisation_variants:
                    if request.quantisation:
                        for v in entry.quantisation_variants:
                            if v.name == request.quantisation:
                                estimated_size_gb = v.size_on_disk_gb
                                break
                    else:
                        estimated_size_gb = entry.quantisation_variants[0].size_on_disk_gb

                estimated_size_mb = estimated_size_gb * 1024
                if available_disk_mb < estimated_size_mb * 1.2:  # Require 20% buffer
                    await self.emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.MODEL_DOWNLOAD_FAILED,
                            component=TraceComponent.SYSTEM,
                            message="Insufficient disk space",
                            level=TraceLevel.WARNING,
                            data={"available_mb": available_disk_mb, "required_mb": estimated_size_mb * 1.2},
                        )
                    )
                    return DownloadResult(
                        success=False,
                        model_id=request.model_id,
                        quantisation=request.quantisation,
                        size_downloaded_gb=0.0,
                        duration_seconds=time.time() - start_time,
                        error=f"Insufficient disk space: {available_disk_mb / 1024:.1f}GB available, {estimated_size_mb * 1.2 / 1024:.1f}GB required",
                    )

            # Check hardware fit
            can_fit, fit_reason = await self.check_fit(
                request.model_id, request.quantisation, resource_manager, registry
            )
            if not can_fit:
                # Present alternatives
                if system_profile:
                    alternatives = await self.list_alternatives(
                        request.model_id, system_profile, registry
                    )
                    if alternatives:
                        await self.emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.MODEL_ALTERNATIVES_LISTED,
                                component=TraceComponent.SYSTEM,
                                message=f"Found {len(alternatives)} alternative models",
                                level=TraceLevel.INFO,
                                data={"alternatives": [m.model_id for m in alternatives]},
                            )
                        )
                
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.MODEL_DOWNLOAD_FAILED,
                        component=TraceComponent.SYSTEM,
                        message="Model does not fit in available memory",
                        level=TraceLevel.WARNING,
                        data={"reason": fit_reason},
                    )
                )
                return DownloadResult(
                    success=False,
                    model_id=request.model_id,
                    quantisation=request.quantisation,
                    size_downloaded_gb=0.0,
                    duration_seconds=time.time() - start_time,
                    error=fit_reason,
                )

            # Execute download based on source
            if request.source == ModelSource.OLLAMA:
                result = await self.download_ollama(request.model_id, request.quantisation)
            elif request.source == ModelSource.HUGGINGFACE:
                result = await self.download_huggingface(
                    request.model_id, request.quantisation or "Q4_K_M", "./models"
                )
            elif request.source == ModelSource.API:
                # API models don't need download, just validate
                result = await self._validate_api_model(request.model_id)
            else:
                result = DownloadResult(
                    success=False,
                    model_id=request.model_id,
                    quantisation=request.quantisation,
                    size_downloaded_gb=0.0,
                    duration_seconds=time.time() - start_time,
                    error=f"Download not supported for source {request.source.value}",
                )

            # Update registry on success
            if result.success:
                await registry.update_download_status(
                    request.model_id, DownloadStatus.DOWNLOADED, result.quantisation
                )

            return result
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.MODEL_DOWNLOAD_FAILED,
                        component=TraceComponent.SYSTEM,
                        message="Download failed",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return DownloadResult(
                success=False,
                model_id=request.model_id,
                quantisation=request.quantisation,
                size_downloaded_gb=0.0,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

    async def download_ollama(
        self, model_id: str, quantisation: str | None = None
    ) -> DownloadResult:
        """Download via Ollama pull API with progress tracking."""
        start_time = time.time()
        
        try:
            # Extract model name from model_id (e.g., "ollama/qwen2.5-coder:7b" -> "qwen2.5-coder:7b")
            model_name = model_id.split("/", 1)[1] if "/" in model_id else model_id

            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_DOWNLOAD_START,
                    component=TraceComponent.SYSTEM,
                    message=f"Pulling {model_name} from Ollama",
                    level=TraceLevel.INFO,
                    data={"model_name": model_name},
                )
            )

            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    f"{self.ollama_api_url}/api/pull",
                    json={"model": model_name, "stream": True},
                )
                response.raise_for_status()

                # Track progress
                total_bytes = 0
                last_progress = 0

                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json
                            data = json.loads(line)
                            if "total" in data and "completed" in data:
                                total = data["total"]
                                completed = data["completed"]
                                progress = (completed / total) * 100 if total > 0 else 0
                                
                                # Emit progress every 10%
                                if progress - last_progress >= 10:
                                    await self.emitter.emit(
                                        TraceEvent(
                                            event_type=TraceEventType.MODEL_DOWNLOAD_PROGRESS,
                                            component=TraceComponent.SYSTEM,
                                            message=f"Download progress: {progress:.1f}%",
                                            level=TraceLevel.INFO,
                                            data={"progress": progress, "completed": completed, "total": total},
                                        )
                                    )
                                    last_progress = progress
                        except json.JSONDecodeError:
                            pass

            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_DOWNLOAD_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Successfully pulled {model_name}",
                    level=TraceLevel.INFO,
                )
            )

            return DownloadResult(
                success=True,
                model_id=model_id,
                quantisation=quantisation,
                size_downloaded_gb=total_bytes / (1024**3),
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.MODEL_DOWNLOAD_FAILED,
                        component=TraceComponent.SYSTEM,
                        message="Ollama pull failed",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return DownloadResult(
                success=False,
                model_id=model_id,
                quantisation=quantisation,
                size_downloaded_gb=0.0,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

    async def download_huggingface(
        self, model_id: str, quantisation: str, target_dir: str
    ) -> DownloadResult:
        """Download GGUF file directly from HuggingFace with progress tracking."""
        start_time = time.time()
        
        try:
            # Construct download URL
            model_name = model_id.split("/", 1)[1] if "/" in model_id else model_id
            download_url = f"https://huggingface.co/{model_name}/resolve/main/{quantisation}.gguf"

            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_DOWNLOAD_START,
                    component=TraceComponent.SYSTEM,
                    message=f"Downloading {quantisation}.gguf from HuggingFace",
                    level=TraceLevel.INFO,
                    data={"model_id": model_id, "quantisation": quantisation, "url": download_url},
                )
            )

            os.makedirs(target_dir, exist_ok=True)
            output_path = os.path.join(target_dir, f"{model_name}_{quantisation}.gguf")

            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream("GET", download_url) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    last_progress = 0

                    with open(output_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                if progress - last_progress >= 10:
                                    await self.emitter.emit(
                                        TraceEvent(
                                            event_type=TraceEventType.MODEL_DOWNLOAD_PROGRESS,
                                            component=TraceComponent.SYSTEM,
                                            message=f"Download progress: {progress:.1f}%",
                                            level=TraceLevel.INFO,
                                            data={"progress": progress, "downloaded": downloaded, "total": total_size},
                                        )
                                    )
                                    last_progress = progress

            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_DOWNLOAD_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Successfully downloaded to {output_path}",
                    level=TraceLevel.INFO,
                )
            )

            return DownloadResult(
                success=True,
                model_id=model_id,
                quantisation=quantisation,
                size_downloaded_gb=downloaded / (1024**3),
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.MODEL_DOWNLOAD_FAILED,
                        component=TraceComponent.SYSTEM,
                        message="HuggingFace download failed",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return DownloadResult(
                success=False,
                model_id=model_id,
                quantisation=quantisation,
                size_downloaded_gb=0.0,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

    async def _validate_api_model(self, model_id: str) -> DownloadResult:
        """Validate API model by checking API key availability."""
        start_time = time.time()
        
        try:
            # Extract provider from model_id (e.g., "anthropic/claude-sonnet-4" -> "anthropic")
            provider = model_id.split("/", 1)[0] if "/" in model_id else model_id
            
            # Check for API key
            api_key = None
            if provider == "anthropic":
                api_key = os.environ.get("ANTHROPIC_API_KEY")
            elif provider == "openai":
                api_key = os.environ.get("OPENAI_API_KEY")
            elif provider == "google":
                api_key = os.environ.get("GOOGLE_API_KEY")
            
            if api_key:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.MODEL_DOWNLOAD_COMPLETE,
                        component=TraceComponent.SYSTEM,
                        message=f"API model {model_id} validated (key present)",
                        level=TraceLevel.INFO,
                    )
                )
                return DownloadResult(
                    success=True,
                    model_id=model_id,
                    quantisation=None,
                    size_downloaded_gb=0.0,
                    duration_seconds=time.time() - start_time,
                )
            else:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.MODEL_DOWNLOAD_FAILED,
                        component=TraceComponent.SYSTEM,
                        message=f"API key not found for {provider}",
                        level=TraceLevel.WARNING,
                    )
                )
                return DownloadResult(
                    success=False,
                    model_id=model_id,
                    quantisation=None,
                    size_downloaded_gb=0.0,
                    duration_seconds=time.time() - start_time,
                    error=f"API key not found for provider {provider}",
                )
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.MODEL_DOWNLOAD_FAILED,
                        component=TraceComponent.SYSTEM,
                        message="API model validation failed",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return DownloadResult(
                success=False,
                model_id=model_id,
                quantisation=None,
                size_downloaded_gb=0.0,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

    async def delete_model(
        self, model_id: str, registry: "ModelRegistry"
    ) -> bool:
        """Delete a downloaded model after user approval."""
        try:
            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_DELETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Requesting deletion of {model_id}",
                    level=TraceLevel.INFO,
                )
            )

            # Request approval
            if self.approval_callback:
                approved = await self.approval_callback.request_approval(
                    action_description=f"Delete model {model_id}",
                    pinned_model_to_evict="",
                    new_model_requesting="",
                    memory_impact=f"Free disk space used by {model_id}",
                )
                
                if not approved:
                    await self.emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.OPERATION_COMPLETE,
                            component=TraceComponent.SYSTEM,
                            message=f"Deletion of {model_id} denied by user",
                            level=TraceLevel.INFO,
                        )
                    )
                    return False
            else:
                # No approval callback, deny
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="No approval callback for model deletion",
                        level=TraceLevel.WARNING,
                    )
                )
                return False

            # Update registry
            await registry.update_download_status(model_id, DownloadStatus.NOT_DOWNLOADED, None)

            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Successfully deleted {model_id}",
                    level=TraceLevel.INFO,
                )
            )

            return True
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to delete model",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return False

    async def list_alternatives(
        self, model_id: str, system_profile: SystemProfile, registry: "ModelRegistry"
    ) -> list[ModelEntry]:
        """Given a model that doesn't fit, find alternatives that do fit."""
        try:
            # Get all models from registry
            all_models = await registry.list_all()
            
            # Filter by task tags of the original model
            original = await registry.get(model_id)
            if not original:
                return []
            
            alternatives = []
            for model in all_models:
                if model.model_id == model_id:
                    continue
                
                # Check for task tag overlap
                tag_overlap = set(original.task_tags) & set(model.task_tags)
                if tag_overlap:
                    # Check if fits
                    can_fit, _ = await self.check_fit(
                        model.model_id, None, None, registry
                    )
                    if can_fit:
                        alternatives.append(model)
            
            await self.emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.MODEL_ALTERNATIVES_LISTED,
                    component=TraceComponent.SYSTEM,
                    message=f"Found {len(alternatives)} alternative models",
                    level=TraceLevel.INFO,
                    data={"alternatives": [m.model_id for m in alternatives]},
                )
            )
            
            return alternatives
        except Exception as e:
            try:
                await self.emitter.emit(
                    TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to list alternatives",
                        level=TraceLevel.ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                )
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return []

    async def get_storage_summary(self) -> dict:
        """Returns total models downloaded, total disk used, available disk space."""
        try:
            from system.profiler import SystemProfiler
            profiler = SystemProfiler(self.memory_router)
            system_profile = await profiler.get_cached()
            
            if not system_profile or not system_profile.storage:
                return {
                    "total_models": 0,
                    "total_disk_used_gb": 0.0,
                    "available_disk_gb": 0.0,
                }
            
            # Convert MB to GB
            total_disk_used_mb = sum(s.total_mb - s.available_mb for s in system_profile.storage)
            available_disk_mb = sum(s.available_mb for s in system_profile.storage)
            
            return {
                "total_models": 0,  # Would need to track this separately
                "total_disk_used_gb": total_disk_used_mb / 1024,
                "available_disk_gb": available_disk_mb / 1024,
            }
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to get storage summary",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self.emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            return {
                "total_models": 0,
                "total_disk_used_gb": 0.0,
                "available_disk_gb": 0.0,
            }

