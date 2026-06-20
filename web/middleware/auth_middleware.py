"""Auth middleware for FastAPI server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from core.auth import AuthManager
from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)

if TYPE_CHECKING:
    from core.observability import TraceEmitter

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for token-based authentication."""

    def __init__(self, app, auth_manager: AuthManager):
        """Initialize the auth middleware.
        
        Args:
            app: The ASGI application
            auth_manager: The auth manager instance
        """
        super().__init__(app)
        self._auth = auth_manager

    async def dispatch(self, request: Request, call_next) -> Response:
        """Dispatch request with authentication check.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response from call_next or 401 if authentication fails
        """
        # Exempt /health path from auth
        if request.url.path == "/health":
            return await call_next(request)

        # Extract bearer token from Authorization header
        auth_header = request.headers.get("Authorization")
        token = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

        # Also check WebSocket upgrade requests: token as query param
        if not token:
            token = request.query_params.get("token")

        # If token missing, return 401
        if not token:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        # Validate token
        is_valid = await self._auth.validate_token(token)

        if not is_valid:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        # Token valid, proceed with request
        return await call_next(request)


class SecretsAudit:
    """Audits config file for secrets that should be in .env only."""

    SECRET_KEYS = ["api_key", "token", "secret", "password", "key"]

    def __init__(self, config_path: str = "jarvis.config.yaml", emitter: TraceEmitter | None = None):
        """Initialize the secrets audit.
        
        Args:
            config_path: Path to config file
            emitter: Trace emitter for observability
        """
        self._config_path = config_path
        self._emitter = emitter or MemoryTraceEmitter()

    async def audit(self) -> list[str]:
        """Audit config file for secrets.
        
        Scans for any key whose name contains a word from SECRET_KEYS.
        
        Returns:
            List of offending key names (empty list = clean)
        """
        try:
            with open(self._config_path, "r") as f:
                content = f.read()
        except FileNotFoundError:
            return []

        offending_keys = []

        for secret_key in self.SECRET_KEYS:
            if secret_key.lower() in content.lower():
                # Find actual key names in the config
                lines = content.split("\n")
                for line in lines:
                    if ":" in line:
                        key_name = line.split(":")[0].strip()
                        if key_name and secret_key.lower() in key_name.lower():
                            if key_name not in offending_keys:
                                offending_keys.append(key_name)

        for key in offending_keys:
            print(f"WARNING: Secret key '{key}' found in config file. Should be in .env only.")
            try:
                event = TraceEvent(
                    event_type=TraceEventType.SECRETS_AUDIT_WARNING,
                    component=TraceComponent.SECURITY,
                    level=TraceLevel.WARNING,
                    message=f"Secret key found in config file: {key}",
                    data={"key": key},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception as e:
                logger.warning(f"Trace emission failed in secrets audit: {e}")  # Trace failure should not abort operation
                pass

        return offending_keys
