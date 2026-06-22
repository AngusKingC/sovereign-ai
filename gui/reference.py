"""Standalone GUI reference layer for the Sovereign AI Agent Framework.

This module provides a reference implementation for a standalone desktop GUI
that uses the same command registry as the CLI, ensuring backwards compatibility.

The standalone GUI would typically use PyQt, Tkinter, or similar frameworks.
This is a reference implementation showing the architecture pattern.
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import asyncio

# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.commands import (  # noqa: E402 -- path manipulation required
    Command,
    CommandContext,
    CommandType,
    get_command_registry,
)
from core.handlers import register_default_handlers  # noqa: E402 -- path manipulation required


class StandaloneGUIReference(ABC):
    """Reference implementation for Standalone GUI.
    
    This demonstrates how to use the shared command registry
    from a standalone desktop GUI, ensuring the same commands
    available in the CLI are also available in the Standalone GUI.
    
    This is an abstract base class - actual implementations would
    use PyQt, Tkinter, or similar frameworks.
    """
    
    def __init__(self) -> None:
        """Initialize the Standalone GUI reference."""
        self.session_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.working_directory = Path.cwd()
        
        # Register default handlers
        register_default_handlers()
        
        # Build menu from command registry
        self._build_menu()
    
    def _build_menu(self) -> None:
        """Build menu from command registry.
        
        This ensures CLI menu items are available in the Standalone GUI.
        """
        registry = get_command_registry()
        menu_items = registry.get_all_menu_items()
        
        # Group menu items by category
        menu_structure: Dict[str, List[Dict[str, Any]]] = {}
        for item in menu_items:
            category = item.get("category", "other")
            if category not in menu_structure:
                menu_structure[category] = []
            menu_structure[category].append(item)
        
        self.menu_structure = menu_structure
    
    def get_menu_structure(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get the menu structure for the GUI."""
        return self.menu_structure
    
    async def execute_command(
        self,
        command_type: CommandType,
        args: List[str] = [],
        kwargs: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """Execute a command.
        
        Args:
            command_type: Type of command to execute
            args: Command arguments
            kwargs: Named parameters
            
        Returns:
            Command result as dictionary
        """
        registry = get_command_registry()
        
        command = Command(
            command_type=command_type,
            args=args,
            kwargs=kwargs,
            context=CommandContext(
                interface_type="standalone",
                session_id=self.session_id,
                user_id=self.user_id,
                working_directory=str(self.working_directory)
            )
        )
        
        result = await registry.execute(command)
        
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
            "duration_ms": result.duration_ms
        }
    
    @abstractmethod
    def show(self) -> None:
        """Show the GUI window."""
        pass
    
    @abstractmethod
    def hide(self) -> None:
        """Hide the GUI window."""
        pass
    
    @abstractmethod
    def update_display(self, result: Dict[str, Any]) -> None:
        """Update the display with command result.
        
        Args:
            result: Command result to display
        """
        pass
    
    @abstractmethod
    def get_user_input(self) -> str:
        """Get user input from the GUI.
        
        Returns:
            User input string
        """
        pass


class MockStandaloneGUI(StandaloneGUIReference):
    """Mock implementation of Standalone GUI for testing.
    
    This demonstrates the pattern without requiring an actual GUI framework.
    """
    
    def __init__(self) -> None:
        """Initialize the mock GUI."""
        super().__init__()
        self.visible = False
        self.display_content = ""
    
    def show(self) -> None:
        """Show the GUI window."""
        self.visible = True
        print("Mock GUI: Window shown")
    
    def hide(self) -> None:
        """Hide the GUI window."""
        self.visible = False
        print("Mock GUI: Window hidden")
    
    def update_display(self, result: Dict[str, Any]) -> None:
        """Update the display with command result."""
        self.display_content = str(result)
        print(f"Mock GUI: Display updated with {result}")
    
    def get_user_input(self) -> str:
        """Get user input from the GUI."""
        return input("Mock GUI: Enter command > ")


# Example usage
async def example_usage() -> None:
    """Example of how to use the Standalone GUI reference."""
    gui = MockStandaloneGUI()
    
    # Show the GUI
    gui.show()
    
    # Get menu structure
    menu = gui.get_menu_structure()
    print("Menu structure:", menu)
    
    # Execute a command
    result = await gui.execute_command(
        CommandType.HELP,
        args=[]
    )
    gui.update_display(result)
    
    # Hide the GUI
    gui.hide()


if __name__ == "__main__":
    asyncio.run(example_usage())

