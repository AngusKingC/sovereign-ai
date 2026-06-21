"""Rich-based CLI implementation (legacy, for --rich flag).

This provides the original Rich-based CLI with slash commands.
The default is now the Textual TUI with arrow key navigation.
"""

import sys
from pathlib import Path
from typing import Optional, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.prompt import Prompt

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.commands import (
    Command,
    CommandContext,
    CommandType,
    get_command_registry,
    register_command_alias,
)
from core.handlers import register_default_handlers
from core.session import SessionManager
from core.orchestrator import Orchestrator
from core.input_sanitiser import InputSanitiser
from cli.adapter_factory import create_worker
from cli.command_history import CommandHistory
from system.worker_persistence import WorkerPersistence


class JarvisRichCLI:
    """Rich-based CLI interface for Jarvis."""
    
    def __init__(self, interactive: bool = True) -> None:
        """Initialize the CLI.
        
        Args:
            interactive: Whether to run in interactive mode
        """
        self.console = Console()
        self.interactive = interactive
        self.session_id: Optional[str] = None
        self.working_directory = Path.cwd()
        
        # Create session manager (in-memory by default, Postgres if DSN available)
        import os
        from memory.postgres import PostgresBackend
        
        db_dsn = os.getenv("SOVEREIGN_DB_DSN")
        if db_dsn:
            # Use Postgres backend for session persistence
            backend = PostgresBackend(dsn=db_dsn, table_name="sessions")
        else:
            # Fall back to in-memory storage
            backend = None
        
        self.session_manager = SessionManager(backend=backend)
        
        # Create command history manager (in-memory by default, Postgres if DSN available)
        if db_dsn:
            # Use Postgres backend for command history
            history_backend = PostgresBackend(dsn=db_dsn, table_name="command_history")
        else:
            # Fall back to in-memory storage
            history_backend = None
        
        self.command_history = CommandHistory(
            backend=history_backend,
            session_id=None,  # Will be set after session creation
        )
        
        # Create worker persistence (Postgres if DSN available, None otherwise)
        if db_dsn:
            from memory.postgres import PostgresBackend
            from core.memory_router import MemoryRouter
            
            # Create memory router for worker persistence
            memory_router = MemoryRouter(postgres_backend=PostgresBackend(dsn=db_dsn, table_name="workers"))
            self.worker_persistence = WorkerPersistence(
                memory_router=memory_router,
                emitter=None,  # CLI doesn't have emitter in constructor
                obsidian_vault_path=os.getenv("OBSIDIAN_VAULT_PATH"),
            )
        else:
            self.worker_persistence = None
        
        # Create InputSanitiser
        input_sanitiser = InputSanitiser(emitter=None)

        # Create orchestrator
        self.orchestrator = Orchestrator(
            memory_router=None,
            input_sanitiser=input_sanitiser,
        )

        # Create default worker and register with orchestrator
        self.worker = create_worker("ollama", "llama3", memory_router=None)
        self.orchestrator.register_worker("ollama_worker", self.worker)

        # Register default handlers with orchestrator and session manager
        register_default_handlers(self.orchestrator, self.session_manager, input_sanitiser)
        
        # Register CLI-specific aliases
        self._register_cli_aliases()
        
        # Store session_id for command history (will be set after session creation)
        self._session_id_for_history: Optional[str] = None
    
    def _register_cli_aliases(self) -> None:
        """Register CLI-specific command aliases."""
        register_command_alias("?", CommandType.HELP)
        register_command_alias("h", CommandType.HELP)
        register_command_alias("q", CommandType.QUERY)
        register_command_alias("s", CommandType.STATUS)
    
    def print_banner(self) -> None:
        """Print the application banner."""
        banner = Text()
        banner.append("╔════════════════════════════════════════════════════════════╗\n", style="bold blue")
        banner.append("║                                                            ║\n", style="bold blue")
        banner.append("║", style="bold blue")
        banner.append("  SOVEREIGN AI AGENT FRAMEWORK  ", style="bold white on blue")
        banner.append("║\n", style="bold blue")
        banner.append("║                                                            ║\n", style="bold blue")
        banner.append("║", style="bold blue")
        banner.append("  Local-first AI with Cloud Escalation  ", style="dim white")
        banner.append("║\n", style="bold blue")
        banner.append("║                                                            ║\n", style="bold blue")
        banner.append("╚════════════════════════════════════════════════════════════╝\n", style="bold blue")
        
        self.console.print(banner)
        self.console.print()
    
    def print_help(self) -> None:
        """Print help information."""
        help_text = """
# Available Commands

## System Commands
- `/help` or `?` - Show this help message
- `/status` or `s` - Show system status
- `/clear` - Clear the screen
- `/exit` or `quit` - Exit the application

## Configuration Commands
- `/model <name>` - Switch AI model
- `/adapter <name>` - Switch LLM adapter
- `/theme <name>` - Switch theme

## AI Commands
- `query <your question>` - Ask the AI a question
- Or just type your question directly

## Tips
- Use Tab for command completion
- Use Up/Down arrows for command history
- Press Ctrl+C to interrupt
- Type `/help` for more information
"""
        self.console.print(Panel(Markdown(help_text), title="Help", border_style="blue"))
    
    async def process_command(self, command_str: str) -> None:
        """Process a command string."""
        command_str = command_str.strip()
        
        if not command_str:
            return
        
        parts = command_str.split()
        first_part = parts[0].lower()
        
        if first_part.startswith("/"):
            registry = get_command_registry()
            command_type = registry.resolve_alias(first_part)
            
            if command_type is None:
                self.console.print(f"[red]Unknown command: {first_part}[/red]")
                return
            
            args = parts[1:]
            command = Command(
                command_type=command_type,
                args=args,
                context=CommandContext(
                    interface_type="cli",
                    session_id=self.session_id,
                    working_directory=str(self.working_directory)
                )
            )
        else:
            command = Command(
                command_type=CommandType.QUERY,
                args=parts,
                context=CommandContext(
                    interface_type="cli",
                    session_id=self.session_id,
                    working_directory=str(self.working_directory)
                )
            )
        
        registry = get_command_registry()
        result = await registry.execute(command)
        self._display_result(result)
    
    def _display_result(self, result: Any) -> None:
        """Display command result."""
        if result.success:
            self.console.print(f"[green]✓[/green] {result.message}")
            
            if result.data:
                for key, value in result.data.items():
                    if key == "help_text":
                        self.console.print(Markdown(value))
                    elif isinstance(value, str) and len(value) > 100:
                        self.console.print(Panel(value, title=key, border_style="green"))
                    else:
                        self.console.print(f"  {key}: {value}")
        else:
            self.console.print(f"[red]✗[/red] {result.message}")
            if result.error:
                self.console.print(f"[red]Error: {result.error}[/red]")
        
        if result.duration_ms:
            self.console.print(f"[dim]({result.duration_ms}ms)[/dim]")
        
        self.console.print()
    
    async def run_interactive(self) -> None:
        """Run the CLI in interactive mode."""
        self.print_banner()
        self.print_help()
        
        # Create session
        self.session_id = await self.session_manager.create_session()
        
        # Update command history with session_id
        self.command_history.session_id = self.session_id
        
        self.console.print("[dim]Type your query or command (or /help for help)[/dim]")
        self.console.print()
        
        while True:
            try:
                prompt = Prompt.ask(
                    "[bold blue]jarvis[/bold blue] >",
                    console=self.console
                )
                
                if prompt.lower() in ["exit", "quit", "/exit", "/quit"]:
                    break
                
                # Add command to history
                await self.command_history.add_command(prompt)
                
                await self.process_command(prompt)
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
            except EOFError:
                break
    
    async def run_non_interactive(self, query: str) -> None:
        """Run the CLI in non-interactive mode."""
        # Create session
        self.session_id = await self.session_manager.create_session()
        
        # Update command history with session_id
        self.command_history.session_id = self.session_id
        
        # Add command to history
        await self.command_history.add_command(query)
        
        await self.process_command(query)
    
    async def run(self, query: Optional[str] = None) -> None:
        """Run the CLI."""
        if query is None:
            await self.run_interactive()
        else:
            await self.run_non_interactive(query)

