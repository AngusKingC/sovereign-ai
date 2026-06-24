"""MCP (Model Context Protocol) Adapter for calling external MCP tool servers."""

import httpx

from core.observability import MemoryTraceEmitter, TraceComponent, TraceEmitter, TraceEvent, TraceEventType, TraceLevel


class MCPAdapter:
    """Client for calling external MCP tool servers."""

    def __init__(
        self,
        server_url: str,
        emitter: TraceEmitter | None = None,
        timeout: int = 30,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._server_url = server_url
        self._emitter = emitter or MemoryTraceEmitter()
        self._timeout = timeout
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout)
        self._tool_cache: list[dict] = []

    async def discover_tools(self) -> list[dict]:
        """Discover tools from the MCP server."""
        try:
            response = await self._http_client.get(f"{self._server_url}/mcp/tools")
            response.raise_for_status()
            tools = response.json()
            self._tool_cache = tools
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.ADAPTER,
                    level=TraceLevel.INFO,
                    message=f"Discovering tools from {self._server_url}",
                    data={"tool_count": len(tools)},
                    duration_ms=0,
                )
            )
            return tools
        except Exception as e:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.ADAPTER,
                    level=TraceLevel.ERROR,
                    message=str(e),
                    data={},
                    duration_ms=0,
                )
            )
            raise RuntimeError(f"Failed to discover tools from MCP server: {e}") from e

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server."""
        if not self._tool_cache:
            await self.discover_tools()

        tool_names = [tool.get("name") for tool in self._tool_cache]
        if tool_name not in tool_names:
            raise ValueError(f"Tool '{tool_name}' not found in cached tools")

        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.ADAPTER_CALL,
                    component=TraceComponent.ADAPTER,
                    level=TraceLevel.INFO,
                    message=f"Calling MCP tool: {tool_name}",
                    data={"tool": tool_name},
                    duration_ms=0,
                )
            )
            response = await self._http_client.post(
                f"{self._server_url}/mcp/call",
                json={"tool": tool_name, "arguments": arguments},
            )
            response.raise_for_status()
            result = response.json()
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.ADAPTER_RESPONSE,
                    component=TraceComponent.ADAPTER,
                    level=TraceLevel.INFO,
                    message=f"Called MCP tool: {tool_name}",
                    data={"tool": tool_name, "success": True},
                    duration_ms=0,
                )
            )
            return result
        except Exception as e:
            error_message = str(e)
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.ADAPTER_ERROR,
                    component=TraceComponent.ADAPTER,
                    level=TraceLevel.WARNING,
                    message=f"Failed to call MCP tool: {tool_name}",
                    data={"tool": tool_name, "success": False, "error": error_message},
                    duration_ms=0,
                )
            )
            return {"success": False, "result": None, "error": error_message}

    def list_cached_tools(self) -> list[str]:
        """Return names of tools currently in the cache."""
        return [tool.get("name", "") for tool in self._tool_cache if tool.get("name")]
