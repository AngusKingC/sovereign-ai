"""
Model Registry - Model Resource Requirements and Compatibility Tracking

Single responsibility: Track all known models with their resource requirements,
adapter compatibility, and download status for intelligent model selection.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from core.schemas import (
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
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.memory_router import MemoryRouter


class ModelRegistry:
    """Registry for tracking model information and compatibility."""

    def __init__(self, memory_router: "MemoryRouter", emitter: TraceEmitter | None = None) -> None:
        """Initialize the model registry with memory router for persistence."""
        self.memory_router = memory_router
        self._models: dict[str, ModelEntry] = {}
        self._loaded = False
        self._emitter = emitter or MemoryTraceEmitter()

    async def _load_from_storage(self) -> None:
        """Load registry from Postgres storage."""
        try:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MODEL_REGISTRY_LOAD,
                    component=TraceComponent.SYSTEM,
                    message="Loading model registry from storage",
                    level=TraceLevel.INFO,
                    data={},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass

            # Try to load from Postgres
            try:
                results = await self.memory_router.fetch_by_filter(
                    filter={"task_id": "model_registry", "query": "model_registry"},
                    collection="model_registry"
                )
                
                if results:
                    for item in results:
                        if isinstance(item, dict):
                            entry = ModelEntry.model_validate(item)
                            self._models[entry.model_id] = entry
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to load model registry from Postgres",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    # Cleanup path: trace event emission failed, don't crash the application
                    # Per Rule 17: broad except requires inline comment
                    pass

            try:
                event = TraceEvent(
                    event_type=TraceEventType.MODEL_REGISTRY_LOAD_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Model registry loaded with {len(self._models)} models",
                    level=TraceLevel.INFO,
                    data={"model_count": len(self._models)},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to load model registry",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass

    async def _save_to_storage(self, entry: ModelEntry) -> None:
        """Save a model entry to storage."""
        try:
            await self.memory_router.write_to_collection(
                data={
                    "content": entry.model_dump_json(),
                    "task_id": "model_registry",
                    "metadata": {"model_id": entry.model_id, "type": "model_entry"},
                },
                collection="model_registry"
            )
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to save model entry to storage",
                    level=TraceLevel.WARNING,
                    data={"model_id": entry.model_id, "error": str(e)},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass

    async def register(self, entry: ModelEntry) -> None:
        """Add or update a model entry."""
        try:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MODEL_REGISTRY_REGISTER,
                    component=TraceComponent.SYSTEM,
                    message=f"Registering model: {entry.model_id}",
                    level=TraceLevel.INFO,
                    data={"model_id": entry.model_id, "source": entry.source.value},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass

            entry.last_updated = datetime.now()
            self._models[entry.model_id] = entry
            await self._save_to_storage(entry)
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to register model",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            raise

    async def get(self, model_id: str) -> ModelEntry | None:
        """Retrieve a model by ID."""
        return self._models.get(model_id)

    async def list_all(self) -> list[ModelEntry]:
        """List all registered models."""
        return list(self._models.values())

    async def list_by_tag(self, tag: str) -> list[ModelEntry]:
        """Filter by task tag."""
        return [m for m in self._models.values() if tag in m.task_tags]

    async def list_by_adapter(self, adapter_name: str) -> list[ModelEntry]:
        """Filter by adapter compatibility."""
        return [m for m in self._models.values() if adapter_name in m.adapter_compatibility]

    async def list_downloaded(self) -> list[ModelEntry]:
        """List only downloaded models."""
        return [m for m in self._models.values() if m.download_status == DownloadStatus.DOWNLOADED]

    async def recommend(
        self, task_tags: list[str], system_profile: SystemProfile
    ) -> list[ModelEntry]:
        """Recommend models based on task tags and system profile."""
        try:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MODEL_REGISTRY_RECOMMEND,
                    component=TraceComponent.SYSTEM,
                    message="Generating model recommendations",
                    level=TraceLevel.INFO,
                    data={"task_tags": task_tags, "vram_available_mb": system_profile.gpu.available_vram_mb},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass

            # Filter by task tag match
            matching_models = []
            for model in self._models.values():
                tag_match_score = len(set(task_tags) & set(model.task_tags)) / len(task_tags) if task_tags else 0.0
                if tag_match_score > 0:
                    matching_models.append((model, tag_match_score))

            # Filter by hardware fit
            available_vram_gb = system_profile.gpu.available_vram_mb / 1024
            available_ram_gb = system_profile.ram.available_mb / 1024

            viable_models = []
            for model, tag_match_score in matching_models:
                # Find the best quantisation that fits
                best_variant = None
                for variant in model.quantisation_variants:
                    if variant.vram_required_gb <= available_vram_gb or variant.ram_required_gb <= available_ram_gb:
                        best_variant = variant
                        break

                if best_variant:
                    # Calculate hardware fit score (higher is better)
                    if best_variant.vram_required_gb <= available_vram_gb:
                        hardware_fit = 1.0 - (best_variant.vram_required_gb / available_vram_gb)
                    else:
                        hardware_fit = 1.0 - (best_variant.ram_required_gb / available_ram_gb)

                    viable_models.append((model, tag_match_score, hardware_fit, best_variant))

            # Sort by: (1) hardware fit, (2) tag match score, (3) quality score
            viable_models.sort(
                key=lambda x: (x[2], x[1], x[3].quality_score), reverse=True
            )

            result = [model for model, _, _, _ in viable_models]

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Generated {len(result)} model recommendations",
                    level=TraceLevel.INFO,
                    data={"recommendation_count": len(result)},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass

            return result
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to generate recommendations",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            raise

    async def update_download_status(
        self, model_id: str, status: DownloadStatus, quantisation: str | None = None
    ) -> None:
        """Update download status for a model."""
        try:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.MODEL_REGISTRY_DOWNLOAD_UPDATE,
                    component=TraceComponent.SYSTEM,
                    message=f"Updating download status for {model_id}",
                    level=TraceLevel.INFO,
                    data={"model_id": model_id, "status": status.value, "quantisation": quantisation},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass

            if model_id in self._models:
                entry = self._models[model_id]
                entry.download_status = status
                entry.downloaded_quantisation = quantisation
                entry.last_updated = datetime.now()
                await self._save_to_storage(entry)
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to update download status",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception:
                # Cleanup path: trace event emission failed, don't crash the application
                # Per Rule 17: broad except requires inline comment
                pass
            raise

    async def initialize(self, system_profile: SystemProfile | None = None) -> None:
        """Initialize registry with seed data and load from storage."""
        if self._loaded:
            return

        # Load from storage first
        await self._load_from_storage()

        # Add seed data if not present
        await self._populate_seed_data()

        # Cross-reference with system profile if provided
        if system_profile:
            await self._cross_reference_with_profile(system_profile)

        self._loaded = True

    async def _populate_seed_data(self) -> None:
        """Populate registry with seed data for known models."""
        seed_models = [
            # Code models
            ModelEntry(
                model_id="ollama/qwen2.5-coder:7b",
                name="Qwen2.5 Coder 7B",
                source=ModelSource.OLLAMA,
                adapter_compatibility=["ollama", "lm_studio"],
                task_tags=["code", "reasoning"],
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=4.5,
                        vram_required_gb=5.0,
                        ram_required_gb=8.0,
                        quality_score=0.85,
                        speed_score=0.90,
                    ),
                    QuantisationVariant(
                        name="Q8_0",
                        size_on_disk_gb=7.5,
                        vram_required_gb=8.0,
                        ram_required_gb=12.0,
                        quality_score=0.95,
                        speed_score=0.75,
                    ),
                ],
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license="Apache 2.0",
                description="Code-focused model with strong reasoning capabilities",
            ),
            ModelEntry(
                model_id="ollama/qwen2.5-coder:14b",
                name="Qwen2.5 Coder 14B",
                source=ModelSource.OLLAMA,
                adapter_compatibility=["ollama", "lm_studio"],
                task_tags=["code", "reasoning"],
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=9.0,
                        vram_required_gb=10.0,
                        ram_required_gb=16.0,
                        quality_score=0.90,
                        speed_score=0.85,
                    ),
                ],
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license="Apache 2.0",
                description="Larger code-focused model with enhanced capabilities",
            ),
            # General/chat models
            ModelEntry(
                model_id="ollama/llama3.2:3b",
                name="Llama 3.2 3B",
                source=ModelSource.OLLAMA,
                adapter_compatibility=["ollama", "lm_studio"],
                task_tags=["chat", "general"],
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=2.0,
                        vram_required_gb=3.0,
                        ram_required_gb=4.0,
                        quality_score=0.75,
                        speed_score=0.95,
                    ),
                ],
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license="Llama 3.2 Community License",
                description="Lightweight general-purpose model",
            ),
            ModelEntry(
                model_id="ollama/llama3.2:8b",
                name="Llama 3.2 8B",
                source=ModelSource.OLLAMA,
                adapter_compatibility=["ollama", "lm_studio"],
                task_tags=["chat", "general", "reasoning"],
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=5.0,
                        vram_required_gb=6.0,
                        ram_required_gb=10.0,
                        quality_score=0.85,
                        speed_score=0.85,
                    ),
                ],
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license="Llama 3.2 Community License",
                description="Balanced general-purpose model",
            ),
            # Reasoning model
            ModelEntry(
                model_id="ollama/mistral:7b",
                name="Mistral 7B",
                source=ModelSource.OLLAMA,
                adapter_compatibility=["ollama", "lm_studio"],
                task_tags=["reasoning", "general", "chat"],
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=4.5,
                        vram_required_gb=5.0,
                        ram_required_gb=8.0,
                        quality_score=0.85,
                        speed_score=0.90,
                    ),
                ],
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license="Apache 2.0",
                description="Strong reasoning and general capabilities",
            ),
            # Embedding model
            ModelEntry(
                model_id="ollama/nomic-embed-text",
                name="Nomic Embed Text",
                source=ModelSource.OLLAMA,
                adapter_compatibility=["ollama"],
                task_tags=["embeddings"],
                quantisation_variants=[
                    QuantisationVariant(
                        name="Q4_K_M",
                        size_on_disk_gb=0.3,
                        vram_required_gb=0.5,
                        ram_required_gb=1.0,
                        quality_score=0.90,
                        speed_score=0.95,
                    ),
                ],
                download_status=DownloadStatus.NOT_DOWNLOADED,
                license="Apache 2.0",
                description="Text embedding model for semantic search",
            ),
            # Cloud API models
            ModelEntry(
                model_id="anthropic/claude-sonnet-4-20250514",
                name="Claude Sonnet 4",
                source=ModelSource.API,
                adapter_compatibility=["anthropic"],
                task_tags=["reasoning", "code", "chat", "general"],
                quantisation_variants=[],
                download_status=DownloadStatus.DOWNLOADED,
                license="Commercial",
                description="Anthropic's flagship model with strong reasoning",
            ),
            ModelEntry(
                model_id="openai/gpt-4o",
                name="GPT-4o",
                source=ModelSource.API,
                adapter_compatibility=["openai"],
                task_tags=["reasoning", "code", "chat", "general"],
                quantisation_variants=[],
                download_status=DownloadStatus.DOWNLOADED,
                license="Commercial",
                description="OpenAI's flagship multimodal model",
            ),
            ModelEntry(
                model_id="google/gemini-pro",
                name="Gemini Pro",
                source=ModelSource.API,
                adapter_compatibility=["gemini"],
                task_tags=["reasoning", "code", "chat", "general"],
                quantisation_variants=[],
                download_status=DownloadStatus.DOWNLOADED,
                license="Commercial",
                description="Google's flagship model",
            ),
        ]

        for model in seed_models:
            if model.model_id not in self._models:
                self._models[model.model_id] = model
                await self._save_to_storage(model)

    async def _cross_reference_with_profile(self, system_profile: SystemProfile) -> None:
        """Cross-reference seed data with SystemProfile to set download status."""
        if not system_profile.ollama.running:
            return

        downloaded_model_names = [
            model.name for model in system_profile.ollama.models_downloaded
        ]

        for model_id, entry in self._models.items():
            if entry.source == ModelSource.OLLAMA:
                # Extract model name from model_id (e.g., "ollama/qwen2.5-coder:7b" -> "qwen2.5-coder:7b")
                model_name = model_id.split("/", 1)[1] if "/" in model_id else model_id
                
                # Check if this model is downloaded
                for downloaded_name in downloaded_model_names:
                    if downloaded_name in model_name or model_name in downloaded_name:
                        await self.update_download_status(
                            model_id, DownloadStatus.DOWNLOADED
                        )
                        break

