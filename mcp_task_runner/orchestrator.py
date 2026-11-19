"""Task orchestration: route model -> execution model -> validated plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .capabilities import ModelProfile, TaskRequirements
from .model_client import OpenAICompatibleClient
from .model_routing import ModelRouteDecision, choose_model_and_gateway
from .planner import TaskPlan, parse_and_validate
from .providers import ProviderConfig, ProviderHealth
from .routing import RoutePricing


@dataclass(frozen=True)
class RoutingDecision:
    task_requirements: TaskRequirements
    model_route: ModelRouteDecision


@dataclass(frozen=True)
class RoutedPlan:
    decision: RoutingDecision
    plan: TaskPlan
    provider: str
    model: str
    latency_ms: float
    usage: dict[str, Any]


class TaskClassifier:
    """Small seam for a routing model or a deterministic classifier."""

    def classify(self, user_goal: str) -> TaskRequirements:
        raise NotImplementedError


class StaticTaskClassifier(TaskClassifier):
    def __init__(self, requirements: TaskRequirements):
        self.requirements = requirements

    def classify(self, user_goal: str) -> TaskRequirements:
        return self.requirements


def plan_with_route(
    *,
    user_goal: str,
    classifier: TaskClassifier,
    profiles: Iterable[ModelProfile],
    providers: Iterable[ProviderConfig],
    health: Iterable[ProviderHealth],
    pricing: Iterable[RoutePricing],
    registry,
    client_factory: Callable[[ModelRouteDecision], OpenAICompatibleClient],
    input_tokens: int,
    output_tokens: int,
) -> RoutedPlan:
    """Select an execution route, call it, and validate its plan output."""
    requirements = classifier.classify(user_goal)
    decision = choose_model_and_gateway(
        profiles,
        providers,
        health,
        pricing,
        requirements,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    if decision.selected is None:
        raise RuntimeError("no model/gateway satisfies task requirements")
    client = client_factory(decision)
    reply = client.chat(
        [
            {"role": "system", "content": "Return a validated JSON task plan only."},
            {"role": "user", "content": user_goal},
        ],
        response_format={"type": "json_object"},
    )
    plan = parse_and_validate(reply.text, registry)
    return RoutedPlan(
        RoutingDecision(requirements, decision),
        plan,
        reply.provider,
        reply.model,
        reply.latency_ms,
        reply.usage,
    )
