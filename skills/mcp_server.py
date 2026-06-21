"""MCP Server - exposes SkillRegistry over MCP HTTP protocol."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from core.observability import MemoryTraceEmitter, TraceEmitter
from core.skill_registry import SkillRegistry


class MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MCP server."""

    def __init__(self, *args: Any, mcp_server: "MCPServer", **kwargs: Any) -> None:
        self.mcp_server = mcp_server
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/mcp/tools":
            self.handle_get_tools()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/mcp/call":
            self.handle_call_tool()
        else:
            self.send_error(404, "Not Found")

    def handle_get_tools(self) -> None:
        """Handle GET /mcp/tools."""
        try:
            tools = self.mcp_server.get_tools_manifest()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(tools).encode())
        except Exception as e:
            self.send_error(500, str(e))

    def handle_call_tool(self) -> None:
        """Handle POST /mcp/call."""
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())

            tool_name = data.get("tool")
            arguments = data.get("arguments", {})

            if not tool_name:
                self.send_error(400, "Missing 'tool' field in request body")
                return

            result = self.mcp_server.call_skill(tool_name, arguments)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode()
)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON in request body")
        except Exception as e:
            self.send_error(500, str(e))


class MCPServer:
    """MCP server that exposes SkillRegistry over HTTP."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        emitter: TraceEmitter | None = None,
        host: str = "localhost",
        port: int = 8765,
    ) -> None:
        self._skill_registry = skill_registry
        self._emitter = emitter or MemoryTraceEmitter()
        self._host = host
        self._port = port
        self._server: HTTPServer | None = None
        self._server_thread: threading.Thread | None = None

    def get_tools_manifest(self) -> list[dict]:
        """Return MCP-compliant tool manifests for all registered skills."""
        skills = self._skill_registry.all_skills()
        manifests = []
        for skill in skills.values():
            manifests.append(
                {
                    "name": skill.name,
                    "description": skill.description,
                    "input_schema": {
                        "type": "object",
                        "properties": skill.parameters,
                    },
                }
            )
        return manifests

    def call_skill(self, tool_name: str, arguments: dict) -> dict:
        """Call a skill by name with arguments."""
        skill = self._skill_registry.get_skill(tool_name)
        if not skill:
            return {"success": False, "result": None, "error": "Tool not found"}

        try:
            # In a real implementation, this would instantiate and call the skill
            # For now, return a placeholder response
            return {"success": True, "result": f"Called {tool_name} with {arguments}", "error": None}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}

    def start(self) -> None:
        """Start the HTTP server in a background thread."""
        handler = lambda *args, **kwargs: MCPRequestHandler(*args, mcp_server=self, **kwargs)
        self._server = HTTPServer((self._host, self._port), handler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

    def stop(self) -> None:
        """Shut down the server thread."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
