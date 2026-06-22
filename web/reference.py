"""Web GUI reference layer for the Sovereign AI Agent Framework.

This module provides a reference implementation for a web-based GUI
that uses the same command registry as the CLI, ensuring backwards compatibility.

The web GUI would typically use FastAPI + WebSockets for real-time communication.
"""

from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import json

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


class WebCommandRequest(BaseModel):
    """Request model for web commands."""
    command_type: str
    args: List[str] = []
    kwargs: Dict[str, Any] = {}
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class WebCommandResponse(BaseModel):
    """Response model for web commands."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class WebGUIReference:
    """Reference implementation for Web GUI.
    
    This demonstrates how to use the shared command registry
    from a web interface, ensuring the same commands available
    in the CLI are also available in the Web GUI.
    """
    
    def __init__(self) -> None:
        """Initialize the Web GUI reference."""
        self.app = FastAPI(title="Sovereign AI Agent Framework - Web GUI")
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Register default handlers
        register_default_handlers()
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup FastAPI routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "message": "Sovereign AI Agent Framework - Web GUI",
                "version": "1.0.0",
                "interfaces": ["cli", "web", "standalone"]
            }
        
        @self.app.get("/menu")
        async def get_menu():
            """Get menu items for the web GUI.
            
            This ensures CLI menu items are available in the Web GUI.
            """
            registry = get_command_registry()
            menu_items = registry.get_all_menu_items()
            return {"menu_items": menu_items}
        
        @self.app.get("/commands")
        async def get_commands():
            """Get all available commands."""
            registry = get_command_registry()
            commands = registry.get_all_commands()
            return {"commands": [cmd.value for cmd in commands]}
        
        @self.app.post("/execute")
        async def execute_command(request: WebCommandRequest):
            """Execute a command via HTTP POST."""
            registry = get_command_registry()
            
            # Resolve command type
            try:
                command_type = CommandType(request.command_type)
            except ValueError:
                return WebCommandResponse(
                    success=False,
                    message=f"Unknown command type: {request.command_type}",
                    error="Invalid command type"
                )
            
            # Create command
            command = Command(
                command_type=command_type,
                args=request.args,
                kwargs=request.kwargs,
                context=CommandContext(
                    interface_type="web",
                    session_id=request.session_id,
                    user_id=request.user_id,
                    working_directory="."
                )
            )
            
            # Execute command
            result = await registry.execute(command)
            
            return WebCommandResponse(
                success=result.success,
                message=result.message,
                data=result.data,
                error=result.error,
                duration_ms=result.duration_ms
            )
        
        @self.app.websocket("/ws/{session_id}")
        async def websocket_endpoint(websocket: WebSocket, session_id: str):
            """WebSocket endpoint for real-time communication."""
            await websocket.accept()
            self.active_connections[session_id] = websocket
            
            try:
                while True:
                    # Receive command from client
                    data = await websocket.receive_text()
                    request_data = json.loads(data)
                    
                    # Execute command
                    registry = get_command_registry()
                    
                    try:
                        command_type = CommandType(request_data["command_type"])
                    except ValueError:
                        response = {
                            "success": False,
                            "message": f"Unknown command type: {request_data['command_type']}",
                            "error": "Invalid command type"
                        }
                        await websocket.send_json(response)
                        continue
                    
                    command = Command(
                        command_type=command_type,
                        args=request_data.get("args", []),
                        kwargs=request_data.get("kwargs", {}),
                        context=CommandContext(
                            interface_type="web",
                            session_id=session_id,
                            user_id=request_data.get("user_id"),
                            working_directory="."
                        )
                    )
                    
                    result = await registry.execute(command)
                    
                    # Send result back to client
                    response = {
                        "success": result.success,
                        "message": result.message,
                        "data": result.data,
                        "error": result.error,
                        "duration_ms": result.duration_ms
                    }
                    await websocket.send_json(response)
                    
            except WebSocketDisconnect:
                del self.active_connections[session_id]
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app


# Create global instance
_web_gui_instance: Optional[WebGUIReference] = None


def get_web_gui() -> WebGUIReference:
    """Get the global Web GUI instance."""
    global _web_gui_instance
    if _web_gui_instance is None:
        _web_gui_instance = WebGUIReference()
    return _web_gui_instance


# For running directly
if __name__ == "__main__":
    import uvicorn
    
    web_gui = get_web_gui()
    uvicorn.run(web_gui.get_app(), host="0.0.0.0", port=8000)  # nosec B104 — reference/demo file, not production code

