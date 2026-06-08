"""Textual TUI implementation with arrow key navigation.

This provides a full-screen terminal UI with menu navigation using
the Textual library, replacing the simple Rich-based CLI.
"""

from textual.app import App, ComposeResult
from textual.widgets import (
    Header,
    Footer,
    Static,
    Input,
    Button,
    ListView,
    ListItem,
    Label,
    Select,
)
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual import events
from textual.screen import ModalScreen
from typing import Optional, List, Any, Callable
import asyncio

# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.commands import (
    Command,
    CommandContext,
    CommandType,
    get_command_registry,
)
from core.handlers import register_default_handlers
from core.session import SessionManager
from core.orchestrator import Orchestrator
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEmitter,
    NullTraceEmitter,
    TraceEvent,
    ConsoleTraceEmitter,
)
from cli.adapter_factory import create_worker
from cli.command_history import CommandHistory


class SelectionScreen(ModalScreen):
    """Modal screen for selecting from a list of options."""
    
    CSS = """
    SelectionScreen {
        align: center middle;
    }
    
    #selection-container {
        width: 60;
        height: 40;
        border: thick green;
    }
    
    #selection-title {
        text-align: center;
        text-style: bold;
    }
    
    #selection-list {
        height: 1fr;
    }
    
    #selection-buttons {
        height: 3;
    }
    """
    
    def __init__(self, title: str, options: List[str], callback: Callable[[str], None]) -> None:
        """Initialize the selection screen.
        
        Args:
            title: Title for the selection screen
            options: List of options to display
            callback: Callback function with selected option
        """
        super().__init__()
        self.title = title
        self.options = options
        self.callback = callback
    
    def compose(self) -> ComposeResult:
        """Compose the selection screen."""
        yield Container(
            Label(self.title, id="selection-title"),
            ListView(id="selection-list"),
            Container(
                Button("Cancel", id="cancel-btn"),
                id="selection-buttons"
            ),
            id="selection-container"
        )
    
    def on_mount(self) -> None:
        """Handle mount event and populate options."""
        list_view = self.query_one("#selection-list", ListView)
        for option in self.options:
            list_item = ListItem(Label(option))
            list_item.option_value = option
            list_view.append(list_item)
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle option selection."""
        item = event.item
        if hasattr(item, 'option_value'):
            self.callback(item.option_value)
            self.app.pop_screen()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "cancel-btn":
            self.app.pop_screen()


class CommandMenu(ListView):
    """Menu widget for command selection with arrow keys."""
    
    def on_mount(self) -> None:
        """Handle mount event and build menu."""
        self.call_after_refresh(self._build_menu)
    
    def _build_menu(self) -> None:
        """Build menu from command registry."""
        registry = get_command_registry()
        menu_items = registry.get_all_menu_items()
        
        # Group by category
        categories: dict[str, list[dict]] = {}
        for item in menu_items:
            category = item.get("category", "other")
            if category not in categories:
                categories[category] = []
            categories[category].append(item)
        
        # Add items to menu
        for category, items in categories.items():
            # Add category header
            self.append(ListItem(Label(f"[bold]{category.upper()}[/bold]", id=f"cat-{category}")))
            
            # Add category items
            for item in items:
                label = f"  {item['label']}"
                if item.get('shortcut'):
                    label += f" ({item['shortcut']})"
                list_item = ListItem(Label(label, id=f"cmd-{item['command_type']}"))
                # Store command type as metadata
                list_item.command_type = item['command_type']
                self.append(list_item)


class OutputDisplay(Static):
    """Widget for displaying command output."""
    
    content = reactive("")
    
    def update_content(self, content: str) -> None:
        """Update the display content."""
        self.content = content
        self.update(content)


class JarvisTUI(App):
    """Main TUI application for Jarvis."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #header {
        height: 3;
    }
    
    #main-container {
        height: 1fr;
    }
    
    #menu-container {
        width: 30;
        dock: left;
    }
    
    #output-container {
        height: 1fr;
    }
    
    #input-container {
        height: 3;
    }
    
    #footer {
        height: 3;
    }
    
    CommandMenu {
        border: solid green;
    }
    
    OutputDisplay {
        border: solid blue;
        padding: 1;
    }
    
    Input {
        width: 1fr;
    }
    """
    
    TITLE = "Sovereign AI Agent Framework"
    
    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the TUI."""
        super().__init__()
        self.emitter = emitter or ConsoleTraceEmitter()
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
        
        # Create orchestrator
        self.orchestrator = Orchestrator(memory_router=None)
        
        # Create default worker and register with orchestrator
        self.worker = create_worker("ollama", "llama3", memory_router=None)
        self.orchestrator.register_worker("ollama_worker", self.worker)
        
        # Register default handlers with orchestrator and session manager
        register_default_handlers(self.orchestrator, self.session_manager)
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header()
        yield Container(
            Container(
                CommandMenu(id="menu"),
                id="menu-container"
            ),
            Container(
                OutputDisplay("Welcome to Jarvis AI Agent Framework\n\nUse arrow keys to navigate menu\nPress Enter to select\nType commands directly below", id="output"),
                id="output-container"
            ),
            id="main-container"
        )
        yield Container(
            Input(placeholder="Type command or query...", id="command-input"),
            id="input-container"
        )
        yield Footer()
    
    def on_mount(self) -> None:
        """Handle mount event."""
        self.output = self.query_one("#output", OutputDisplay)
        self.menu = self.query_one("#menu", CommandMenu)
        self.input = self.query_one("#command-input", Input)
        self.input.focus()
        
        # Create session
        asyncio.create_task(self._create_session())
        
        # Emit TUI start event
        asyncio.create_task(self.emitter.emit(
            TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.CLI,
                message="Textual TUI started",
                level=TraceLevel.INFO,
                data={"session_id": self.session_id}
            )
        ))
    
    async def _create_session(self) -> None:
        """Create a new session."""
        self.session_id = await self.session_manager.create_session()
        
        # Update command history with session_id
        self.command_history.session_id = self.session_id
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        command_str = event.value
        if not command_str:
            return
        
        # Add command to history
        asyncio.create_task(self.command_history.add_command(command_str))
        
        asyncio.create_task(self.process_command(command_str))
        event.input.value = ""
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle menu selection."""
        item = event.item
        if isinstance(item, ListItem):
            # Get command type from metadata
            if hasattr(item, 'command_type'):
                command_type = item.command_type
                
                # Handle adapter/model selection with modal
                if command_type == "adapter":
                    from core.handlers import AdapterHandler
                    handler = AdapterHandler()
                    self.push_screen(
                        SelectionScreen(
                            "Select Adapter",
                            handler.AVAILABLE_ADAPTERS,
                            self._on_adapter_selected
                        )
                    )
                elif command_type == "model":
                    from core.handlers import ModelHandler
                    handler = ModelHandler()
                    # For now, show message about adapter selection
                    asyncio.create_task(self.process_command("/model"))
                else:
                    asyncio.create_task(self.process_command(f"/{command_type}"))
    
    def _on_adapter_selected(self, adapter_name: str) -> None:
        """Handle adapter selection from modal."""
        # Create new worker
        self.worker = create_worker(adapter_name, "llama3", memory_router=None)
        
        # Re-register worker with orchestrator (replace the old worker)
        self.orchestrator.register_worker("ollama_worker", self.worker)
        
        # Process the adapter command to update UI
        asyncio.create_task(self.process_command(f"/adapter {adapter_name}"))
    
    async def process_command(self, command_str: str) -> None:
        """Process a command string."""
        command_str = command_str.strip()
        
        if not command_str:
            return
        
        # Parse command
        parts = command_str.split()
        first_part = parts[0].lower()
        
        # Check if it's a slash command
        if first_part.startswith("/"):
            registry = get_command_registry()
            command_type = registry.resolve_alias(first_part)
            
            if command_type is None:
                self.output.update_content(f"[red]Unknown command: {first_part}[/red]")
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
            # Treat as query
            command = Command(
                command_type=CommandType.QUERY,
                args=parts,
                context=CommandContext(
                    interface_type="cli",
                    session_id=self.session_id,
                    working_directory=str(self.working_directory)
                )
            )
        
        # Execute command
        registry = get_command_registry()
        result = await registry.execute(command)
        
        # Display result
        self._display_result(result)
    
    def _display_result(self, result) -> None:
        """Display command result."""
        if result.success:
            output = f"[green]✓[/green] {result.message}\n"
            
            if result.data:
                for key, value in result.data.items():
                    if key == "help_text":
                        output += f"\n{value}\n"
                    elif isinstance(value, str) and len(value) > 100:
                        output += f"\n{key}:\n{value}\n"
                    else:
                        output += f"{key}: {value}\n"
        else:
            output = f"[red]✗[/red] {result.message}\n"
            if result.error:
                output += f"[red]Error: {result.error}[/red]\n"
        
        if result.duration_ms:
            output += f"\n[dim]({result.duration_ms}ms)[/dim]"
        
        self.output.update_content(output)


def main() -> None:
    """Main entry point for TUI."""
    app = JarvisTUI()
    app.run()


if __name__ == "__main__":
    main()

