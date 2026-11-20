"""Safe end-to-end Windows-MCP planning workflow.

The model sees the discovered tool catalog, proposes a plan, the local planner
validates it, and only reviewed read-only MCP tools may execute.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capabilities import ModelProfile, TaskRequirements
from .classifier import HeuristicTaskClassifier
from .core import ToolRegistry
from .mcp_http import StreamableHttpMcpClient
from .mcp_registry import register_discovered_tools
from .model_client import OpenAICompatibleClient
from .orchestrator import TaskClassifier, plan_with_route
from .providers import ProviderConfig, ProviderHealth
from .routing import RoutePricing
from .plan_executor import PlanExecutionResult, execute_read_only_plan


@dataclass(frozen=True)
class WindowsWorkflowResult:
    plan: dict[str, Any]
    execution: PlanExecutionResult
    selected_model: str
    selected_provider: str
    usage: dict[str, Any]
    latency_ms: float


def run_read_only_workflow(
    *,
    goal: str,
    client: StreamableHttpMcpClient,
    profiles: list[ModelProfile],
    providers: list[ProviderConfig],
    health: list[ProviderHealth],
    pricing: list[RoutePricing],
    input_tokens: int = 5000,
    output_tokens: int = 1500,
    classifier: TaskClassifier | None = None,
) -> WindowsWorkflowResult:
    """Plan and execute only the discovered reviewed read-only MCP tools."""
    client.initialize()
    discovered = client.list_tools()
    registry = ToolRegistry()
    register_discovered_tools(registry, discovered)

    routed = plan_with_route(
        user_goal=goal,
        classifier=classifier or HeuristicTaskClassifier(),
        profiles=profiles,
        providers=providers,
        health=health,
        pricing=pricing,
        registry=registry,
        client_factory=lambda _: client,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    execution = execute_read_only_plan(routed.plan.to_dict(), client, registry)
    selected = routed.decision.model_route.selected
    if selected is None:
        raise RuntimeError("planner returned without a selected route")
    return WindowsWorkflowResult(
        plan=routed.plan.to_dict(),
        execution=execution,
        selected_model=routed.model,
        selected_provider=routed.provider,
        usage=routed.usage,
        latency_ms=routed.latency_ms,
    )
