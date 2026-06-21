"""
Instruction file versioning and update management.

Version and update mechanism for instruction files. Updates are triggered when a worker's
rating trend drops below a threshold over N recent tasks. Proposed updates require user
approval. Rollback is available to any previous version.
"""

from datetime import datetime, timezone
from uuid import uuid4

from core.instruction_generator import InstructionGenerator
from core.rating_system import RatingSystem
from core.worker_factory import DynamicWorkerProfile
from core.memory_router import MemoryRouter
from core.approval_gate import ApprovalGate
from core.observability import MemoryTraceEmitter, TraceEmitter, TraceEvent, TraceEventType, TraceComponent, TraceLevel
from core.schemas import InstructionFile, VersionUpdateProposal


class InstructionVersionManager:
    """Manages instruction file versioning and updates with approval workflow."""
    
    def __init__(
        self,
        instruction_generator: InstructionGenerator,
        rating_system: RatingSystem,
        approval_gate: ApprovalGate,
        memory_router: MemoryRouter,
        emitter: TraceEmitter | None = None,
        trend_threshold: float = -0.5,
        min_ratings: int = 5
    ):
        """Initialize instruction version manager.
        
        Args:
            instruction_generator: InstructionGenerator for generating updates
            rating_system: RatingSystem for checking performance trends
            approval_gate: ApprovalGate for user approval workflow
            memory_router: MemoryRouter for storing proposals and version history
            emitter: TraceEmitter for observability (defaults to MemoryTraceEmitter)
            trend_threshold: Trigger update if trend below this value
            min_ratings: Minimum ratings before trend check
        """
        self.instruction_generator = instruction_generator
        self.rating_system = rating_system
        self.approval_gate = approval_gate
        self.memory_router = memory_router
        self.emitter = emitter if emitter is not None else MemoryTraceEmitter()
        self.trend_threshold = trend_threshold
        self.min_ratings = min_ratings
        self._pending_proposals: dict[str, VersionUpdateProposal] = {}
    
    async def check_and_trigger_update(
        self,
        profile: DynamicWorkerProfile
    ) -> VersionUpdateProposal | None:
        """Check if an instruction update is needed and trigger proposal if so.

        Args:
            profile: Worker profile to check for update eligibility

        Returns:
            VersionUpdateProposal if update needed, None otherwise
        """
        # Collision policy: only one PENDING proposal per worker at a time.
        # If a PENDING proposal exists (from rating-trend trigger or trace-score trigger),
        # return it immediately. New proposals queue only after the existing one is resolved.
        # This prevents duplicate proposals when both trigger paths fire simultaneously.
        if profile.worker_id in self._pending_proposals:
            existing_proposal = self._pending_proposals[profile.worker_id]
            try:
                await self.emitter.emit(TraceEvent(
                    event_type=TraceEventType.PROPOSAL_COLLISION_SKIPPED,
                    component=TraceComponent.INSTRUCTION_VERSIONING,
                    level=TraceLevel.INFO,
                    message=f"Skipped duplicate proposal for worker {profile.worker_id}",
                    data={"worker_id": profile.worker_id},
                    duration_ms=0
                ))
            except Exception:
                pass
            return existing_proposal

        # Check rating trend
        rating_trend = await self.rating_system.get_trend(profile.worker_id, window=10)
        
        # If trend is None or above threshold, no update needed
        if rating_trend is None:
            return None
        
        if rating_trend >= self.trend_threshold:
            return None
        
        # Check rating count
        ratings = await self.rating_system.get_ratings(profile.worker_id, limit=1000)
        if len(ratings) < self.min_ratings:
            return None
        
        # Retrieve current instruction file
        current_instruction = await self.instruction_generator.get_instruction_file(profile.worker_id)
        if not current_instruction:
            return None
        
        # Generate proposed updated content
        trigger_reason = f"rating trend {rating_trend:.2f} over last {len(ratings)} tasks"
        
        updated_instruction = await self.instruction_generator.update_instruction_file(
            profile=profile,
            existing=current_instruction,
            trigger=trigger_reason
        )
        
        # Create proposal
        proposal_id = str(uuid4())
        proposal = VersionUpdateProposal(
            proposal_id=proposal_id,
            worker_id=profile.worker_id,
            current_version=current_instruction.version,
            proposed_content=updated_instruction.content,
            trigger_reason=trigger_reason,
            rating_trend=rating_trend,
            status="pending",
            created_at=datetime.now(timezone.utc)
        )

        # Track pending proposal for collision prevention
        self._pending_proposals[profile.worker_id] = proposal
        
        # Store proposal
        await self.memory_router.write_to_collection(
            data={
                "type": "version_update_proposal",
                "proposal_id": proposal_id,
                "worker_id": profile.worker_id,
                "current_version": proposal.current_version,
                "proposed_content": proposal.proposed_content,
                "trigger_reason": proposal.trigger_reason,
                "rating_trend": proposal.rating_trend,
                "status": proposal.status,
                "created_at": proposal.created_at.isoformat()
            },
            collection="version_update_proposals"
        )
        
        # Submit to ApprovalGate
        await self.approval_gate.submit_for_approval(
            proposal_id=proposal_id,
            description=f"Update instruction file for {profile.worker_id}: {trigger_reason}",
            context={
                "worker_id": profile.worker_id,
                "current_version": proposal.current_version,
                "rating_trend": proposal.rating_trend
            }
        )
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Instruction update proposed for worker {profile.worker_id}",
                level=TraceLevel.INFO,
                data={
                    "worker_id": profile.worker_id,
                    "proposal_id": proposal_id,
                    "rating_trend": rating_trend,
                    "trigger_reason": trigger_reason
                }
            ))
        except Exception:
            pass
        
        return proposal
    
    async def approve_update(
        self,
        proposal: VersionUpdateProposal
    ) -> InstructionFile:
        """Approve and apply a proposed instruction update.
        
        Args:
            proposal: VersionUpdateProposal to approve
            
        Returns:
            New InstructionFile with applied update
            
        Raises:
            ValueError: If proposal status is not "pending"
        """
        # Verify proposal status
        if proposal.status != "pending":
            raise ValueError(f"Cannot approve proposal with status {proposal.status}")
        
        # Retrieve current instruction file
        current_instruction = await self.instruction_generator.get_instruction_file(proposal.worker_id)
        if not current_instruction:
            raise ValueError(f"No current instruction file found for worker {proposal.worker_id}")
        
        # Create updated instruction file with proposed content
        new_version = current_instruction.version + 1
        created_at = datetime.now(timezone.utc)
        
        new_instruction = InstructionFile(
            worker_id=proposal.worker_id,
            version=new_version,
            content=proposal.proposed_content,
            obsidian_path=current_instruction.obsidian_path,
            created_at=created_at,
            updated_at=created_at
        )
        
        # Store new instruction file
        await self.memory_router.write_to_collection(
            data={
                "type": "instruction_file",
                "worker_id": proposal.worker_id,
                "version": new_version,
                "content": proposal.proposed_content,
                "obsidian_path": current_instruction.obsidian_path,
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat()
            },
            collection="instruction_files"
        )
        
        # Update proposal status
        proposal = proposal.model_copy(update={"status": "approved"})
        await self.memory_router.write_to_collection(
            data={
                "type": "version_update_proposal",
                "proposal_id": proposal.proposal_id,
                "worker_id": proposal.worker_id,
                "current_version": proposal.current_version,
                "proposed_content": proposal.proposed_content,
                "trigger_reason": proposal.trigger_reason,
                "rating_trend": proposal.rating_trend,
                "status": proposal.status,
                "created_at": proposal.created_at.isoformat()
            },
            collection="version_update_proposals"
        )

        # Clear pending proposal tracking
        if proposal.worker_id in self._pending_proposals:
            del self._pending_proposals[proposal.worker_id]
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Instruction update approved for worker {proposal.worker_id}",
                level=TraceLevel.INFO,
                data={
                    "worker_id": proposal.worker_id,
                    "proposal_id": proposal.proposal_id,
                    "new_version": new_version
                }
            ))
        except Exception:
            pass
        
        return new_instruction

    async def reject_update(
        self,
        proposal: VersionUpdateProposal
    ) -> None:
        """Reject a proposed instruction update.

        Args:
            proposal: VersionUpdateProposal to reject

        Raises:
            ValueError: If proposal status is not "pending"
        """
        # Verify proposal status
        if proposal.status != "pending":
            raise ValueError(f"Cannot reject proposal with status {proposal.status}")

        # Update proposal status
        proposal = proposal.model_copy(update={"status": "rejected"})
        await self.memory_router.write_to_collection(
            data={
                "type": "version_update_proposal",
                "proposal_id": proposal.proposal_id,
                "worker_id": proposal.worker_id,
                "current_version": proposal.current_version,
                "proposed_content": proposal.proposed_content,
                "trigger_reason": proposal.trigger_reason,
                "rating_trend": proposal.rating_trend,
                "status": proposal.status,
                "created_at": proposal.created_at.isoformat()
            },
            collection="version_update_proposals"
        )

        # Clear pending proposal tracking
        if proposal.worker_id in self._pending_proposals:
            del self._pending_proposals[proposal.worker_id]

        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Instruction update rejected for worker {proposal.worker_id}",
                level=TraceLevel.INFO,
                data={
                    "worker_id": proposal.worker_id,
                    "proposal_id": proposal.proposal_id
                }
            ))
        except Exception:
            pass

    async def rollback(
        self,
        worker_id: str,
        target_version: int
    ) -> InstructionFile:
        """Rollback instruction file to a previous version.
        
        Args:
            worker_id: Worker identifier
            target_version: Version to rollback to
            
        Returns:
            New InstructionFile with rolled-back content
            
        Raises:
            ValueError: If target version does not exist
        """
        # Retrieve version history
        version_history = await self.get_version_history(worker_id)
        
        # Find target version
        target_instruction = None
        for instruction in version_history:
            if instruction.version == target_version:
                target_instruction = instruction
                break
        
        if not target_instruction:
            raise ValueError(f"Version {target_version} not found for worker {worker_id}")
        
        # Retrieve current instruction file
        current_instruction = await self.instruction_generator.get_instruction_file(worker_id)
        if not current_instruction:
            raise ValueError(f"No current instruction file found for worker {worker_id}")
        
        # Create new version with rolled-back content
        new_version = current_instruction.version + 1
        created_at = datetime.now(timezone.utc)
        
        rollback_instruction = InstructionFile(
            worker_id=worker_id,
            version=new_version,
            content=target_instruction.content,
            obsidian_path=current_instruction.obsidian_path,
            created_at=created_at,
            updated_at=created_at
        )
        
        # Store new instruction file
        await self.memory_router.write_to_collection(
            data={
                "type": "instruction_file",
                "worker_id": worker_id,
                "version": new_version,
                "content": target_instruction.content,
                "obsidian_path": current_instruction.obsidian_path,
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat()
            },
            collection="instruction_files"
        )
        
        # Create changelog entry for rollback
        await self.memory_router.write_to_collection(
            data={
                "type": "instruction_changelog",
                "worker_id": worker_id,
                "version": new_version,
                "trigger": f"rollback to v{target_version}",
                "diff_summary": f"Rolled back instruction file to version {target_version}",
                "rating_trend": None,
                "created_at": created_at.isoformat()
            },
            collection="instruction_changelogs"
        )
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Instruction file rolled back to v{target_version} for worker {worker_id}",
                level=TraceLevel.INFO,
                data={
                    "worker_id": worker_id,
                    "target_version": target_version,
                    "new_version": new_version
                }
            ))
        except Exception:
            pass
        
        return rollback_instruction
    
    async def get_version_history(
        self,
        worker_id: str
    ) -> list[InstructionFile]:
        """Get version history for a worker's instruction file.
        
        Args:
            worker_id: Worker identifier
            
        Returns:
            List of InstructionFile objects, oldest first
        """
        results = await self.memory_router.fetch_by_filter(
            filter={"worker_id": worker_id},
            collection="instruction_files",
            limit=1000
        )
        
        history = []
        for result in results:
            content_data = result.get("content", {})
            try:
                instruction = InstructionFile(
                    worker_id=content_data.get("worker_id", ""),
                    version=content_data.get("version", 1),
                    content=content_data.get("content", ""),
                    obsidian_path=content_data.get("obsidian_path", ""),
                    created_at=datetime.fromisoformat(content_data.get("created_at", datetime.now(timezone.utc).isoformat())),
                    updated_at=datetime.fromisoformat(content_data.get("updated_at", datetime.now(timezone.utc).isoformat()))
                )
                history.append(instruction)
            except Exception:
                continue
        
        # Sort by version ascending
        history.sort(key=lambda i: i.version)
        return history
