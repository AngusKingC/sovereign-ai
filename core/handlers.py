"""Command handlers for the Sovereign AI Agent Framework.

These handlers implement the actual logic for each command type.
They are interface-agnostic and can be used by CLI, Web GUI, and Standalone GUI.
"""

import asyncio
import time
from typing import Dict, Any
from core.commands import (
    Command,
    CommandContext,
    CommandHandler,
    CommandResult,
    CommandType,
)
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEmitter,
    TraceEvent,
)
from core.schemas import Message, MessageRole, Task, TaskPriority, TaskStatus
from core.session import SessionManager


def register_default_handlers(
    orchestrator: "Orchestrator | None" = None,
    session_manager: SessionManager | None = None,
    input_sanitiser: "InputSanitiser | None" = None,
) -> None:
    """Register all default command handlers.
    
    Args:
        orchestrator: Optional Orchestrator instance for QueryHandler.
                      If None, QueryHandler will not be registered.
        session_manager: Optional session manager for conversation history.
        input_sanitiser: Optional InputSanitiser for sanitising queries (Rule 14).
    """
    from core.commands import register_command, register_command_alias
    
    handlers: Dict[CommandType, CommandHandler] = {
        CommandType.HELP: HelpHandler(),
        CommandType.STATUS: StatusHandler(),
        CommandType.CLEAR: ClearHandler(),
        CommandType.EXIT: ExitHandler(),
        CommandType.MODEL: ModelHandler(),
        CommandType.ADAPTER: AdapterHandler(),
        CommandType.THEME: ThemeHandler(),
    }
    
    # Only register QueryHandler if orchestrator is provided
    if orchestrator is not None:
        handlers[CommandType.QUERY] = QueryHandler(orchestrator, session_manager, input_sanitiser)
    
    for command_type, handler in handlers.items():
        register_command(command_type, handler)
    
    # Register slash command aliases
    register_command_alias("/help", CommandType.HELP)
    register_command_alias("/status", CommandType.STATUS)
    register_command_alias("/clear", CommandType.CLEAR)
    register_command_alias("/exit", CommandType.EXIT)
    register_command_alias("/quit", CommandType.EXIT)
    register_command_alias("/model", CommandType.MODEL)
    register_command_alias("/adapter", CommandType.ADAPTER)
    register_command_alias("/theme", CommandType.THEME)


class HelpHandler(CommandHandler):
    """Handler for help commands."""
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute help command."""
        from core.commands import get_command_registry
        
        start_time = time.perf_counter()
        
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Help command received",
            level=TraceLevel.INFO,
            data={"command": "help"}
        ))
        
        registry = get_command_registry()
        commands = registry.get_all_commands()
        
        help_text = "Available commands:\n"
        for cmd in commands:
            help_text += f"  - {cmd.value}\n"
        
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_EXECUTED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Help command executed successfully",
            level=TraceLevel.INFO,
            data={"command": "help", "command_count": len(commands)},
            duration_ms=duration_ms
        ))
        
        return CommandResult(
            success=True,
            message="Help information displayed",
            data={"commands": [cmd.value for cmd in commands], "help_text": help_text},
            duration_ms=duration_ms
        )
    
    def get_help(self) -> str:
        """Return help text for this command."""
        return "Show available commands and their usage"
    
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Help",
            "icon": "help",
            "shortcut": "F1",
            "description": "Show available commands",
            "category": "system"
        }


class StatusHandler(CommandHandler):
    """Handler for status commands."""
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute status command."""
        start_time = time.perf_counter()
        
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Status command received",
            level=TraceLevel.INFO,
            data={"command": "status"}
        ))
        
        status_info = {
            "system": "operational",
            "adapters": ["ollama", "lm_studio", "openai", "anthropic", "gemini", "groq", "cohere", "huggingface", "together", "mistral", "deepseek"],
            "memory_backends": ["obsidian", "postgres", "qdrant"],
            "working_directory": command.context.working_directory if command.context else ".",
        }
        
        if command.context:
            status_info["session_id"] = command.context.session_id
            status_info["interface_type"] = command.context.interface_type
        
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_EXECUTED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Status command executed successfully",
            level=TraceLevel.INFO,
            data={"command": "status", "status_info": status_info},
            duration_ms=duration_ms
        ))
        
        return CommandResult(
            success=True,
            message="System status retrieved",
            data=status_info,
            duration_ms=duration_ms
        )
    
    def get_help(self) -> str:
        """Return help text for this command."""
        return "Show current system status and configuration"
    
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Status",
            "icon": "status",
            "shortcut": "Ctrl+S",
            "description": "Show system status",
            "category": "system"
        }


class ClearHandler(CommandHandler):
    """Handler for clear commands."""
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute clear command."""
        return CommandResult(
            success=True,
            message="Screen cleared",
            data={"action": "clear"}
        )
    
    def get_help(self) -> str:
        """Return help text for this command."""
        return "Clear the screen or conversation history"
    
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Clear",
            "icon": "clear",
            "shortcut": "Ctrl+L",
            "description": "Clear screen/history",
            "category": "system"
        }


class ExitHandler(CommandHandler):
    """Handler for exit commands."""
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute exit command."""
        return CommandResult(
            success=True,
            message="Exiting...",
            data={"action": "exit"}
        )
    
    def get_help(self) -> str:
        """Return help text for this command."""
        return "Exit the application"
    
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Exit",
            "icon": "exit",
            "shortcut": "Ctrl+Q",
            "description": "Exit the application",
            "category": "system"
        }


class ModelHandler(CommandHandler):
    """Handler for model switching commands."""
    
    # Default models for each adapter
    ADAPTER_DEFAULT_MODELS = {
        "ollama": "llama2",
        "lm_studio": "local-model",
        "openai": "gpt-4",
        "anthropic": "claude-sonnet-4-6",
        "gemini": "gemini-3.5-flash",
        "groq": "llama3-70b-8192",
        "cohere": "command-r-plus",
        "huggingface": "meta-llama/Meta-Llama-3-70B",
        "together": "meta-llama/Llama-3-70b-chat-hf",
        "mistral": "mistral-large-latest",
        "deepseek": "deepseek-chat"
    }
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute model command."""
        if not command.args:
            # List available models for current adapter (mock for now)
            model_list = "No adapter selected. Please select an adapter first using /adapter"
            return CommandResult(
                success=True,
                message="Available models (requires adapter selection):",
                data={"models": [], "model_list": model_list, "note": "Select adapter first"}
            )
        
        model_name = command.args[0]
        return CommandResult(
            success=True,
            message=f"Model switched to {model_name}",
            data={"model": model_name}
        )
    
    def get_help(self) -> str:
        """Return help text for this command."""
        return "Switch to a different model (requires adapter selection first)"
    
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Switch Model",
            "icon": "model",
            "description": "Switch to a different AI model",
            "category": "configuration",
            "submenu": True
        }


class AdapterHandler(CommandHandler):
    """Handler for adapter switching commands."""
    
    AVAILABLE_ADAPTERS = [
        "ollama",
        "lm_studio",
        "openai",
        "anthropic",
        "gemini",
        "groq",
        "cohere",
        "huggingface",
        "together",
        "mistral",
        "deepseek"
    ]
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute adapter command."""
        start_time = time.perf_counter()
        
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Adapter command received",
            level=TraceLevel.INFO,
            data={"command": "adapter", "args": command.args}
        ))
        
        if not command.args:
            # List available adapters
            adapter_list = "\n".join([f"  - {adapter}" for adapter in self.AVAILABLE_ADAPTERS])
            
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.COMMAND_EXECUTED,
                component=TraceComponent.COMMAND_HANDLER,
                message="Adapter list displayed",
                level=TraceLevel.INFO,
                data={"command": "adapter", "adapter_count": len(self.AVAILABLE_ADAPTERS)},
                duration_ms=duration_ms
            ))
            
            return CommandResult(
                success=True,
                message="Available adapters:",
                data={"adapters": self.AVAILABLE_ADAPTERS, "adapter_list": adapter_list},
                duration_ms=duration_ms
            )
        
        adapter_name = command.args[0]
        if adapter_name not in self.AVAILABLE_ADAPTERS:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.COMMAND_FAILED,
                component=TraceComponent.COMMAND_HANDLER,
                message=f"Unknown adapter: {adapter_name}",
                level=TraceLevel.WARNING,
                error_type="ValidationError",
                error_message=f"Unknown adapter: {adapter_name}",
                data={"requested_adapter": adapter_name, "available_adapters": self.AVAILABLE_ADAPTERS},
                duration_ms=duration_ms
            ))
            
            return CommandResult(
                success=False,
                message=f"Unknown adapter: {adapter_name}",
                error=f"Available adapters: {', '.join(self.AVAILABLE_ADAPTERS)}",
                duration_ms=duration_ms
            )
        
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_EXECUTED,
            component=TraceComponent.COMMAND_HANDLER,
            message=f"Adapter switched to {adapter_name}",
            level=TraceLevel.INFO,
            data={"command": "adapter", "adapter": adapter_name},
            duration_ms=duration_ms
        ))
        
        return CommandResult(
            success=True,
            message=f"Adapter switched to {adapter_name}",
            data={"adapter": adapter_name},
            duration_ms=duration_ms
        )
    
    def get_help(self) -> str:
        """Return help text for this command."""
        return "Switch to a different adapter (or list available adapters)"
    
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Switch Adapter",
            "icon": "adapter",
            "description": "Switch to a different LLM adapter",
            "category": "configuration",
            "submenu": True
        }


class ThemeHandler(CommandHandler):
    """Handler for theme switching commands."""
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute theme command."""
        if not command.args:
            return CommandResult(
                success=False,
                message="Theme name required",
                error="Usage: /theme <theme_name>"
            )
        
        theme_name = command.args[0]
        return CommandResult(
            success=True,
            message=f"Theme switched to {theme_name}",
            data={"theme": theme_name}
        )
    
    def get_help(self) -> str:
        """Return help text for this command."""
        return "Switch to a different theme"
    
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Switch Theme",
            "icon": "theme",
            "description": "Switch to a different theme",
            "category": "appearance",
            "submenu": True
        }


class QueryHandler(CommandHandler):
    """Handler for query commands."""
    
    def __init__(
        self,
        orchestrator: "Orchestrator",
        session_manager: SessionManager | None = None,
        input_sanitiser: "InputSanitiser | None" = None,
    ) -> None:
        """Initialize QueryHandler with injected dependencies.

        Args:
            orchestrator: Orchestrator instance for routing tasks to workers
            session_manager: Optional session manager for conversation history
            input_sanitiser: Optional InputSanitiser for sanitising queries (Rule 14)
        """
        super().__init__()
        self.orchestrator = orchestrator
        self.session_manager = session_manager
        # Security controls default to active — None means "create default"
        if input_sanitiser is not None:
            self._input_sanitiser = input_sanitiser
        else:
            from core.input_sanitiser import InputSanitiser
            self._input_sanitiser = InputSanitiser(emitter=self.emitter)
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute query command."""
        from uuid import uuid4
        from datetime import datetime
        
        start_time = time.perf_counter()
        
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.COMMAND_RECEIVED,
            component=TraceComponent.COMMAND_HANDLER,
            message="Query command received",
            level=TraceLevel.INFO,
            data={"command": "query", "args": command.args}
        ))
        
        if not command.args:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.COMMAND_FAILED,
                component=TraceComponent.COMMAND_HANDLER,
                message="Query command failed: no query provided",
                level=TraceLevel.WARNING,
                error_type="ValidationError",
                error_message="Query required",
                duration_ms=int((time.perf_counter() - start_time) * 1000)
            ))
            return CommandResult(
                success=False,
                message="Query required",
                error="Usage: query <your question>",
                duration_ms=int((time.perf_counter() - start_time) * 1000)
            )
        
        query = " ".join(command.args)

        # Sanitise external input before it enters LLM context (Rule 14)
        # This covers CLI and TUI query paths that go through route_task()
        # (orchestrator.submit_task() has its own sanitiser, but route_task()
        # takes a Task object — so we must sanitise before Task construction)
        query = await self._input_sanitiser.sanitise(query, source="cli_query")

        # Append user message to session history if session manager available
        if self.session_manager and command.context.session_id:
            try:
                await self.session_manager.append(
                    command.context.session_id,
                    Message(role=MessageRole.USER, content=query, timestamp=time.perf_counter())
                )
            except Exception:
                # Ignore session errors to not block query processing
                pass
        
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.OPERATION_START,
            component=TraceComponent.COMMAND_HANDLER,
            message="Processing query via orchestrator",
            level=TraceLevel.INFO,
            data={"query": query}
        ))
        
        # Construct Task from query string
        task = Task(
            task_id=uuid4(),
            intent=query,
            complexity_score=0.5,
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
        )
        
        try:
            # Route task to appropriate worker via orchestrator
            worker_output = await self.orchestrator.route_task(task)
            
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Append assistant response to session history if session manager available
            if self.session_manager and command.context.session_id:
                try:
                    await self.session_manager.append(
                        command.context.session_id,
                        Message(role=MessageRole.ASSISTANT, content=worker_output.content, timestamp=time.perf_counter())
                    )
                except Exception:
                    # Ignore session errors to not block query processing
                    pass
            
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.COMMAND_EXECUTED,
                component=TraceComponent.COMMAND_HANDLER,
                message="Query processed successfully",
                level=TraceLevel.INFO,
                data={
                    "query": query,
                    "response": worker_output.content,
                    "worker_id": worker_output.worker_id,
                    "confidence": worker_output.confidence,
                    "tokens_used": worker_output.tokens_used,
                    "duration_ms": duration_ms
                },
                duration_ms=duration_ms
            ))
            
            return CommandResult(
                success=True,
                message="Query processed",
                data={
                    "query": query,
                    "response": worker_output.content,
                    "worker_id": worker_output.worker_id,
                    "confidence": worker_output.confidence,
                    "tokens_used": worker_output.tokens_used,
                    "duration_ms": duration_ms
                },
                duration_ms=duration_ms
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.COMMAND_FAILED,
                component=TraceComponent.COMMAND_HANDLER,
                message="Query command failed: orchestrator error",
                level=TraceLevel.ERROR,
                error_type="OrchestratorError",
                error_message=str(e),
                duration_ms=duration_ms
            ))
            return CommandResult(
                success=False,
                message=f"Failed to process query: {str(e)}",
                error=str(e),
                duration_ms=duration_ms
            )
    
    def get_help(self) -> str:
        """Return help text for this command."""
        return "Ask the AI a question"
    
    def get_menu_item(self) -> Dict[str, Any]:
        """Return menu item definition for GUI interfaces."""
        return {
            "label": "Query",
            "icon": "query",
            "description": "Ask the AI a question",
            "category": "ai"
        }

