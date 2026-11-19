"""Read-only Windows-MCP diagnostic plan and tool mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mcp_http import StreamableHttpMcpClient


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    tool_name: str
    arguments: dict[str, Any]
    purpose: str


DEFAULT_CHECKS = (
    DiagnosticCheck("process", "local_process_probe", {}, "Check the Windows-MCP bridge process locally"),
    DiagnosticCheck("port", "local_tcp_probe", {"host": "127.0.0.1", "port": 8766}, "Check the bridge port locally"),
    DiagnosticCheck("handshake", "mcp_initialize", {}, "Confirm MCP initialization through the client"),
    DiagnosticCheck("tools", "mcp_tools_list", {}, "List tools advertised by the endpoint"),
)


def build_read_only_plan(*, endpoint: str, checks: tuple[DiagnosticCheck, ...] = DEFAULT_CHECKS) -> dict[str, Any]:
    """Return a serializable plan; this function performs no network calls."""
    return {
        "kind": "windows_mcp_diagnostic",
        "endpoint": endpoint,
        "read_only": True,
        "checks": [
            {
                "name": check.name,
                "tool": check.tool_name,
                "arguments": check.arguments,
                "purpose": check.purpose,
            }
            for check in checks
        ],
    }


def discover_endpoint(client: StreamableHttpMcpClient) -> dict[str, Any]:
    """Initialize and discover tools from an already-running endpoint."""
    initialize_result = client.initialize()
    tools = client.list_tools()
    return {
        "initialized": True,
        "protocol": initialize_result.get("protocolVersion"),
        "server": initialize_result.get("serverInfo"),
        "tools": tools,
        "session_id": client.session_id,
    }
