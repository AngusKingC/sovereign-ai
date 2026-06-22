"""HTTP client skill for making HTTP requests."""

import asyncio
import httpx
from typing import Any
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class HttpClientSkill:
    """HTTP client skill for making HTTP requests."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize the HTTP client skill.

        Args:
            emitter: Trace emitter for observability
            approval_gate: Approval gate for write operations
            timeout: Timeout for HTTP requests in seconds
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate
        self.timeout = timeout

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform HTTP GET request.

        Args:
            url: URL to request
            headers: HTTP headers
            params: Query parameters

        Returns:
            Dict with status_code, body, and headers.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.HTTP_REQUEST,
                component=TraceComponent.HTTP_CLIENT_SKILL,
                level=TraceLevel.INFO,
                message="HTTP GET request",
                data={"method": "GET", "url": url},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, params=params)

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.HTTP_REQUEST,
                component=TraceComponent.HTTP_CLIENT_SKILL,
                level=TraceLevel.INFO,
                message="HTTP GET completed",
                data={"method": "GET", "url": url, "status_code": response.status_code},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "status_code": response.status_code,
            "body": response.text,
            "headers": dict(response.headers),
        }

    async def post(
        self,
        url: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform HTTP POST request.

        Args:
            url: URL to request
            body: Request body
            headers: HTTP headers

        Returns:
            Dict with status_code, body, and headers.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.NETWORK_REQUEST,
                action_description="http post",
                action_parameters={"url": url},
                risk_level="medium",
                reason_for_approval="HTTP POST requires approval per policy",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "status_code": 403,
                    "body": "POST denied by approval gate",
                    "headers": {},
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.HTTP_REQUEST,
                component=TraceComponent.HTTP_CLIENT_SKILL,
                level=TraceLevel.INFO,
                message="HTTP POST request",
                data={"method": "POST", "url": url},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=body, headers=headers)

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.HTTP_REQUEST,
                component=TraceComponent.HTTP_CLIENT_SKILL,
                level=TraceLevel.INFO,
                message="HTTP POST completed",
                data={"method": "POST", "url": url, "status_code": response.status_code},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "status_code": response.status_code,
            "body": response.text,
            "headers": dict(response.headers),
        }

    async def put(
        self,
        url: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform HTTP PUT request.

        Args:
            url: URL to request
            body: Request body
            headers: HTTP headers

        Returns:
            Dict with status_code, body, and headers.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.NETWORK_REQUEST,
                action_description="http put",
                action_parameters={"url": url},
                risk_level="medium",
                reason_for_approval="HTTP PUT requires approval per policy",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "status_code": 403,
                    "body": "PUT denied by approval gate",
                    "headers": {},
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.HTTP_REQUEST,
                component=TraceComponent.HTTP_CLIENT_SKILL,
                level=TraceLevel.INFO,
                message="HTTP PUT request",
                data={"method": "PUT", "url": url},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(url, json=body, headers=headers)

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.HTTP_REQUEST,
                component=TraceComponent.HTTP_CLIENT_SKILL,
                level=TraceLevel.INFO,
                message="HTTP PUT completed",
                data={"method": "PUT", "url": url, "status_code": response.status_code},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "status_code": response.status_code,
            "body": response.text,
            "headers": dict(response.headers),
        }

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform HTTP DELETE request.

        Args:
            url: URL to request
            headers: HTTP headers

        Returns:
            Dict with status_code, body, and headers.
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.NETWORK_REQUEST,
                action_description="http delete",
                action_parameters={"url": url},
                risk_level="medium",
                reason_for_approval="HTTP DELETE requires approval per policy",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "status_code": 403,
                    "body": "DELETE denied by approval gate",
                    "headers": {},
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.HTTP_REQUEST,
                component=TraceComponent.HTTP_CLIENT_SKILL,
                level=TraceLevel.INFO,
                message="HTTP DELETE request",
                data={"method": "DELETE", "url": url},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(url, headers=headers)

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.HTTP_REQUEST,
                component=TraceComponent.HTTP_CLIENT_SKILL,
                level=TraceLevel.INFO,
                message="HTTP DELETE completed",
                data={"method": "DELETE", "url": url, "status_code": response.status_code},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "status_code": response.status_code,
            "body": response.text,
            "headers": dict(response.headers),
        }
