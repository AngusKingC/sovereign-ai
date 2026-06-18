"""
Worker persistence for saving and loading worker profiles.

Single responsibility: Persist worker profiles to PostgreSQL and Obsidian mirror.
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from core.worker_factory import DynamicWorkerProfile
from core.schemas import WorkerStatus
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEmitter,
    NullTraceEmitter,
    TraceEvent,
)
from core.memory_router import MemoryRouter


class WorkerPersistence:
    """Manager for worker profile persistence to PostgreSQL and Obsidian."""
    
    def __init__(
        self,
        memory_router: MemoryRouter,
        emitter: TraceEmitter | None = None,
        obsidian_vault_path: str | None = None,
    ) -> None:
        """Initialize worker persistence.
        
        Args:
            memory_router: Memory router for PostgreSQL storage
            emitter: Trace emitter for observability
            obsidian_vault_path: Path to Obsidian vault for markdown mirror
        """
        self.emitter = emitter or NullTraceEmitter()
        self.memory_router = memory_router
        self.obsidian_vault_path = Path(obsidian_vault_path) if obsidian_vault_path else None
        
        # Ensure workers directory exists in Obsidian vault
        if self.obsidian_vault_path:
            workers_dir = self.obsidian_vault_path / "workers"
            workers_dir.mkdir(parents=True, exist_ok=True)
    
    async def save(self, profile: DynamicWorkerProfile) -> None:
        """Save worker profile to PostgreSQL and Obsidian mirror.
        
        Args:
            profile: Worker profile to save
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_START,
                component=TraceComponent.SYSTEM,
                message=f"Saving worker profile: {profile.worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": profile.worker_id, "version": profile.version},
            ))
            
            # Check if this is an update (worker already exists)
            existing = await self._load_raw(profile.worker_id)
            if existing:
                # Mark old version as not current
                await self._mark_old_version(profile.worker_id)
                # Increment version
                profile.version = existing.get("version", 1) + 1
            
            # Save to PostgreSQL
            await self.memory_router.write_to_collection(
                data={
                    "type": "worker_profile",
                    "worker_id": profile.worker_id,
                    "version": profile.version,
                    "is_current": True,
                    "profile": profile.model_dump(),
                },
                collection="workers",
            )
            
            # Write to Obsidian mirror
            if self.obsidian_vault_path:
                await self._write_obsidian_mirror(profile)
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Saved worker profile: {profile.worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": profile.worker_id, "version": profile.version},
            ))
        except Exception as e:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.SYSTEM,
                message=f"Failed to save worker profile: {profile.worker_id}",
                level=TraceLevel.ERROR,
                data={"worker_id": profile.worker_id},
                error_type=type(e).__name__,
                error_message=str(e),
            ))
            raise
    
    async def load_all(self) -> list[DynamicWorkerProfile]:
        """Load all current worker profiles from PostgreSQL.
        
        Returns:
            List of current worker profiles (is_current=True)
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_START,
                component=TraceComponent.SYSTEM,
                message="Loading all worker profiles",
                level=TraceLevel.INFO,
            ))
            
            # Query for current workers
            results = await self.memory_router.fetch_by_filter(
                filter={"type": "worker_profile", "is_current": True},
                collection="workers",
            )
            
            profiles = []
            for result in results:
                profile_data = result.get("content", {}).get("profile", {})
                if profile_data:
                    profiles.append(DynamicWorkerProfile(**profile_data))
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Loaded {len(profiles)} worker profiles",
                level=TraceLevel.INFO,
                data={"count": len(profiles)},
            ))
            
            return profiles
        except Exception as e:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.SYSTEM,
                message="Failed to load worker profiles",
                level=TraceLevel.ERROR,
                error_type=type(e).__name__,
                error_message=str(e),
            ))
            raise
    
    async def load_one(self, worker_id: str) -> DynamicWorkerProfile | None:
        """Load a single worker profile by ID.
        
        Args:
            worker_id: Worker ID to load
            
        Returns:
            Worker profile or None if not found
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_START,
                component=TraceComponent.SYSTEM,
                message=f"Loading worker profile: {worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": worker_id},
            ))
            
            # Query for specific worker
            results = await self.memory_router.fetch_by_filter(
                filter={"type": "worker_profile", "worker_id": worker_id, "is_current": True},
                collection="workers",
            )
            
            if not results:
                await self.emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.SYSTEM,
                    message=f"Worker profile not found: {worker_id}",
                    level=TraceLevel.INFO,
                    data={"worker_id": worker_id},
                ))
                return None
            
            profile_data = results[0].get("content", {}).get("profile", {})
            profile = DynamicWorkerProfile(**profile_data)
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Loaded worker profile: {worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": worker_id},
            ))
            
            return profile
        except Exception as e:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.SYSTEM,
                message=f"Failed to load worker profile: {worker_id}",
                level=TraceLevel.ERROR,
                data={"worker_id": worker_id},
                error_type=type(e).__name__,
                error_message=str(e),
            ))
            raise
    
    async def deprecate(self, worker_id: str) -> None:
        """Deprecate a worker profile.
        
        Args:
            worker_id: Worker ID to deprecate
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_START,
                component=TraceComponent.SYSTEM,
                message=f"Deprecating worker: {worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": worker_id},
            ))
            
            # Load current profile
            profile = await self.load_one(worker_id)
            if not profile:
                raise ValueError(f"Worker not found: {worker_id}")
            
            # Update status
            profile.status = WorkerStatus.DEPRECATED
            
            # Save updated profile
            await self.save(profile)
            
            # Update Obsidian mirror
            if self.obsidian_vault_path:
                await self._write_obsidian_mirror(profile)
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Deprecated worker: {worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": worker_id},
            ))
        except Exception as e:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.SYSTEM,
                message=f"Failed to deprecate worker: {worker_id}",
                level=TraceLevel.ERROR,
                data={"worker_id": worker_id},
                error_type=type(e).__name__,
                error_message=str(e),
            ))
            raise
    
    async def archive(self, worker_id: str) -> None:
        """Archive a worker profile.
        
        Args:
            worker_id: Worker ID to archive
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_START,
                component=TraceComponent.SYSTEM,
                message=f"Archiving worker: {worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": worker_id},
            ))
            
            # Load current profile
            profile = await self.load_one(worker_id)
            if not profile:
                raise ValueError(f"Worker not found: {worker_id}")
            
            # Update status
            profile.status = WorkerStatus.ARCHIVED
            
            # Save updated profile
            await self.save(profile)
            
            # Update Obsidian mirror
            if self.obsidian_vault_path:
                await self._write_obsidian_mirror(profile)
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Archived worker: {worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": worker_id},
            ))
        except Exception as e:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.SYSTEM,
                message=f"Failed to archive worker: {worker_id}",
                level=TraceLevel.ERROR,
                data={"worker_id": worker_id},
                error_type=type(e).__name__,
                error_message=str(e),
            ))
            raise
    
    async def get_version_history(self, worker_id: str) -> list[DynamicWorkerProfile]:
        """Get version history for a worker.
        
        Args:
            worker_id: Worker ID to get history for
            
        Returns:
            List of all versions ordered by version number ascending
        """
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_START,
                component=TraceComponent.SYSTEM,
                message=f"Loading version history for worker: {worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": worker_id},
            ))
            
            # Query for all versions of the worker
            results = await self.memory_router.fetch_by_filter(
                filter={"type": "worker_profile", "worker_id": worker_id},
                collection="workers",
            )
            
            profiles = []
            for result in results:
                profile_data = result.get("content", {}).get("profile", {})
                if profile_data:
                    profiles.append(DynamicWorkerProfile(**profile_data))
            
            # Sort by version number ascending
            profiles.sort(key=lambda p: p.version)
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Loaded {len(profiles)} versions for worker: {worker_id}",
                level=TraceLevel.INFO,
                data={"worker_id": worker_id, "version_count": len(profiles)},
            ))
            
            return profiles
        except Exception as e:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_ERROR,
                component=TraceComponent.SYSTEM,
                message=f"Failed to load version history for worker: {worker_id}",
                level=TraceLevel.ERROR,
                data={"worker_id": worker_id},
                error_type=type(e).__name__,
                error_message=str(e),
            ))
            raise
    
    async def _load_raw(self, worker_id: str) -> dict[str, Any] | None:
        """Load raw worker data from PostgreSQL.
        
        Args:
            worker_id: Worker ID to load
            
        Returns:
            Raw worker data or None if not found
        """
        results = await self.memory_router.fetch_by_filter(
            filter={"type": "worker_profile", "worker_id": worker_id, "is_current": True},
            collection="workers",
        )
        
        if not results:
            return None
        
        return results[0].get("content", {})
    
    async def _mark_old_version(self, worker_id: str) -> None:
        """Mark old version as not current.
        
        Args:
            worker_id: Worker ID to mark
        """
        # Load current version
        current = await self._load_raw(worker_id)
        if current:
            # Write back with is_current=False
            await self.memory_router.write_to_collection(
                data={
                    "type": "worker_profile",
                    "worker_id": worker_id,
                    "version": current.get("version", 1),
                    "is_current": False,
                    "profile": current.get("profile", {}),
                },
                collection="workers",
            )
    
    async def _write_obsidian_mirror(self, profile: DynamicWorkerProfile) -> None:
        """Write worker profile to Obsidian markdown file.
        
        Args:
            profile: Worker profile to write
        """
        if not self.obsidian_vault_path:
            return
        
        workers_dir = self.obsidian_vault_path / "workers"
        filename = f"{profile.worker_id}_v{profile.version}.md"
        filepath = workers_dir / filename
        
        content = f"""# {profile.name}

**Status**: {profile.status.value}
**Version**: {profile.version}
**Created**: {profile.creation_date.isoformat()}
**Purpose**: {profile.purpose}
**Capabilities**: {", ".join(profile.capabilities)}
**Preferred Models**: {", ".join(profile.preferred_models)}
**Performance Score**: {profile.performance_score}
**Active Tasks**: {profile.active_tasks}
**Instruction File**: {profile.instruction_file_ref or "not set"}
"""
        
        filepath.write_text(content, encoding="utf-8")
