"""Tests for MCP Adapter."""

import pytest
from unittest.mock import AsyncMock, Mock

from adapters.mcp_adapter import MCPAdapter
from core.observability import MemoryTraceEmitter, TraceEventType

class TestMCPAdapter:
    """Test MCPAdapter class."""

    @pytest.mark.asyncio
    async def test_discover_tools_returns_correctly_parsed_list(self) -> None:
        """Test that discover_tools returns correctly parsed list of tool manifests."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [
            {"name": "tool1", "description": "Test tool 1", "input_schema": {"type": "object"}},
            {"name": "tool2", "description": "Test tool 2", "input_schema": {"type": "object"}},
        ]
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)
        tools = await adapter.discover_tools()

        assert len(tools) == 2
        assert tools[0]["name"] == "tool1"
        assert tools[1]["name"] == "tool2"

    @pytest.mark.asyncio
    async def test_discover_tools_populates_tool_cache(self) -> None:
        """Test that discover_tools populates self._tool_cache."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [{"name": "tool1", "description": "Test tool", "input_schema": {}}]
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)
        await adapter.discover_tools()

        assert len(adapter._tool_cache) == 1
        assert adapter._tool_cache[0]["name"] == "tool1"

    @pytest.mark.asyncio
    async def test_discover_tools_emits_mcp_discover_trace_event(self) -> None:
        """Test that discover_tools emits mcp_discover trace event with correct tool count."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [
            {"name": "tool1", "description": "Test tool 1", "input_schema": {}},
            {"name": "tool2", "description": "Test tool 2", "input_schema": {}},
        ]
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)
        await adapter.discover_tools()

        events = emitter.get_events()
        discover_events = [e for e in events if e.event_type == TraceEventType.OPERATION_COMPLETE]
        assert len(discover_events) == 1
        assert discover_events[0].data["tool_count"] == 2

    @pytest.mark.asyncio
    async def test_call_tool_sends_correct_post_body(self) -> None:
        """Test that call_tool sends correct POST body and returns success dict."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "result": "test result", "error": None}
        mock_response.raise_for_status = Mock()
        mock_client.post.return_value = mock_response

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)
        adapter._tool_cache = [{"name": "tool1", "description": "Test tool", "input_schema": {}}]

        result = await adapter.call_tool("tool1", {"arg1": "value1"})

        mock_client.post.assert_called_once_with(
            "http://localhost:8765/mcp/call", json={"tool": "tool1", "arguments": {"arg1": "value1"}}
        )
        assert result["success"] is True
        assert result["result"] == "test result"

    @pytest.mark.asyncio
    async def test_call_tool_with_empty_cache_calls_discover_first(self) -> None:
        """Test that call_tool with empty cache calls discover_tools() first."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [{"name": "tool1", "description": "Test tool", "input_schema": {}}]
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        mock_client.post.return_value = mock_response

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)

        await adapter.call_tool("tool1", {})

        mock_client.get.assert_called_once_with("http://localhost:8765/mcp/tools")

    @pytest.mark.asyncio
    async def test_call_tool_with_unknown_tool_raises_value_error(self) -> None:
        """Test that call_tool with unknown tool name raises ValueError."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)
        adapter._tool_cache = [{"name": "tool1", "description": "Test tool", "input_schema": {}}]

        with pytest.raises(ValueError, match="Tool 'unknown_tool' not found"):
            await adapter.call_tool("unknown_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_server_error_returns_failure_dict(self) -> None:
        """Test that call_tool when server returns error payload returns failure dict."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Server error")

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)
        adapter._tool_cache = [{"name": "tool1", "description": "Test tool", "input_schema": {}}]

        result = await adapter.call_tool("tool1", {})

        assert result["success"] is False
        assert result["result"] is None
        assert "Server error" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_emits_mcp_tool_call_trace_event(self) -> None:
        """Test that call_tool emits mcp_tool_call trace event."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "result": "test result", "error": None}
        mock_response.raise_for_status = Mock()
        mock_client.post.return_value = mock_response

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)
        adapter._tool_cache = [{"name": "tool1", "description": "Test tool", "input_schema": {}}]

        await adapter.call_tool("tool1", {})

        events = emitter.get_events()
        call_events = [e for e in events if e.event_type == TraceEventType.ADAPTER_CALL]
        assert len(call_events) >= 1
        assert call_events[0].data["tool"] == "tool1"

    @pytest.mark.asyncio
    async def test_list_cached_tools_returns_empty_list_before_discover(self) -> None:
        """Test that list_cached_tools returns empty list before any discover call."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)

        tools = adapter.list_cached_tools()

        assert tools == []

    @pytest.mark.asyncio
    async def test_list_cached_tools_returns_tool_names_after_discover(self) -> None:
        """Test that list_cached_tools returns tool names after discover_tools() call."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [
            {"name": "tool1", "description": "Test tool 1", "input_schema": {}},
            {"name": "tool2", "description": "Test tool 2", "input_schema": {}},
        ]
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)
        await adapter.discover_tools()

        tools = adapter.list_cached_tools()

        assert tools == ["tool1", "tool2"]

    @pytest.mark.asyncio
    async def test_discover_tools_network_failure_emits_error_and_raises(self) -> None:
        """Test that discover_tools network failure emits error trace and raises RuntimeError."""
        emitter = MemoryTraceEmitter()
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")

        adapter = MCPAdapter(server_url="http://localhost:8765", emitter=emitter, http_client=mock_client)

        with pytest.raises(RuntimeError, match="Failed to discover tools"):
            await adapter.discover_tools()

        events = emitter.get_events()
        error_events = [e for e in events if e.level == "error" and e.event_type == TraceEventType.OPERATION_ERROR]
        assert len(error_events) == 1
