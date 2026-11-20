"""Read-only Windows-MCP report executor.

Only reviewed read-only tools are callable. The executor never invokes input,
launch, switch, or other desktop-mutating tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mcp_http import StreamableHttpMcpClient
from .mcp_registry import DEFAULT_READ_ONLY_TOOLS


@dataclass(frozen=True)
class DiagnosticResult:
    tool: str
    status: str
    value: Any = None
    error: str | None = None


def collect_read_only_report(
    client: StreamableHttpMcpClient,
    *,
    allowed_tools: frozenset[str] = DEFAULT_READ_ONLY_TOOLS,
    retries: int = 1,
) -> dict[str, Any]:
    """Initialize, discover, and call only reviewed read-only tools."""
    initialization = client.initialize()
    discovered = client.list_tools()
    discovered_names = {item.get("name") for item in discovered if isinstance(item, dict)}
    results: list[DiagnosticResult] = []

    for tool_name in sorted(discovered_names & allowed_tools):
        try:
            value = client.call_read_only(tool_name, {}, allowed_tools=set(allowed_tools), retries=retries)
            results.append(DiagnosticResult(tool_name, "ok", value=value))
        except Exception as exc:  # report one failed check without running another class of tool
            results.append(DiagnosticResult(tool_name, "failed", error=str(exc)))

    return {
        "read_only": True,
        "protocol": initialization.get("protocolVersion"),
        "server": initialization.get("serverInfo"),
        "discovered_tool_count": len(discovered_names),
        "executed_tools": [result.tool for result in results],
        "results": [result.__dict__ for result in results],
        "session_id_present": bool(client.session_id),
    }
