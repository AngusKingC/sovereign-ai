"""
Authentication manager for token-based auth.

Single responsibility: Manage auth token lifecycle — generation, storage,
validation, and rotation. Token stored in .env file, never in config YAML.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

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


class AuthToken(BaseModel):
    """Auth token metadata."""
    token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    rotated_at: datetime | None = None


class AuthManager:
    """Manages auth token lifecycle — generation, storage, validation, rotation."""

    def __init__(
        self,
        env_path: str = ".env",
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the auth manager.
        
        Args:
            env_path: Path to .env file
            emitter: Trace emitter for observability
        """
        self._env_path = env_path
        self._emitter = emitter or MemoryTraceEmitter()
        self._token: str | None = None

    async def get_or_create_token(self) -> str:
        """Get or create auth token.
        
        Reads JARVIS_AUTH_TOKEN from .env file. If not present, generates
        a new token, writes it to .env, and stores in self._token.
        
        Returns:
            The token string
        """
        env = self._read_env()
        token = env.get("JARVIS_AUTH_TOKEN")
        
        if token:
            self._token = token
            try:
                event = TraceEvent(
                    event_type=TraceEventType.AUTH_TOKEN_LOADED,
                    component=TraceComponent.AUTH,
                    level=TraceLevel.INFO,
                    message="Auth token loaded from .env",
                    data={"token_present": True},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass  # Trace failure should not abort operation
        else:
            token = secrets.token_urlsafe(32)
            self._token = token
            env["JARVIS_AUTH_TOKEN"] = token
            self._write_env(env)
            try:
                event = TraceEvent(
                    event_type=TraceEventType.AUTH_TOKEN_CREATED,
                    component=TraceComponent.AUTH,
                    level=TraceLevel.WARNING,
                    message="Auth token generated and written to .env",
                    data={"token_present": True},
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                pass  # Trace failure should not abort operation
        
        return token

    async def validate_token(self, provided: str) -> bool:
        """Validate provided token against stored token.
        
        Uses timing-safe comparison to prevent timing attacks.
        
        Args:
            provided: The token provided by the client
            
        Returns:
            True if token is valid, False otherwise
        """
        if self._token is None:
            await self.get_or_create_token()
        
        is_valid = secrets.compare_digest(provided, self._token)
        
        try:
            event_type = TraceEventType.AUTH_TOKEN_VALIDATED if is_valid else TraceEventType.AUTH_TOKEN_REJECTED
            event = TraceEvent(
                event_type=event_type,
                component=TraceComponent.AUTH,
                level=TraceLevel.INFO,
                message="Token validation result",
                data={"valid": is_valid},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass  # Trace failure should not abort operation
        
        return is_valid

    async def rotate_token(self) -> str:
        """Rotate to a new token, invalidating the old one.
        
        Generates a new token, overwrites in .env, updates self._token.
        Old token is immediately invalid after this call.
        
        Returns:
            The new token string
        """
        new_token = secrets.token_urlsafe(32)
        self._token = new_token
        
        env = self._read_env()
        env["JARVIS_AUTH_TOKEN"] = new_token
        self._write_env(env)
        
        try:
            event = TraceEvent(
                event_type=TraceEventType.AUTH_TOKEN_ROTATED,
                component=TraceComponent.AUTH,
                level=TraceLevel.WARNING,
                message="Auth token rotated",
                data={"token_present": True},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass  # Trace failure should not abort operation
        
        return new_token

    def _read_env(self) -> dict[str, str]:
        """Read .env file as key=value pairs.
        
        Returns:
            Dictionary of key=value pairs, empty dict if file does not exist
        """
        try:
            with open(self._env_path, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return {}
        
        env = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
        
        return env

    def _write_env(self, values: dict[str, str]) -> None:
        """Write key=value pairs to .env file.
        
        Preserves existing entries not in values.
        
        Args:
            values: Dictionary of key=value pairs to write
        """
        existing = self._read_env()
        existing.update(values)
        
        with open(self._env_path, "w") as f:
            for key, value in existing.items():
                f.write(f"{key}={value}\n")
