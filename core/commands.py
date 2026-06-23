"""Core command registry and action system for interface-agnostic operations.

This module provides a shared command layer that can be used by:
- CLI (interactive TUI + non-interactive)
- Web GUI (FastAPI + WebSockets)
- Standalone GUI (desktop app)

All interfaces share the same command registry, ensuring backwards compatibility.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime

if TYPE_CHECKING:
    from orchestrator.improvement_loop import ImprovementLoopOrchestrator


class CommandType(str, Enum):
    """Types of commands available in the system."""
    QUERY = "query"  # Ask the AI a question
    GENERATE = "generate"  # Generate code/content
    ANALYZE = "analyze"  # Analyze code/project
    REFINE = "refine"  # Refine existing content
    EXPLAIN = "explain"  # Explain code/concepts
    DEBUG = "debug"  # Debug code
    TEST = "test"  # Run tests
    DEPLOY = "deploy"  # Deploy code
    CONFIG = "config"  # Configure system
    MEMORY = "memory"  # Memory operations
    SESSION = "session"  # Session management
    HELP = "help"  # Show help
    EXIT = "exit"  # Exit the interface
    CLEAR = "clear"  # Clear screen/history
    MODEL = "model"  # Switch models
    ADAPTER = "adapter"  # Switch adapters
    THEME = "theme"  # Change theme
    STATUS = "status"  # Show status
    IMPROVE = "improve"  # Trigger improvement loop


class CommandContext(BaseModel):
    """Context for command execution."""
    interface_type: str = Field(description="Type of interface: cli, web, standalone")
    session_id: Optional[str] = Field(default=None, description="Current session ID")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    working_directory: str = Field(description="Current working directory")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CommandResult(BaseModel):
    """Result of command execution."""
    success: bool = Field(description="Whether command succeeded")
    message: str = Field(description="Human-readable result message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Structured result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    duration_ms: Optional[int] = Field(default=None, description="Execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.now)


class Command(BaseModel):
    """A command that can be executed."""
    command_type: CommandType = Field(description="Type of command")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    kwargs: Dict[str, Any] = Field(default_factory=dict, description="Named parameters")
    context: Optional[CommandContext] = Field(default=None, description="Execution context")


class CommandHandler(ABC):
    """Abstract base class for command handlers."""

    def __init__(self) -> None:
        """Initialize the command handler with a default trace emitter."""
        from core.observability import MemoryTraceEmitter, TraceEmitter
        self.emitter: TraceEmitter = MemoryTraceEmitter()

    @abstractmethod
    async def execute(self, command: Command) -> CommandResult:
        """Execute the command and return a result."""
        pass
    
    @abstractmethod
    def get_help(self) -> str:
        """Return help text for this command."""
        pass
    
    @abstractmethod
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        pass


class ImproveCommandHandler(CommandHandler):
    """Handler for the IMPROVE command - triggers the improvement loop."""

    def __init__(self) -> None:
        """Initialize the command handler with a default trace emitter."""
        super().__init__()
        self._improvement_orchestrator: Optional["ImprovementLoopOrchestrator"] = None

    def set_improvement_orchestrator(self, orchestrator: "ImprovementLoopOrchestrator") -> None:
        """Set the improvement loop orchestrator instance (dependency injection)."""
        self._improvement_orchestrator = orchestrator

    async def execute(self, command: Command) -> CommandResult:
        """Execute the improve command by routing to the improvement loop orchestrator.

        Args:
            command: Command with optional kwargs["task_id"] for targeted improvement,
                     or kwargs["recent_count"] for batch improvement over last N tasks.

        Returns:
            CommandResult with improvement task results.
        """
        if self._improvement_orchestrator is None:
            return CommandResult(
                success=False,
                message="Improvement loop orchestrator not configured",
                error="ImprovementLoopOrchestrator not set. Call set_improvement_orchestrator() first."
            )

        task_id = command.kwargs.get("task_id")
        recent_count = command.kwargs.get("recent_count", 10)

        try:
            result = await self._improvement_orchestrator.process_improvement_task(
                task_id=task_id,
                recent_count=recent_count
            )

            return CommandResult(
                success=True,
                message="Improvement task completed",
                data=result
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"Improvement task failed: {str(e)}",
                error=str(e)
            )

    def get_help(self) -> str:
        """Return help text for the improve command."""
        return (
            "/improve [task_id] [recent_count]\n"
            "Trigger the improvement loop to evaluate and improve task performance.\n"
            "  task_id: Optional specific task ID to evaluate\n"
            "  recent_count: Number of recent tasks to evaluate (default: 10)"
        )

    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Improve",
            "description": "Trigger improvement loop",
            "icon": "sparkles",
            "category": "system"
        }


T = TypeVar('T', bound=CommandHandler)


class CommandRegistry:
    """Registry for all available commands.
    
    This registry is shared across all interfaces (CLI, Web GUI, Standalone GUI)
    to ensure backwards compatibility and consistent behavior.
    """
    
    def __init__(self) -> None:
        self._handlers: Dict[CommandType, CommandHandler] = {}
        self._aliases: Dict[str, CommandType] = {}
    
    def register(self, command_type: CommandType, handler: CommandHandler) -> None:
        """Register a command handler."""
        self._handlers[command_type] = handler
    
    def register_alias(self, alias: str, command_type: CommandType) -> None:
        """Register a command alias (e.g., '/' commands)."""
        self._aliases[alias] = command_type
    
    def get_handler(self, command_type: CommandType) -> Optional[CommandHandler]:
        """Get handler for a command type."""
        return self._handlers.get(command_type)
    
    def resolve_alias(self, alias: str) -> Optional[CommandType]:
        """Resolve an alias to a command type."""
        return self._aliases.get(alias)
    
    def get_all_commands(self) -> List[CommandType]:
        """Get all registered command types."""
        return list(self._handlers.keys())
    
    def get_all_menu_items(self) -> List[Dict[str, Any]]:
        """Get all menu items for GUI interfaces.
        
        This ensures CLI menu items are available in Web GUI and Standalone GUI.
        """
        menu_items = []
        for command_type, handler in self._handlers.items():
            menu_item = handler.get_menu_item()
            menu_item["command_type"] = command_type.value
            menu_items.append(menu_item)
        return menu_items
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute a command using the registered handler."""
        handler = self.get_handler(command.command_type)
        if handler is None:
            return CommandResult(
                success=False,
                message=f"Unknown command: {command.command_type}",
                error=f"No handler registered for {command.command_type}"
            )
        
        return await handler.execute(command)


# Global command registry instance
# NOTE: This is a known violation of the "No global state" architecture law.
# Refactoring to dependency injection would require significant changes across
# the codebase. This is documented for future cleanup.
_global_registry: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    """Get the global command registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = CommandRegistry()
    return _global_registry


def register_command(command_type: CommandType, handler: CommandHandler) -> None:
    """Register a command with the global registry."""
    registry = get_command_registry()
    registry.register(command_type, handler)


def register_command_alias(alias: str, command_type: CommandType) -> None:
    """Register a command alias with the global registry."""
    registry = get_command_registry()
    registry.register_alias(alias, command_type)


# Register the IMPROVE command
register_command(CommandType.IMPROVE, ImproveCommandHandler())
register_command_alias("/improve", CommandType.IMPROVE)
