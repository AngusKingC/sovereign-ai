"""
Resource Manager - Live Resource Tracking and Model Load Enforcement

Single responsibility: Monitor loaded models, enforce resource budgets,
and manage model loading/unloading with intelligent eviction policies.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx

from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)
from core.schemas import (
    ApprovalCallback,
    LoadDecision,
    LoadedModel,
    ResourceSnapshot,
    SystemProfile,
)

if TYPE_CHECKING:
    from core.memory_router import MemoryRouter
    from system.model_acquisition import ModelRegistry

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages resource usage and model loading decisions."""

    def __init__(
        self,
        memory_router: "MemoryRouter",
        approval_callback: ApprovalCallback | None = None,
        kv_cache_budget_mb: int = 1024,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the resource manager with memory router and optional approval callback.

        Args:
            memory_router: Memory router for persistence
            approval_callback: Optional callback for user approval on pinned model eviction
            kv_cache_budget_mb: Reserved VRAM for KV cache overhead (default 1GB)
            emitter: Trace emitter for observability
        """
        self.memory_router = memory_router
        self.approval_callback = approval_callback
        self._kv_cache_budget_mb = kv_cache_budget_mb
        self._loaded_models: dict[str, LoadedModel] = {}
        self._ollama_api_url = "http://localhost:11434"
        self._emitter = emitter or MemoryTraceEmitter()

    async def available_vram_mb(
        self, total_vram_mb: int, loaded_model_vram_mb: float
    ) -> int:
        """Calculate available VRAM after accounting for loaded models and KV cache budget.

        Args:
            total_vram_mb: Total VRAM in MB
            loaded_model_vram_mb: VRAM used by loaded models in GB

        Returns:
            Available VRAM in MB, floored at 0
        """
        available = (
            total_vram_mb - int(loaded_model_vram_mb * 1024) - self._kv_cache_budget_mb
        )
        result = max(0, available)

        # Emit warning if available VRAM is critically low
        threshold_mb = int(self._kv_cache_budget_mb * 0.25)
        if result < threshold_mb:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    level=TraceLevel.WARNING,
                    message="VRAM critically low",
                    data={
                        "available_mb": result,
                        "threshold_mb": threshold_mb,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e, exc_info=True
                )

        return result

    async def snapshot(self, system_profile: SystemProfile) -> ResourceSnapshot:
        """Query current live resource state from SystemProfiler and Ollama API."""
        try:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.RESOURCE_SNAPSHOT,
                    component=TraceComponent.SYSTEM,
                    message="Taking resource snapshot",
                    level=TraceLevel.INFO,
                    data={},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e, exc_info=True
                )

            # Get resource info from system profile
            vram_total_gb = system_profile.gpu.total_vram_mb / 1024
            vram_available_gb = system_profile.gpu.available_vram_mb / 1024
            vram_used_gb = vram_total_gb - vram_available_gb

            ram_total_gb = system_profile.ram.total_mb / 1024
            ram_available_gb = system_profile.ram.available_mb / 1024
            ram_used_gb = ram_total_gb - ram_available_gb

            # Get loaded models from Ollama API
            loaded_models = []
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self._ollama_api_url}/api/ps")
                    if response.status_code == 200:
                        data = response.json()
                        for model_info in data.get("models", []):
                            model_name = model_info.get("name", "unknown")
                            # Try to find matching loaded model in our state
                            loaded_model = self._loaded_models.get(model_name)
                            if loaded_model:
                                loaded_models.append(loaded_model)
                            else:
                                # Create a basic entry for unknown loaded model
                                loaded_models.append(
                                    LoadedModel(
                                        model_id=model_name,
                                        adapter_name="ollama",
                                        quantisation="unknown",
                                        vram_used_gb=0.0,
                                        ram_used_gb=0.0,
                                    )
                                )
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to query Ollama API for loaded models",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e2:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e2, exc_info=True
                    )

            snapshot = ResourceSnapshot(
                timestamp=datetime.now(timezone.utc),
                vram_total_gb=vram_total_gb,
                vram_used_gb=vram_used_gb,
                vram_available_gb=vram_available_gb,
                ram_total_gb=ram_total_gb,
                ram_used_gb=ram_used_gb,
                ram_available_gb=ram_available_gb,
                loaded_models=loaded_models,
            )

            # Store snapshot to Postgres
            await self._store_snapshot(snapshot)

            return snapshot
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to take resource snapshot",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )
            raise

    async def _store_snapshot(self, snapshot: ResourceSnapshot) -> None:
        """Store snapshot to Postgres."""
        try:
            await self.memory_router.write_to_collection(
                data={
                    "content": snapshot.model_dump_json(),
                    "task_id": "resource_snapshot",
                    "metadata": {"type": "resource_snapshot"},
                },
                collection="resource_snapshots",
            )
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to store resource snapshot",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def can_load(
        self, model_id: str, quantisation: str, registry: "ModelRegistry"
    ) -> tuple[bool, str]:
        """Check if model fits in current memory."""
        try:
            # Get model entry from registry
            entry = await registry.get(model_id)
            if not entry:
                return False, f"Model {model_id} not found in registry"

            # Find quantisation variant
            variant = None
            for v in entry.quantisation_variants:
                if v.name == quantisation:
                    variant = v
                    break

            if not variant:
                return (
                    False,
                    f"Quantisation variant {quantisation} not found for model {model_id}",
                )

            # Get current snapshot
            from system.profiler import SystemProfiler

            profiler = SystemProfiler(self.memory_router)
            system_profile = await profiler.get_cached()
            if not system_profile:
                return False, "System profile not available"

            snapshot = await self.snapshot(system_profile)

            # Calculate available VRAM accounting for KV cache budget
            total_vram_mb = int(system_profile.gpu.total_vram_mb)
            loaded_model_vram_mb = snapshot.vram_used_gb
            available_vram_mb = await self.available_vram_mb(
                total_vram_mb, loaded_model_vram_mb
            )
            available_vram_gb = available_vram_mb / 1024

            # Check VRAM first
            if variant.vram_required_gb <= available_vram_gb:
                return (
                    True,
                    f"Model fits in available VRAM ({variant.vram_required_gb}GB <= {available_vram_gb}GB)",
                )

            # Check RAM fallback
            if variant.ram_required_gb <= snapshot.ram_available_gb:
                return (
                    True,
                    f"Model fits in available RAM ({variant.ram_required_gb}GB <= {snapshot.ram_available_gb}GB)",
                )

            return (
                False,
                f"Model does not fit in available VRAM ({variant.vram_required_gb}GB > {available_vram_gb}GB) or RAM ({variant.ram_required_gb}GB > {snapshot.ram_available_gb}GB)",
            )
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to check if model can load",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )
            return False, f"Error checking load capability: {str(e)}"

    async def request_load(
        self, model_id: str, quantisation: str, registry: "ModelRegistry"
    ) -> LoadDecision:
        """Full load decision flow."""
        try:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.RESOURCE_LOAD_REQUEST,
                    component=TraceComponent.SYSTEM,
                    message=f"Load request for {model_id}:{quantisation}",
                    level=TraceLevel.INFO,
                    data={"model_id": model_id, "quantisation": quantisation},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e, exc_info=True
                )

            # Check if already loaded
            if model_id in self._loaded_models:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.RESOURCE_LOAD_APPROVED,
                        component=TraceComponent.SYSTEM,
                        message=f"Model {model_id} already loaded",
                        level=TraceLevel.INFO,
                        data={},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return LoadDecision(
                    approved=True,
                    model_id=model_id,
                    quantisation=quantisation,
                    models_to_evict=[],
                    requires_user_approval=False,
                    reason="Model already loaded",
                )

            # Get model entry
            entry = await registry.get(model_id)
            if not entry:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.RESOURCE_LOAD_DENIED,
                        component=TraceComponent.SYSTEM,
                        message=f"Model {model_id} not found in registry",
                        level=TraceLevel.WARNING,
                        data={},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return LoadDecision(
                    approved=False,
                    model_id=model_id,
                    quantisation=quantisation,
                    models_to_evict=[],
                    requires_user_approval=False,
                    reason="Model not found in registry",
                )

            # Find quantisation variant
            variant = None
            for v in entry.quantisation_variants:
                if v.name == quantisation:
                    variant = v
                    break

            if not variant:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.RESOURCE_LOAD_DENIED,
                        component=TraceComponent.SYSTEM,
                        message=f"Quantisation variant {quantisation} not found",
                        level=TraceLevel.WARNING,
                        data={},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return LoadDecision(
                    approved=False,
                    model_id=model_id,
                    quantisation=quantisation,
                    models_to_evict=[],
                    requires_user_approval=False,
                    reason="Quantisation variant not found",
                )

            # Get current snapshot
            from system.profiler import SystemProfiler

            profiler = SystemProfiler(self.memory_router)
            system_profile = await profiler.get_cached()
            if not system_profile:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.RESOURCE_LOAD_DENIED,
                        component=TraceComponent.SYSTEM,
                        message="System profile not available",
                        level=TraceLevel.WARNING,
                        data={},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return LoadDecision(
                    approved=False,
                    model_id=model_id,
                    quantisation=quantisation,
                    models_to_evict=[],
                    requires_user_approval=False,
                    reason="System profile not available",
                )

            snapshot = await self.snapshot(system_profile)

            # Calculate available VRAM accounting for KV cache budget
            total_vram_mb = int(system_profile.gpu.total_vram_mb)
            loaded_model_vram_mb = snapshot.vram_used_gb
            available_vram_mb = await self.available_vram_mb(
                total_vram_mb, loaded_model_vram_mb
            )
            available_vram_gb = available_vram_mb / 1024

            # Check if fits without eviction
            if variant.vram_required_gb <= available_vram_gb:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.RESOURCE_LOAD_APPROVED,
                        component=TraceComponent.SYSTEM,
                        message="Model fits in available VRAM",
                        level=TraceLevel.INFO,
                        data={},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return LoadDecision(
                    approved=True,
                    model_id=model_id,
                    quantisation=quantisation,
                    models_to_evict=[],
                    requires_user_approval=False,
                    reason="Model fits in available VRAM",
                )

            # Calculate eviction candidates
            models_to_evict = []
            vram_to_free = variant.vram_required_gb - available_vram_gb

            # Sort loaded models by eviction priority: idle time first, then task priority, pinned last
            eviction_candidates = sorted(
                self._loaded_models.values(),
                key=lambda m: (
                    m.is_pinned,  # Pinned models last
                    m.task_priority.value != "LOW",  # LOW priority first
                    m.last_used_at,  # Longest unused first
                ),
            )

            vram_freed = 0.0
            for model in eviction_candidates:
                if vram_freed >= vram_to_free:
                    break

                if model.is_pinned:
                    # Need user approval for pinned model
                    if self.approval_callback:
                        try:
                            event = TraceEvent(
                                event_type=TraceEventType.RESOURCE_APPROVAL_REQUESTED,
                                component=TraceComponent.SYSTEM,
                                message=f"Requesting approval to evict pinned model {model.model_id}",
                                level=TraceLevel.INFO,
                                data={},
                                duration_ms=0,
                            )
                            await self._emitter.emit(event)
                        except Exception as e:
                            # Trace emission is fire-and-forget; never block caller
                            logger.warning(
                                "AR18: trace event emission failed: %s",
                                e,
                                exc_info=True,
                            )

                        approved = await self.approval_callback.request_approval(
                            action_description=f"Evict pinned model {model.model_id} to load {model_id}",
                            pinned_model_to_evict=model.model_id,
                            new_model_requesting=model_id,
                            memory_impact=f"Free {model.vram_used_gb}GB VRAM, require {variant.vram_required_gb}GB VRAM",
                        )

                        if approved:
                            models_to_evict.append(model.model_id)
                            vram_freed += model.vram_used_gb
                        else:
                            try:
                                event = TraceEvent(
                                    event_type=TraceEventType.RESOURCE_LOAD_DENIED,
                                    component=TraceComponent.SYSTEM,
                                    message=f"User denied eviction of pinned model {model.model_id}",
                                    level=TraceLevel.INFO,
                                    data={},
                                    duration_ms=0,
                                )
                                await self._emitter.emit(event)
                            except Exception as e:
                                # Trace emission is fire-and-forget; never block caller
                                logger.warning(
                                    "AR18: trace event emission failed: %s",
                                    e,
                                    exc_info=True,
                                )
                            return LoadDecision(
                                approved=False,
                                model_id=model_id,
                                quantisation=quantisation,
                                models_to_evict=[],
                                requires_user_approval=True,
                                reason="User denied eviction of pinned model",
                            )
                    else:
                        # No approval callback, deny
                        try:
                            event = TraceEvent(
                                event_type=TraceEventType.RESOURCE_LOAD_DENIED,
                                component=TraceComponent.SYSTEM,
                                message="No approval callback for pinned model eviction",
                                level=TraceLevel.WARNING,
                                data={},
                                duration_ms=0,
                            )
                            await self._emitter.emit(event)
                        except Exception as e:
                            # Trace emission is fire-and-forget; never block caller
                            logger.warning(
                                "AR18: trace event emission failed: %s",
                                e,
                                exc_info=True,
                            )
                        return LoadDecision(
                            approved=False,
                            model_id=model_id,
                            quantisation=quantisation,
                            models_to_evict=[],
                            requires_user_approval=True,
                            reason="Pinned model eviction required but no approval callback available",
                        )
                else:
                    models_to_evict.append(model.model_id)
                    vram_freed += model.vram_used_gb

            if vram_freed >= vram_to_free:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.RESOURCE_LOAD_APPROVED,
                        component=TraceComponent.SYSTEM,
                        message=f"Load approved with {len(models_to_evict)} evictions",
                        level=TraceLevel.INFO,
                        data={"models_to_evict": models_to_evict},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return LoadDecision(
                    approved=True,
                    model_id=model_id,
                    quantisation=quantisation,
                    models_to_evict=models_to_evict,
                    requires_user_approval=False,
                    reason=f"Load approved after evicting {len(models_to_evict)} models",
                )
            else:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.RESOURCE_LOAD_DENIED,
                        component=TraceComponent.SYSTEM,
                        message="Insufficient memory even after eviction",
                        level=TraceLevel.WARNING,
                        data={},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return LoadDecision(
                    approved=False,
                    model_id=model_id,
                    quantisation=quantisation,
                    models_to_evict=models_to_evict,
                    requires_user_approval=False,
                    reason="Insufficient memory even after eviction",
                )
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to process load request",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )
            return LoadDecision(
                approved=False,
                model_id=model_id,
                quantisation=quantisation,
                models_to_evict=[],
                requires_user_approval=False,
                reason=f"Error processing load request: {str(e)}",
            )

    async def record_load(
        self,
        model_id: str,
        adapter_name: str,
        quantisation: str,
        vram_used_gb: float,
        ram_used_gb: float,
    ) -> None:
        """Record that a model has been loaded."""
        try:
            loaded_model = LoadedModel(
                model_id=model_id,
                adapter_name=adapter_name,
                quantisation=quantisation,
                vram_used_gb=vram_used_gb,
                ram_used_gb=ram_used_gb,
                loaded_at=datetime.now(timezone.utc),
                last_used_at=datetime.now(timezone.utc),
            )
            self._loaded_models[model_id] = loaded_model
            await self._persist_loaded_state()
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to record model load",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def record_unload(self, model_id: str) -> None:
        """Record that a model has been unloaded."""
        try:
            if model_id in self._loaded_models:
                del self._loaded_models[model_id]
                await self._persist_loaded_state()
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to record model unload",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def record_usage(self, model_id: str) -> None:
        """Update last_used_at for a model."""
        try:
            if model_id in self._loaded_models:
                self._loaded_models[model_id].last_used_at = datetime.now(timezone.utc)
                await self._persist_loaded_state()
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to record model usage",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def pin_model(self, model_id: str) -> None:
        """Pin a model so it is never auto-evicted."""
        try:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.RESOURCE_PIN,
                    component=TraceComponent.SYSTEM,
                    message=f"Pinning model {model_id}",
                    level=TraceLevel.INFO,
                    data={},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e, exc_info=True
                )
            if model_id in self._loaded_models:
                self._loaded_models[model_id].is_pinned = True
                await self._persist_loaded_state()
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to pin model",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def unpin_model(self, model_id: str) -> None:
        """Unpin a model."""
        try:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.RESOURCE_UNPIN,
                    component=TraceComponent.SYSTEM,
                    message=f"Unpinning model {model_id}",
                    level=TraceLevel.INFO,
                    data={},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e, exc_info=True
                )
            if model_id in self._loaded_models:
                self._loaded_models[model_id].is_pinned = False
                await self._persist_loaded_state()
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to unpin model",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def get_loaded_models(self) -> list[LoadedModel]:
        """List currently loaded models."""
        return list(self._loaded_models.values())

    async def evict(self, model_id: str, force: bool = False) -> bool:
        """Evict a model from memory."""
        try:
            if model_id not in self._loaded_models:
                return False

            model = self._loaded_models[model_id]

            if model.is_pinned and not force:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.RESOURCE_EVICT,
                        component=TraceComponent.SYSTEM,
                        message=f"Cannot evict pinned model {model_id}",
                        level=TraceLevel.WARNING,
                        data={},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return False

            try:
                event = TraceEvent(
                    event_type=TraceEventType.RESOURCE_EVICT,
                    component=TraceComponent.SYSTEM,
                    message=f"Evicting model {model_id}",
                    level=TraceLevel.INFO,
                    data={},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e, exc_info=True
                )

            # Send unload signal to Ollama API
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{self._ollama_api_url}/api/generate",
                        json={"model": model_id, "keep_alive": 0},
                    )
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to send unload signal to Ollama",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e2:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e2, exc_info=True
                    )

            await self.record_unload(model_id)
            return True
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to evict model",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )
            return False

    async def release_model(self, adapter) -> None:
        """Marks the adapter's model as lowest eviction priority — first candidate if VRAM is needed.

        Args:
            adapter: The adapter whose model should be marked as evictable

        No-op if adapter is not tracked.
        """
        try:
            # Try to get model_id from adapter
            model_id = getattr(adapter, "model_id", None)
            if model_id is None:
                # Adapter might not have model_id attribute, try other common attributes
                model_id = getattr(adapter, "model_name", None)

            if model_id is None or model_id not in self._loaded_models:
                # No-op if adapter is not tracked
                return

            # Mark model as lowest eviction priority by setting is_pinned=False
            # and updating last_used_at to a very old time
            self._loaded_models[model_id].is_pinned = False
            self._loaded_models[model_id].last_used_at = datetime.min
            await self._persist_loaded_state()

            # Emit trace event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.RESOURCE_EVICT,
                    component=TraceComponent.SYSTEM,
                    message=f"Model {model_id} marked as evictable",
                    level=TraceLevel.INFO,
                    data={"model_id": model_id},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e, exc_info=True
                )
        except Exception as e:
            # Release failure should not crash
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to release model",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def ensure_model(self, adapter) -> None:
        """Restores adapter's model to normal eviction priority.

        Args:
            adapter: The adapter whose model should be ensured

        If model has been evicted, attempt reload (best-effort). If reload not supported,
        emit warning trace event and return without error.
        """
        try:
            # Try to get model_id from adapter
            model_id = getattr(adapter, "model_id", None)
            if model_id is None:
                # Adapter might not have model_id attribute, try other common attributes
                model_id = getattr(adapter, "model_name", None)

            if model_id is None:
                # No model_id available, emit warning and return
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Cannot ensure model: adapter has no model_id",
                        level=TraceLevel.WARNING,
                        data={},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e, exc_info=True
                    )
                return

            if model_id in self._loaded_models:
                # Model is tracked, restore normal priority
                self._loaded_models[model_id].is_pinned = False
                self._loaded_models[model_id].last_used_at = datetime.now(timezone.utc)
                await self._persist_loaded_state()
            else:
                # Model has been evicted or not tracked, attempt reload if supported
                # Check if adapter has a reload method
                if hasattr(adapter, "reload"):
                    try:
                        await adapter.reload()
                        # Record the load if successful
                        vram_used_gb = getattr(adapter, "vram_used_gb", 0.0)
                        ram_used_gb = getattr(adapter, "ram_used_gb", 0.0)
                        adapter_name = getattr(adapter, "__class__.__name__", "unknown")
                        quantisation = getattr(adapter, "quantisation", "unknown")

                        await self.record_load(
                            model_id,
                            adapter_name,
                            quantisation,
                            vram_used_gb,
                            ram_used_gb,
                        )
                    except Exception as e:
                        # Reload failed, emit warning
                        try:
                            event = TraceEvent(
                                event_type=TraceEventType.OPERATION_ERROR,
                                component=TraceComponent.SYSTEM,
                                message=f"Failed to reload model {model_id}",
                                level=TraceLevel.WARNING,
                                data={"error": str(e)},
                                duration_ms=0,
                            )
                            await self._emitter.emit(event)
                        except Exception as e2:
                            # Trace emission is fire-and-forget; never block caller
                            logger.warning(
                                "AR18: trace event emission failed: %s",
                                e2,
                                exc_info=True,
                            )
                else:
                    # Reload not supported, emit warning and return
                    try:
                        event = TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.SYSTEM,
                            message=f"Model {model_id} evicted and reload not supported",
                            level=TraceLevel.WARNING,
                            data={"model_id": model_id},
                            duration_ms=0,
                        )
                        await self._emitter.emit(event)
                    except Exception as e:
                        # Trace emission is fire-and-forget; never block caller
                        logger.warning(
                            "AR18: trace event emission failed: %s", e, exc_info=True
                        )

            # Emit trace event
            try:
                event = TraceEvent(
                    event_type=TraceEventType.RESOURCE_PIN,
                    component=TraceComponent.SYSTEM,
                    message=f"Model {model_id} priority restored",
                    level=TraceLevel.INFO,
                    data={"model_id": model_id},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e, exc_info=True
                )
        except Exception as e:
            # Ensure failure should not crash
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to ensure model",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def _persist_loaded_state(self) -> None:
        """Persist loaded model state to storage."""
        try:
            state = {
                "loaded_models": [m.model_dump() for m in self._loaded_models.values()],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.memory_router.write_to_collection(
                data={
                    "content": str(state),
                    "task_id": "resource_manager_state",
                    "metadata": {"type": "loaded_models_state"},
                },
                collection="resource_manager_state",
            )
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to persist loaded model state",
                    level=TraceLevel.WARNING,
                    data={"error": str(e)},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )

    async def initialize(self, system_profile: SystemProfile) -> None:
        """Initialize resource manager and reconcile with actual state."""
        try:
            # Load persisted state
            try:
                results = await self.memory_router.fetch_by_filter(
                    filter={
                        "task_id": "resource_manager_state",
                        "query": "loaded_models_state",
                    },
                    collection="resource_manager_state",
                )
                if results:
                    # Reconstruct loaded models from persisted state
                    for item in results:
                        if isinstance(item, dict) and "loaded_models" in item:
                            for model_data in item["loaded_models"]:
                                loaded_model = LoadedModel.model_validate(model_data)
                                self._loaded_models[loaded_model.model_id] = (
                                    loaded_model
                                )
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.SYSTEM,
                        message="Failed to load persisted resource manager state",
                        level=TraceLevel.WARNING,
                        data={"error": str(e)},
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception as e2:
                    # Trace emission is fire-and-forget; never block caller
                    logger.warning(
                        "AR18: trace event emission failed: %s", e2, exc_info=True
                    )

            # Reconcile with actual Ollama state
            snapshot = await self.snapshot(system_profile)
            actual_loaded = {m.model_id for m in snapshot.loaded_models}
            tracked_loaded = set(self._loaded_models.keys())

            # Remove models that are no longer actually loaded
            for model_id in tracked_loaded - actual_loaded:
                await self.record_unload(model_id)

            # Add models that are actually loaded but not tracked
            for model_id in actual_loaded - tracked_loaded:
                # Find the model in snapshot
                for model in snapshot.loaded_models:
                    if model.model_id == model_id:
                        await self.record_load(
                            model.model_id,
                            model.adapter_name,
                            model.quantisation,
                            model.vram_used_gb,
                            model.ram_used_gb,
                        )
                        break
        except Exception as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message="Failed to initialize resource manager",
                    level=TraceLevel.ERROR,
                    data={},
                    duration_ms=0,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._emitter.emit(event)
            except Exception as e2:
                # Trace emission is fire-and-forget; never block caller
                logger.warning(
                    "AR18: trace event emission failed: %s", e2, exc_info=True
                )
