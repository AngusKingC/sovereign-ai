"""
VRAM Manager — PEMADS Phase 2 wrapper around ResourceManager.

Tracks VRAM usage across expert panel debates. Provides:
- ensure_expert_models(experts): load all expert models before debate
- release_expert_models(experts): release after debate
- get_vram_status(): current VRAM usage for UI consumption
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.worker_base import LLMAdapter
from system.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class VRAMManager:
    def __init__(
        self, resource_manager: ResourceManager, emitter: Optional[Any] = None
    ) -> None:
        self._rm = resource_manager
        self._emitter = emitter
        self._debate_loaded: set[str] = set()  # model_names currently loaded for debate

    async def ensure_expert_models(self, adapters: list[LLMAdapter]) -> None:
        """Load all expert models. Best-effort — failures are logged, not raised."""
        for adapter in adapters:
            try:
                await self._rm.ensure_model(adapter)
                self._debate_loaded.add(adapter.model_name)
            except Exception as e:
                logger.warning(f"Failed to load {adapter.model_name}: {e}")

    async def release_expert_models(self, adapters: list[LLMAdapter]) -> None:
        """Release all expert models after debate."""
        for adapter in adapters:
            try:
                await self._rm.release_model(adapter)
                self._debate_loaded.discard(adapter.model_name)
            except Exception as e:
                logger.warning(f"Failed to release {adapter.model_name}: {e}")

    async def get_vram_status(self) -> dict[str, Any]:
        """Return VRAM status for UI consumption."""
        loaded = await self._rm.get_loaded_models()
        return {
            "loaded_models": [
                {
                    "model_id": m.model_id,
                    "vram_used_gb": m.vram_used_gb,
                    "is_pinned": m.is_pinned,
                }
                for m in loaded
            ],
            "debate_loaded": list(self._debate_loaded),
            "loaded_count": len(loaded),
        }
