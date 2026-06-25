"""
Skill Registry - discovers, validates, and registers skill plugins.

Single responsibility: Maintain a registry of all available skills,
enabling dynamic discovery and instantiation of worker capabilities.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.observability import (
    MemoryTraceEmitter,
    TraceComponent,
    TraceEmitter,
    TraceEvent,
    TraceEventType,
    TraceLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class SkillMetadata:
    """Metadata for a skill plugin."""

    name: str
    description: str
    parameters: dict[str, Any]
    output_format: str
    dependencies: list[str]
    hardware: str
    tags: list[str]
    skill_path: str


class SkillRegistry:
    """Registry for skill plugins."""

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the skill registry."""
        self.emitter = emitter or MemoryTraceEmitter()
        self._skills: dict[str, SkillMetadata] = {}
        self._skills_dir = Path(__file__).parent.parent / "skills"

    async def discover_skills(self) -> dict[str, SkillMetadata]:
        """
        Discover skills by scanning skills/ directory for SKILL.md files.

        Returns:
            Dictionary mapping skill names to their metadata
        """
        if not self._skills_dir.exists():
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ORCHESTRATOR,
                    message="Skills directory does not exist",
                    level=TraceLevel.WARNING,
                    data={
                        "error": "Skills directory does not exist",
                        "path": str(self._skills_dir),
                    },
                    duration_ms=0,
                )
                await self.emitter.emit(event)
            except Exception as e:
                logger.warning("Trace emission failed: %s", e)
            return {}

        discovered = {}

        for skill_dir in self._skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue

            skill_md_path = skill_dir / "SKILL.md"
            if not skill_md_path.exists():
                continue

            try:
                metadata = await self._parse_skill_md(skill_md_path, skill_dir)
                if metadata:
                    discovered[metadata.name] = metadata
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.ORCHESTRATOR,
                        message="Failed to parse skill directory",
                        level=TraceLevel.ERROR,
                        data={
                            "error": str(e),
                            "skill_dir": str(skill_dir),
                        },
                        duration_ms=0,
                    )
                    await self.emitter.emit(event)
                except Exception as e2:
                    logger.warning("Trace emission failed: %s", e2)

        self._skills = discovered

        try:
            event = TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                message="Skills discovery completed",
                level=TraceLevel.INFO,
                data={
                    "skills_discovered": len(discovered),
                    "skill_names": list(discovered.keys()),
                },
                duration_ms=0,
            )
            await self.emitter.emit(event)
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)

        return discovered

    async def _parse_skill_md(
        self, skill_md_path: Path, skill_dir: Path
    ) -> SkillMetadata | None:
        """
        Parse SKILL.md file and extract metadata.

        Args:
            skill_md_path: Path to SKILL.md file
            skill_dir: Path to skill directory

        Returns:
            SkillMetadata if parsing succeeds, None otherwise
        """
        loop = asyncio.get_event_loop()

        # Uses run_in_executor rather than aiofiles to avoid adding a new dependency for a single call site
        def read_file() -> str:
            with open(skill_md_path, "r") as f:
                return f.read()

        content = await loop.run_in_executor(None, read_file)

        # Simple parsing - extract key sections
        # In a production system, this would use a proper markdown parser
        name = skill_dir.name
        description = ""
        parameters = {}
        output_format = ""
        dependencies = []
        hardware = ""
        tags = []

        lines = content.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith("## "):
                current_section = line[3:].lower()
            elif current_section == "description" and line:
                description = line
            elif current_section == "parameters" and line.startswith("-"):
                # Parse parameter line
                param_line = line[1:].strip()
                parts = param_line.split(":")
                if len(parts) >= 2:
                    param_name = parts[0].strip()
                    param_info = ":".join(parts[1:]).strip()
                    parameters[param_name] = param_info
            elif current_section == "output" and line:
                output_format = line
            elif current_section == "dependencies" and line.startswith("-"):
                dep = line[1:].strip()
                if dep:
                    dependencies.append(dep)
            elif current_section == "hardware" and line:
                hardware = line
            elif current_section == "tags" and line.startswith("-"):
                tag = line[1:].strip()
                if tag:
                    tags.append(tag)

        return SkillMetadata(
            name=name,
            description=description,
            parameters=parameters,
            output_format=output_format,
            dependencies=dependencies,
            hardware=hardware,
            tags=tags,
            skill_path=str(skill_dir),
        )

    async def validate_skill(self, metadata: SkillMetadata) -> bool:
        """
        Validate a skill against the plugin specification.

        Args:
            metadata: Skill metadata to validate

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not metadata.name:
            return False
        if not metadata.description:
            return False
        if not metadata.output_format:
            return False

        # Check that skill.py exists
        skill_py_path = Path(metadata.skill_path) / "skill.py"
        if not skill_py_path.exists():
            return False

        return True

    def get_skill(self, name: str) -> SkillMetadata | None:
        """
        Get skill metadata by name.

        Args:
            name: Skill name

        Returns:
            SkillMetadata if found, None otherwise
        """
        return self._skills.get(name)

    def query_by_capability(self, capability: str) -> list[SkillMetadata]:
        """
        Query skills by capability (tag).

        Args:
            capability: Capability tag to search for

        Returns:
            List of matching skills
        """
        return [skill for skill in self._skills.values() if capability in skill.tags]

    def query_by_task_type(self, task_type: str) -> list[SkillMetadata]:
        """
        Query skills by task type.

        Args:
            task_type: Task type to search for

        Returns:
            List of matching skills
        """
        # For now, this is a simple tag-based query
        # In production, this would be more sophisticated
        return [
            skill for skill in self._skills.values() if task_type.lower() in skill.tags
        ]

    def query_by_dependency(self, dependency: str) -> list[SkillMetadata]:
        """
        Query skills by dependency.

        Args:
            dependency: Dependency to search for

        Returns:
            List of matching skills
        """
        return [
            skill for skill in self._skills.values() if dependency in skill.dependencies
        ]

    def all_skills(self) -> dict[str, SkillMetadata]:
        """
        Get all registered skills.

        Returns:
            Dictionary mapping skill names to metadata
        """
        return self._skills.copy()
