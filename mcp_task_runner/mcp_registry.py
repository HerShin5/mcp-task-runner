"""Convert discovered MCP tools into local, fail-closed tool metadata."""

from __future__ import annotations

from typing import Any, Iterable

from .core import RiskLevel, ToolRegistry, ToolSpec


# Conservative allowlist: discovery alone must never grant write capability.
DEFAULT_READ_ONLY_TOOLS = frozenset({"snapshot", "screenshot", "debug_nodes"})


def register_discovered_tools(
    registry: ToolRegistry,
    tools: Iterable[dict[str, Any]],
    *,
    read_only_tools: frozenset[str] = DEFAULT_READ_ONLY_TOOLS,
) -> list[ToolSpec]:
    """Register MCP metadata without attaching executable handlers.

    Unknown tools are deliberately classified as destructive. A future adapter
    may add a narrower, reviewed policy; the discovery response itself is not a
    permission grant.
    """
    registered: list[ToolSpec] = []
    for raw in tools:
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        description = str(raw.get("description", "discovered MCP tool"))
        read_only = name in read_only_tools
        spec = ToolSpec(
            name=name,
            description=description,
            risk_level=RiskLevel.READ_ONLY if read_only else RiskLevel.DESTRUCTIVE,
            supports_verify=read_only,
        )
        try:
            registry.register(spec)
            registered.append(spec)
        except ValueError:
            # Keep discovery idempotent when a caller pre-registers a reviewed tool.
            continue
    return registered
