"""Execute only validated read-only plan steps through an MCP client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import RiskLevel, ToolRegistry
from .mcp_http import StreamableHttpMcpClient
from .windows_report import DiagnosticResult


@dataclass(frozen=True)
class PlanExecutionResult:
    status: str
    results: tuple[DiagnosticResult, ...]
    blocked_steps: tuple[str, ...] = ()


def execute_read_only_plan(
    plan: dict[str, Any],
    client: StreamableHttpMcpClient,
    registry: ToolRegistry,
    *,
    retries: int = 1,
) -> PlanExecutionResult:
    """Execute only read-only registered MCP steps; block everything else."""
    client.initialize()
    discovered = {item.get("name") for item in client.list_tools() if isinstance(item, dict)}
    results: list[DiagnosticResult] = []
    blocked: list[str] = []

    for step in plan.get("steps", []):
        step_id = str(step.get("id", "unknown"))
        tool_name = step.get("tool")
        if not isinstance(tool_name, str):
            blocked.append(step_id)
            continue
        if tool_name not in discovered:
            blocked.append(step_id)
            results.append(DiagnosticResult(tool_name, "failed", error="tool not advertised by MCP endpoint"))
            continue
        try:
            spec = registry.get(tool_name)
        except KeyError:
            blocked.append(step_id)
            results.append(DiagnosticResult(tool_name, "blocked", error="tool is not registered locally"))
            continue
        if spec.risk_level is not RiskLevel.READ_ONLY:
            blocked.append(step_id)
            results.append(DiagnosticResult(tool_name, "blocked", error="non-read-only step requires approval"))
            continue
        try:
            value = client.call_read_only(tool_name, step.get("arguments", {}), allowed_tools={tool_name}, retries=retries)
            results.append(DiagnosticResult.from_mcp(tool_name, value))
        except Exception as exc:
            results.append(DiagnosticResult(tool_name, "failed", error=str(exc)))

    if blocked:
        status = "blocked"
    elif any(item.status == "failed" for item in results):
        status = "degraded"
    else:
        status = "executed"
    return PlanExecutionResult(status, tuple(results), tuple(blocked))
