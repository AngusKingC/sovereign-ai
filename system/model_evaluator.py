"""
Model Evaluator - Intelligent model selection and evaluation.

Single responsibility: Evaluate and recommend the best available model
for a worker's task type based on hardware constraints and task suitability.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field

from core.schemas import (
    ModelEntry,
    QuantisationVariant,
    SystemProfile,
    DownloadStatus,
    EvaluationRecord,
)
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEmitter,
    TraceEvent,
    NullTraceEmitter,
)

if TYPE_CHECKING:
    from system.model_registry import ModelRegistry
    from system.resource_manager import ResourceManager


class ModelRecommendation(BaseModel):
    """A single model recommendation with scoring details."""
    model_id: str = Field(description="Model identifier")
    model_name: str = Field(description="Human-readable model name")
    quantisation: str = Field(description="Quantisation variant name")
    score: float = Field(ge=0.0, le=1.0, description="Overall recommendation score")
    reasoning: str = Field(description="Human-readable explanation of the score")
    fits_vram: bool = Field(description="Whether model fits in available VRAM")
    fits_ram: bool = Field(description="Whether model fits in available RAM")
    task_suitability: float = Field(ge=0.0, le=1.0, description="Task tag match score")


class EvaluationResult(BaseModel):
    """Result of model evaluation for a worker."""
    worker_id: str = Field(description="Worker identifier")
    task_type: str = Field(description="Task type being evaluated")
    recommendations: list[ModelRecommendation] = Field(description="Ranked recommendations, best first")
    evaluated_at: datetime = Field(description="When evaluation was performed")
    hardware_snapshot: dict = Field(description="Hardware state at time of evaluation")


class ModelEvaluator:
    """Evaluates and recommends models for workers based on task and hardware."""

    def __init__(
        self,
        model_registry: "ModelRegistry",
        resource_manager: "ResourceManager",
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the model evaluator with dependencies.
        
        Args:
            model_registry: Registry of available models
            resource_manager: Manager for hardware resource tracking
            emitter: TraceEmitter for observability
        """
        self.model_registry = model_registry
        self.resource_manager = resource_manager
        self.emitter = emitter if emitter is not None else NullTraceEmitter()

    async def evaluate(
        self,
        worker_id: str,
        task_tags: list[str],
        quality_preference: float = 0.5,
    ) -> EvaluationResult:
        """
        Evaluate models for a worker based on task tags and hardware constraints.
        
        Args:
            worker_id: Worker identifier
            task_tags: List of task tags to match against model capabilities
            quality_preference: 0.0-1.0, higher weights quality over speed
            
        Returns:
            EvaluationResult with ranked recommendations
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=TraceEventType.OPERATION_START,
                component=TraceComponent.SYSTEM,
                level=TraceLevel.INFO,
                message=f"Model evaluation started for worker {worker_id}",
                data={
                    "worker_id": worker_id,
                    "task_tags": task_tags,
                    "quality_preference": quality_preference,
                },
                duration_ms=0,
            ))
        except Exception:
            pass

        # Get hardware snapshot
        from system.profiler import SystemProfiler
        profiler = SystemProfiler(self.resource_manager.memory_router)
        system_profile = await profiler.get_cached()
        
        if not system_profile:
            # Return empty result if no system profile available
            result = EvaluationResult(
                worker_id=worker_id,
                task_type=",".join(task_tags),
                recommendations=[],
                evaluated_at=datetime.utcnow(),
                hardware_snapshot={},
            )
            
            try:
                await self.emitter.emit(TraceEvent(
                    event_id=uuid4(),
                    timestamp=datetime.utcnow(),
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    level=TraceLevel.WARNING,
                    message="Model evaluation completed with no system profile",
                    data={"worker_id": worker_id, "recommendation_count": 0},
                    duration_ms=0,
                ))
            except Exception:
                pass
            
            return result

        # Get resource snapshot
        try:
            snapshot = await self.resource_manager.snapshot(system_profile)
            hardware_snapshot = {
                "vram_available_gb": snapshot.vram_available_gb,
                "vram_total_gb": snapshot.vram_total_gb,
                "ram_available_gb": snapshot.ram_available_gb,
                "ram_total_gb": snapshot.ram_total_gb,
            }
        except Exception:
            # Fallback to system profile if snapshot fails
            hardware_snapshot = {
                "vram_available_gb": system_profile.gpu.available_vram_mb / 1024,
                "vram_total_gb": system_profile.gpu.total_vram_mb / 1024,
                "ram_available_gb": system_profile.ram.available_mb / 1024,
                "ram_total_gb": system_profile.ram.total_mb / 1024,
            }

        # Query models for task tags
        matching_models = []
        for tag in task_tags:
            models = await self.model_registry.list_by_tag(tag)
            for model in models:
                if model not in matching_models:
                    matching_models.append(model)

        # Score each candidate
        recommendations = []
        for model in matching_models:
            # Find best quantisation variant that fits
            best_variant = None
            for variant in model.quantisation_variants:
                if variant.vram_required_gb <= hardware_snapshot["vram_available_gb"]:
                    best_variant = variant
                    break
                elif variant.ram_required_gb <= hardware_snapshot["ram_available_gb"]:
                    best_variant = variant
                    break

            if not best_variant:
                continue  # Skip models that don't fit

            # Calculate scores
            hardware_score = 1.0 if best_variant.vram_required_gb <= hardware_snapshot["vram_available_gb"] else 0.5
            suitability_score = len(set(task_tags) & set(model.task_tags)) / len(task_tags) if task_tags else 0.0
            quality_score = best_variant.quality_score
            speed_score = best_variant.speed_score

            # Final score calculation
            final_score = (
                (hardware_score * 0.4) +
                (suitability_score * 0.3) +
                (quality_score * quality_preference * 0.3) +
                (speed_score * (1 - quality_preference) * 0.3)
            )

            # Determine fit flags
            fits_vram = best_variant.vram_required_gb <= hardware_snapshot["vram_available_gb"]
            fits_ram = best_variant.ram_required_gb <= hardware_snapshot["ram_available_gb"]

            # Build reasoning
            reasoning_parts = []
            if fits_vram:
                reasoning_parts.append(f"Fits VRAM ({best_variant.vram_required_gb}GB)")
            elif fits_ram:
                reasoning_parts.append(f"Fits RAM ({best_variant.ram_required_gb}GB)")
            reasoning_parts.append(f"Task suitability: {suitability_score:.2f}")
            reasoning_parts.append(f"Quality: {quality_score:.2f}")
            reasoning_parts.append(f"Speed: {speed_score:.2f}")
            reasoning = ", ".join(reasoning_parts)

            recommendation = ModelRecommendation(
                model_id=model.model_id,
                model_name=model.name,
                quantisation=best_variant.name,
                score=final_score,
                reasoning=reasoning,
                fits_vram=fits_vram,
                fits_ram=fits_ram,
                task_suitability=suitability_score,
            )
            recommendations.append(recommendation)

        # Sort by score descending
        recommendations.sort(key=lambda r: r.score, reverse=True)

        result = EvaluationResult(
            worker_id=worker_id,
            task_type=",".join(task_tags),
            recommendations=recommendations,
            evaluated_at=datetime.utcnow(),
            hardware_snapshot=hardware_snapshot,
        )

        try:
            await self.emitter.emit(TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                level=TraceLevel.INFO,
                message=f"Model evaluation completed for worker {worker_id}",
                data={
                    "worker_id": worker_id,
                    "recommendation_count": len(recommendations),
                    "best_model": recommendations[0].model_id if recommendations else None,
                },
                duration_ms=0,
            ))
        except Exception:
            pass

        return result

    async def get_best(
        self,
        worker_id: str,
        task_tags: list[str],
        quality_preference: float = 0.5,
    ) -> ModelRecommendation | None:
        """
        Get the best model recommendation for a worker.
        
        Args:
            worker_id: Worker identifier
            task_tags: List of task tags to match against model capabilities
            quality_preference: 0.0-1.0, higher weights quality over speed
            
        Returns:
            Top recommendation or None if no models fit hardware constraints
        """
        result = await self.evaluate(worker_id, task_tags, quality_preference)
        
        if result.recommendations:
            return result.recommendations[0]
        return None

    async def record_selection(
        self,
        worker_id: str,
        model_id: str,
        quantisation: str,
    ) -> None:
        """
        Record which model was ultimately selected for a worker.
        
        Args:
            worker_id: Worker identifier
            model_id: Selected model identifier
            quantisation: Selected quantisation variant
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                level=TraceLevel.INFO,
                message=f"Model selection recorded for worker {worker_id}",
                data={
                    "worker_id": worker_id,
                    "model_id": model_id,
                    "quantisation": quantisation,
                },
                duration_ms=0,
            ))
        except Exception:
            pass

        # Update ModelRegistry download status if needed
        try:
            entry = await self.model_registry.get(model_id)
            if entry and entry.download_status != DownloadStatus.DOWNLOADED:
                await self.model_registry.update_download_status(
                    model_id, DownloadStatus.DOWNLOADED, quantisation
                )
        except Exception:
            pass

    def historical_performance_weight(
        self,
        worker_id: str,
        base_score: float,
        evaluation_records: list[EvaluationRecord],
    ) -> float:
        """Weight base score with historical performance data.
        
        Args:
            worker_id: Worker identifier
            base_score: Base score from hardware/fit evaluation
            evaluation_records: Historical evaluation records for the worker
            
        Returns:
            Weighted score if >10 records exist, otherwise base score unchanged
        """
        if len(evaluation_records) > 10:
            # Compute average final score from historical records
            avg_final_score = sum(record.final_score for record in evaluation_records) / len(evaluation_records)
            # Weighted blend: 70% historical, 30% base
            return (avg_final_score * 0.7) + (base_score * 0.3)
        else:
            # Not enough historical data, return base score unchanged
            return base_score
