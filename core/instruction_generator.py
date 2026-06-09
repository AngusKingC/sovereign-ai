"""
Instruction file generator for workers and orchestrator.

LLM-based worker profile generation replacing the rule-based system from Prompt 15.
Each worker gets an instruction file and changelog in Obsidian. Orchestrator gets identical files.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from core.worker_base import LLMAdapter
from core.worker_factory import DynamicWorkerProfile
from core.memory_router import MemoryRouter
from core.rating_system import RatingSystem
from core.observability import MemoryTraceEmitter, TraceEmitter, TraceEvent, TraceEventType, TraceComponent, TraceLevel
from core.schemas import InstructionFile, InstructionChangelogEntry


class InstructionGenerator:
    """LLM-based instruction file generator for workers and orchestrator."""
    
    def __init__(
        self,
        adapter: LLMAdapter,
        rating_system: RatingSystem,
        memory_router: MemoryRouter,
        obsidian_vault_path: str | None = None,
        emitter: TraceEmitter | None = None
    ):
        """Initialize instruction generator.
        
        Args:
            adapter: LLMAdapter for generating instruction content
            rating_system: RatingSystem for accessing worker rating history
            memory_router: MemoryRouter for storing instruction files
            obsidian_vault_path: Path to Obsidian vault for markdown files (optional)
            emitter: TraceEmitter for observability (defaults to MemoryTraceEmitter)
        """
        self.adapter = adapter
        self.rating_system = rating_system
        self.memory_router = memory_router
        self.obsidian_vault_path = Path(obsidian_vault_path) if obsidian_vault_path else None
        self.emitter = emitter if emitter is not None else MemoryTraceEmitter()
    
    async def generate_instruction_file(
        self,
        profile: DynamicWorkerProfile,
        trigger: str | None = None
    ) -> tuple[InstructionFile, DynamicWorkerProfile]:
        """Generate a new instruction file for a worker.
        
        Args:
            profile: Worker profile to generate instruction for
            trigger: Reason for generation (optional)
            
        Returns:
            InstructionFile object with version 1
        """
        # Build LLM prompt for instruction generation
        prompt = self._build_generation_prompt(profile)
        
        # Generate instruction content using LLM
        response = await self.adapter.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )
        
        content = response.content.strip()
        
        # Create instruction file
        version = 1
        created_at = datetime.now()
        updated_at = created_at
        
        obsidian_path = self._get_obsidian_instruction_path(profile.worker_id)
        
        instruction_file = InstructionFile(
            worker_id=profile.worker_id,
            version=version,
            content=content,
            obsidian_path=obsidian_path,
            created_at=created_at,
            updated_at=updated_at
        )
        
        # Store in memory router
        await self.memory_router.write(
            {
                "type": "instruction_file",
                "worker_id": profile.worker_id,
                "version": version,
                "content": content,
                "obsidian_path": obsidian_path,
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat()
            },
            collection="instruction_files"
        )
        
        # Write to Obsidian if vault path is set
        if self.obsidian_vault_path:
            await self._write_to_obsidian(instruction_file)
        
        # Create initial changelog entry
        changelog_entry = InstructionChangelogEntry(
            worker_id=profile.worker_id,
            version=version,
            trigger=trigger or "Initial generation",
            diff_summary="Initial instruction file created",
            rating_trend=None,
            created_at=created_at
        )
        
        await self.memory_router.write(
            {
                "type": "instruction_changelog",
                "worker_id": profile.worker_id,
                "version": version,
                "trigger": changelog_entry.trigger,
                "diff_summary": changelog_entry.diff_summary,
                "rating_trend": changelog_entry.rating_trend,
                "created_at": changelog_entry.created_at.isoformat()
            },
            collection="instruction_changelogs"
        )
        
        # Write changelog to Obsidian if vault path is set
        if self.obsidian_vault_path:
            await self._write_changelog_to_obsidian(profile.worker_id, [changelog_entry])
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Generated instruction file v{version} for worker {profile.worker_id}",
                level=TraceLevel.INFO,
                data={
                    "worker_id": profile.worker_id,
                    "version": version,
                    "trigger": trigger
                }
            ))
        except Exception:
            pass
        
        # Update profile with instruction file reference
        profile = profile.model_copy(update={"instruction_file_ref": obsidian_path})
        
        return instruction_file, profile
    
    async def update_instruction_file(
        self,
        profile: DynamicWorkerProfile,
        existing: InstructionFile,
        trigger: str
    ) -> InstructionFile:
        """Update an existing instruction file.
        
        Args:
            profile: Worker profile
            existing: Existing instruction file to update
            trigger: Reason for update
            
        Returns:
            New InstructionFile object with incremented version
        """
        # Get rating trend if available
        rating_trend = await self.rating_system.get_trend(profile.worker_id, window=10)
        
        # Build LLM prompt for update
        prompt = self._build_update_prompt(profile, existing.content, trigger, rating_trend)
        
        # Generate updated instruction content using LLM
        response = await self.adapter.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )
        
        content = response.content.strip()
        
        # Generate diff summary
        diff_prompt = self._build_diff_summary_prompt(existing.content, content)
        diff_response = await self.adapter.generate(
            messages=[{"role": "user", "content": diff_prompt}],
            temperature=0.3,
            max_tokens=500
        )
        diff_summary = diff_response.content.strip()
        
        # Create new instruction file with incremented version
        new_version = existing.version + 1
        created_at = datetime.now()
        updated_at = created_at
        
        obsidian_path = existing.obsidian_path
        
        new_instruction_file = InstructionFile(
            worker_id=profile.worker_id,
            version=new_version,
            content=content,
            obsidian_path=obsidian_path,
            created_at=created_at,
            updated_at=updated_at
        )
        
        # Store in memory router
        await self.memory_router.write(
            {
                "type": "instruction_file",
                "worker_id": profile.worker_id,
                "version": new_version,
                "content": content,
                "obsidian_path": obsidian_path,
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat()
            },
            collection="instruction_files"
        )
        
        # Write to Obsidian if vault path is set
        if self.obsidian_vault_path:
            await self._write_to_obsidian(new_instruction_file)
        
        # Create changelog entry
        changelog_entry = InstructionChangelogEntry(
            worker_id=profile.worker_id,
            version=new_version,
            trigger=trigger,
            diff_summary=diff_summary,
            rating_trend=rating_trend,
            created_at=created_at
        )
        
        await self.memory_router.write(
            {
                "type": "instruction_changelog",
                "worker_id": profile.worker_id,
                "version": new_version,
                "trigger": changelog_entry.trigger,
                "diff_summary": changelog_entry.diff_summary,
                "rating_trend": changelog_entry.rating_trend,
                "created_at": changelog_entry.created_at.isoformat()
            },
            collection="instruction_changelogs"
        )
        
        # Update changelog in Obsidian if vault path is set
        if self.obsidian_vault_path:
            existing_changelog = await self.get_instruction_changelog(profile.worker_id)
            existing_changelog.append(changelog_entry)
            await self._write_changelog_to_obsidian(profile.worker_id, existing_changelog)
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Updated instruction file v{new_version} for worker {profile.worker_id}",
                level=TraceLevel.INFO,
                data={
                    "worker_id": profile.worker_id,
                    "version": new_version,
                    "trigger": trigger,
                    "rating_trend": rating_trend
                }
            ))
        except Exception:
            pass
        
        return new_instruction_file
    
    async def get_instruction_file(
        self,
        worker_id: str
    ) -> InstructionFile | None:
        """Get the latest instruction file for a worker.
        
        Args:
            worker_id: Worker identifier
            
        Returns:
            Latest InstructionFile, or None if not found
        """
        results = await self.memory_router.fetch(
            {"worker_id": worker_id},
            collection="instruction_files",
            limit=1
        )
        
        if not results:
            return None
        
        result = results[0]
        content_data = result.get("content", {})
        
        try:
            return InstructionFile(
                worker_id=content_data.get("worker_id", ""),
                version=content_data.get("version", 1),
                content=content_data.get("content", ""),
                obsidian_path=content_data.get("obsidian_path", ""),
                created_at=datetime.fromisoformat(content_data.get("created_at", datetime.now().isoformat())),
                updated_at=datetime.fromisoformat(content_data.get("updated_at", datetime.now().isoformat()))
            )
        except Exception:
            return None
    
    async def get_instruction_changelog(
        self,
        worker_id: str
    ) -> list[InstructionChangelogEntry]:
        """Get the changelog for a worker's instruction file.
        
        Args:
            worker_id: Worker identifier
            
        Returns:
            List of changelog entries in chronological order
        """
        results = await self.memory_router.fetch(
            {"worker_id": worker_id},
            collection="instruction_changelogs",
            limit=100
        )
        
        changelog = []
        for result in results:
            content_data = result.get("content", {})
            try:
                entry = InstructionChangelogEntry(
                    worker_id=content_data.get("worker_id", ""),
                    version=content_data.get("version", 1),
                    trigger=content_data.get("trigger", ""),
                    diff_summary=content_data.get("diff_summary", ""),
                    rating_trend=content_data.get("rating_trend"),
                    created_at=datetime.fromisoformat(content_data.get("created_at", datetime.now().isoformat()))
                )
                changelog.append(entry)
            except Exception:
                continue
        
        # Sort by created_at ascending
        changelog.sort(key=lambda e: e.created_at)
        return changelog
    
    def _build_generation_prompt(self, profile: DynamicWorkerProfile) -> str:
        """Build LLM prompt for instruction file generation."""
        prompt = f"""Generate an instruction file for a worker with the following profile:

Worker Name: {profile.name}
Purpose: {profile.purpose}
Capabilities: {', '.join(profile.capabilities)}
Preferred Models: {', '.join(profile.preferred_models)}
Performance Score: {profile.performance_score}

Generate a markdown instruction file with the following structure:
# {profile.name} — Instruction File
**Version**: 1
**Generated**: {datetime.now().strftime('%Y-%m-%d')}

## Role
[Describe the worker's role based on its purpose]

## Goal
[Primary objective]

## Capabilities
[List the capabilities from the profile]

## Constraints
[What this worker must never do]

## Output Format
[Expected output structure]

## Model-Specific Optimisations
[Tailored guidance based on preferred models]

## Examples
[2-3 example task/response pairs]

Keep the instruction file concise but comprehensive. Focus on practical guidance."""
        return prompt
    
    def _build_update_prompt(
        self,
        profile: DynamicWorkerProfile,
        existing_content: str,
        trigger: str,
        rating_trend: float | None
    ) -> str:
        """Build LLM prompt for instruction file update."""
        trend_info = f"Rating trend: {rating_trend:.2f}" if rating_trend else "No rating data available"
        
        prompt = f"""Update the following instruction file for a worker:

Worker Name: {profile.name}
Purpose: {profile.purpose}
Capabilities: {', '.join(profile.capabilities)}
Preferred Models: {', '.join(profile.preferred_models)}
Performance Score: {profile.performance_score}
{trend_info}

Update Trigger: {trigger}

Existing Instruction File:
{existing_content}

Generate an updated instruction file with the same structure. Incorporate insights from the rating trend and the update trigger. Maintain version number in the header but increment it in your response."""
        return prompt
    
    def _build_diff_summary_prompt(self, old_content: str, new_content: str) -> str:
        """Build LLM prompt for diff summary generation."""
        prompt = f"""Generate a concise summary of the differences between these two instruction files:

OLD:
{old_content[:1000]}...

NEW:
{new_content[:1000]}...

Provide a 1-2 sentence summary of what changed."""
        return prompt
    
    def _get_obsidian_instruction_path(self, worker_id: str) -> str:
        """Get the Obsidian path for an instruction file."""
        if self.obsidian_vault_path:
            return str(self.obsidian_vault_path / "workers" / f"{worker_id}_INSTRUCTION.md")
        return f"workers/{worker_id}_INSTRUCTION.md"
    
    def _get_obsidian_changelog_path(self, worker_id: str) -> str:
        """Get the Obsidian path for a changelog file."""
        if self.obsidian_vault_path:
            return str(self.obsidian_vault_path / "workers" / f"{worker_id}_INSTRUCTION_CHANGELOG.md")
        return f"workers/{worker_id}_INSTRUCTION_CHANGELOG.md"
    
    async def _write_to_obsidian(self, instruction_file: InstructionFile) -> None:
        """Write instruction file to Obsidian vault."""
        if not self.obsidian_vault_path:
            return
        
        obsidian_path = Path(instruction_file.obsidian_path)
        obsidian_path.parent.mkdir(parents=True, exist_ok=True)
        
        obsidian_path.write_text(instruction_file.content, encoding='utf-8')
    
    async def _write_changelog_to_obsidian(self, worker_id: str, changelog: list[InstructionChangelogEntry]) -> None:
        """Write changelog to Obsidian vault."""
        if not self.obsidian_vault_path:
            return
        
        obsidian_path = Path(self._get_obsidian_changelog_path(worker_id))
        obsidian_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = f"# Instruction File Changelog: {worker_id}\n\n"
        
        for entry in changelog:
            trend_info = f" (trend: {entry.rating_trend:.2f})" if entry.rating_trend else ""
            content += f"## Version {entry.version} — {entry.created_at.strftime('%Y-%m-%d %H:%M')}{trend_info}\n"
            content += f"**Trigger**: {entry.trigger}\n"
            content += f"**Summary**: {entry.diff_summary}\n\n"
        
        obsidian_path.write_text(content, encoding='utf-8')
