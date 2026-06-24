"""
Home Assistant Skill - integrates with Home Assistant via REST API.

Single responsibility: Control Home Assistant entities and fetch states.
"""

import os
from typing import Any
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

from core.approval_gate import ApprovalRequest, ApprovalActionType, ApprovalGate
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)
from core.exceptions import SkillExecutionError, ApprovalDeniedError


class HomeAssistantSkill:
    """Skill for interacting with Home Assistant."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        approval_gate: "ApprovalGate | None" = None,
    ) -> None:
        """Initialize the Home Assistant skill."""
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self._base_url = os.getenv("HA_BASE_URL")
        self._token = os.getenv("HA_TOKEN")

    async def get_states(self) -> list[dict]:
        """
        Fetch all entity states from Home Assistant.

        Returns:
            List of entity state dictionaries

        Raises:
            SkillExecutionError: If HA is unreachable or returns error
        """
        if not self._base_url or not self._token:
            raise SkillExecutionError(
                "home_assistant",
                "HA_BASE_URL and HA_TOKEN environment variables must be set"
            )

        try:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/states",
                    headers=headers
                )
                response.raise_for_status()
                states = response.json()

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message="Fetched all Home Assistant states",
                    data={
                        "skill": "home_assistant",
                        "entity_count": len(states),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return states

        except httpx.HTTPError as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Failed to fetch Home Assistant states",
                    data={
                        "skill": "home_assistant",
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            raise SkillExecutionError("home_assistant", f"Failed to fetch states: {str(e)}")

    async def get_state(self, entity_id: str) -> dict:
        """
        Fetch a single entity state from Home Assistant.

        Args:
            entity_id: The entity ID to fetch

        Returns:
            Entity state dictionary

        Raises:
            SkillExecutionError: If HA is unreachable or entity not found
        """
        if not self._base_url or not self._token:
            raise SkillExecutionError(
                "home_assistant",
                "HA_BASE_URL and HA_TOKEN environment variables must be set"
            )

        try:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/states/{entity_id}",
                    headers=headers
                )
                if response.status_code == 404:
                    raise SkillExecutionError(
                        "home_assistant",
                        f"Entity '{entity_id}' not found"
                    )
                response.raise_for_status()
                state = response.json()

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message=f"Fetched Home Assistant state for {entity_id}",
                    data={
                        "skill": "home_assistant",
                        "entity_id": entity_id,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return state

        except httpx.HTTPError as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message=f"Failed to fetch state for {entity_id}",
                    data={
                        "skill": "home_assistant",
                        "entity_id": entity_id,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            raise SkillExecutionError("home_assistant", f"Failed to fetch state: {str(e)}")

    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        **kwargs: Any,
    ) -> bool:
        """
        Call a Home Assistant service.

        Args:
            domain: The service domain (e.g., "light", "switch")
            service: The service name (e.g., "turn_on", "turn_off")
            entity_id: The entity ID to call the service on
            **kwargs: Additional service parameters

        Returns:
            True if service call succeeded

        Raises:
            SkillExecutionError: If HA is unreachable or service call fails
            ApprovalDeniedError: If approval is denied
        """
        from core.approval_gate import ApprovalGate

        if not self._base_url or not self._token:
            raise SkillExecutionError(
                "home_assistant",
                "HA_BASE_URL and HA_TOKEN environment variables must be set"
            )

        # Request approval before executing service
        if self._approval_gate:
            approval_gate = self._approval_gate
        else:
            from core.approval_gate import ApprovalGate
            approval_gate = ApprovalGate(emitter=self._emitter, state_machine=None, memory_router=None)  # type: ignore[arg-type]
        action_description = f"Call Home Assistant service {domain}.{service} on {entity_id}"
        try:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.NETWORK_REQUEST,
                action_description=action_description,
                action_parameters={"domain": domain, "service": service, "entity_id": entity_id, **kwargs},
                risk_level="medium",
                reason_for_approval="Home Assistant service call requires approval per policy",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            )
            response = await approval_gate.request_approval(request)
            if not response.approved:
                raise ApprovalDeniedError(action_description)
        except ApprovalDeniedError:
            raise

        try:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }
            service_data = {"entity_id": entity_id, **kwargs}
            async with httpx.AsyncClient() as client:
                http_response = await client.post(
                    f"{self._base_url}/api/services/{domain}/{service}",
                    headers=headers,
                    json=service_data,
                )
                http_response.raise_for_status()

            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    message=f"Called Home Assistant service {domain}.{service} on {entity_id}",
                    data={
                        "skill": "home_assistant",
                        "domain": domain,
                        "service": service,
                        "entity_id": entity_id,
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass

            return True

        except httpx.HTTPError as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message=f"Failed to call service {domain}.{service}",
                    data={
                        "skill": "home_assistant",
                        "domain": domain,
                        "service": service,
                        "entity_id": entity_id,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            raise SkillExecutionError("home_assistant", f"Failed to call service: {str(e)}")
