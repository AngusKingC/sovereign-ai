"""
Command history management for CLI.

Single responsibility: Manage command history with persistence and completion.
Provides PostgreSQL persistence via PostgresBackend when configured,
with in-memory fallback when no DB is available.
"""

import os
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from core.memory_router import MemoryBackend
from core.commands import CommandType


class CommandHistory:
    """Manager for command history with persistence and completion."""

    def __init__(
        self,
        backend: MemoryBackend | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        max_history: int = 1000,
    ) -> None:
        """Initialize the command history manager.

        Args:
            backend: Optional memory backend for persistence.
                     If None, uses in-memory storage (list).
            session_id: Optional session ID for scoping history.
            user_id: Optional user ID for scoping history.
            max_history: Maximum number of commands to keep in history.
        """
        self.backend = backend
        self.session_id = session_id
        self.user_id = user_id
        self.max_history = max_history
        self._in_memory: list[dict[str, Any]] = []
        self._history_index: int = -1  # For up/down navigation
        self._current_input: str = ""  # Current input being edited

    async def add_command(self, command: str) -> None:
        """Add a command to history.

        Args:
            command: The command string to add.
        """
        timestamp = datetime.now()
        entry = {
            "command": command,
            "timestamp": timestamp.isoformat(),
            "session_id": self.session_id,
            "user_id": self.user_id,
        }

        if self.backend:
            # Store in backend
            await self.backend.write({
                "type": "command_history",
                "session_id": self.session_id,
                "user_id": self.user_id,
                "command": command,
                "timestamp": timestamp.isoformat(),
            })
        else:
            # Store in memory
            self._in_memory.append(entry)
            # Trim to max_history
            if len(self._in_memory) > self.max_history:
                self._in_memory = self._in_memory[-self.max_history:]

        # Reset navigation index
        self._history_index = -1
        self._current_input = ""

    async def get_history(self) -> list[dict[str, Any]]:
        """Get command history for the current session/user.

        Returns:
            List of command entries in chronological order.
        """
        if self.backend:
            try:
                # Fetch from backend
                from core.schemas import Task
                intent_parts = ["command_history"]
                if self.session_id:
                    intent_parts.append(f"session:{self.session_id}")
                if self.user_id:
                    intent_parts.append(f"user:{self.user_id}")
                intent = ":".join(intent_parts)
                
                task = Task(
                    task_id=uuid4(),
                    intent=intent,
                    complexity_score=0.0,
                    priority="normal",
                    current_state="received",
                    created_at=datetime.now(),
                )
                results = await self.backend.fetch(task)
                # Sort by timestamp
                results.sort(key=lambda x: x.get("content", {}).get("timestamp", ""))
                return results
            except Exception:
                return []
        else:
            # Return in-memory history
            return self._in_memory

    async def search_history(self, query: str) -> list[str]:
        """Search command history for commands matching query.

        Args:
            query: Search query string.

        Returns:
            List of matching command strings.
        """
        history = await self.get_history()
        matching = []
        for entry in history:
            content = entry.get("content", {})
            command = content.get("command", "")
            if query.lower() in command.lower():
                matching.append(command)
        return matching

    def navigate_up(self, current_input: str) -> str:
        """Navigate up through command history.

        Args:
            current_input: Current input being edited.

        Returns:
            Previous command in history, or current_input if at beginning.
        """
        if self._history_index == -1:
            # First navigation - save current input
            self._current_input = current_input
            self._history_index = 0
        else:
            self._history_index += 1

        # Get history (synchronously for navigation)
        if self.backend:
            # For backend, we'd need to fetch asynchronously
            # For now, use in-memory cache for navigation
            history = self._in_memory
        else:
            history = self._in_memory

        if self._history_index >= len(history):
            # At end of history
            self._history_index = len(history) - 1
            return history[-1]["command"] if history else current_input

        # Navigate from end of history
        actual_index = len(history) - 1 - self._history_index
        if actual_index < 0:
            return self._current_input

        return history[actual_index]["command"]

    def navigate_down(self, current_input: str) -> str:
        """Navigate down through command history.

        Args:
            current_input: Current input being edited.

        Returns:
            Next command in history, or current_input if at end.
        """
        if self._history_index == -1:
            return current_input

        self._history_index -= 1

        if self._history_index < 0:
            # Back to current input
            self._history_index = -1
            return self._current_input

        # Get history
        if self.backend:
            history = self._in_memory
        else:
            history = self._in_memory

        # Navigate from end of history
        actual_index = len(history) - 1 - self._history_index
        if actual_index < 0:
            return self._current_input

        return history[actual_index]["command"]

    def reset_navigation(self) -> None:
        """Reset navigation state."""
        self._history_index = -1
        self._current_input = ""

    async def get_completions(
        self,
        prefix: str,
        command_types: list[CommandType] | None = None,
    ) -> list[str]:
        """Get tab completions for a given prefix.

        Args:
            prefix: The prefix to complete.
            command_types: Optional list of command types to include.

        Returns:
            List of completion suggestions.
        """
        completions = []

        # Command completions
        if command_types is None:
            command_types = list(CommandType)

        for cmd_type in command_types:
            cmd_name = cmd_type.value if isinstance(cmd_type.value, str) else str(cmd_type.value)
            if cmd_name.startswith(prefix) or prefix.startswith(cmd_name):
                completions.append(f"/{cmd_name}")

        # Adapter completions
        from cli.adapter_factory import create_adapter
        available_adapters = ["ollama", "lm_studio"]
        for adapter in available_adapters:
            if adapter.startswith(prefix):
                completions.append(adapter)

        # Model completions (common models)
        common_models = ["llama3", "llama2", "mistral", "gemma", "phi"]
        for model in common_models:
            if model.startswith(prefix):
                completions.append(model)

        # History completions
        history = await self.get_history()
        for entry in history:
            content = entry.get("content", {})
            command = content.get("command", "")
            if command.startswith(prefix) and command not in completions:
                completions.append(command)

        return sorted(set(completions))

    async def close(self) -> None:
        """Close the command history manager and backend."""
        if self.backend and hasattr(self.backend, 'close'):
            await self.backend.close()
        self._in_memory.clear()

