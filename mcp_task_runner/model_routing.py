"""Joint model + gateway selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .capabilities import ModelProfile, TaskRequirements
from .management import ManagementRoute, ManagementSnapshot, resolve_management_route
from .providers import ProviderConfig, ProviderHealth
from .quality import QualityAssessment, QualityState
from .routing import PricingBand, RoutePricing


@dataclass(frozen=True)
class ModelRouteCandidate:
    model: ModelProfile
    provider: ProviderConfig
    health: ProviderHealth
    pricing: RoutePricing
    estimated_cost: float
    quality_score: float = 100.0
    management: ManagementRoute | None = None


@dataclass(frozen=True)
class ModelRouteDecision:
    selected: ModelRouteCandidate | None
    candidates: tuple[ModelRouteCandidate, ...]
    reason: str


def choose_model_and_gateway(
    profiles: Iterable[ModelProfile],
    providers: Iterable[ProviderConfig],
    health: Iterable[ProviderHealth],
    pricing: Iterable[RoutePricing],
    requirements: TaskRequirements,
    *,
    input_tokens: int,
    output_tokens: int,
    quality: Iterable[QualityAssessment] = (),
    management: Iterable[ManagementSnapshot] = (),
) -> ModelRouteDecision:
    """Choose a capable model and a healthy provider for that model.

    Capability filtering happens before price comparison. A provider/model
    pair is eligible only when the model is in the provider's declared model
    list (or its primary model), the health probe is usable, and pricing data
    exists for that exact pair.
    """
    profile_map = {profile.name: profile for profile in profiles}
    providers_by_model: dict[str, list[ProviderConfig]] = {}
    for provider in providers:
        for model_name in dict.fromkeys((provider.model, *provider.models)):
            if model_name:
                providers_by_model.setdefault(model_name, []).append(provider)

    health_map = {item.name: item for item in health}
    pricing_map = {(item.provider_name, item.model): item for item in pricing}
    quality_map = {item.route: item for item in quality}
    management_map = {item.provider: item for item in management}
    candidates: list[ModelRouteCandidate] = []

    for model_name, profile in profile_map.items():
        if not profile.matches(requirements):
            continue
        for provider in providers_by_model.get(model_name, []):
            status = health_map.get(provider.name)
            if status is None or not status.reachable:
                continue
            # Health probe may have checked a provider's default model while
            # the requested model is another member of that provider's list.
            if status.available_models and model_name not in status.available_models:
                continue
            if not status.available_models and status.model_available is False and model_name == provider.model:
                continue
            route_name = f"{model_name}@{provider.name}"
            assessment = quality_map.get(route_name)
            if assessment is not None and assessment.state is QualityState.BLOCKED:
                continue
            route_pricing = pricing_map.get((provider.name, model_name))
            if route_pricing is None:
                continue
            management_route = resolve_management_route(management_map.get(provider.name), model_name)
            snapshot = management_map.get(provider.name)
            if snapshot is not None and snapshot.groups and management_route is None:
                continue
            estimated_cost = route_pricing.estimate(input_tokens, output_tokens)
            if management_route is not None:
                estimated_cost *= management_route.rate_multiplier
            candidates.append(
                ModelRouteCandidate(
                    model=profile,
                    provider=provider,
                    health=status,
                    pricing=route_pricing,
                    estimated_cost=estimated_cost,
                    quality_score=assessment.score if assessment is not None else 100.0,
                    management=management_route,
                )
            )

    if not candidates:
        return ModelRouteDecision(None, (), "no capable model/provider pair passed health, model, and pricing filters")

    def score(candidate: ModelRouteCandidate) -> tuple[float, float, int]:
        # Quality preference can spend more; economy prefers raw cost.
        quality_discount = candidate.quality_score * (0.01 if requirements.cost_preference == "quality" else 0.005)
        latency = candidate.health.latency_ms or 10_000
        latency_penalty = latency * (0.001 if requirements.cost_preference == "speed" else 0.0005)
        assessment = quality_map.get(f"{candidate.model.name}@{candidate.provider.name}")
        quality_penalty = 0.0
        if assessment is not None and assessment.should_deprioritize:
            quality_penalty = 1.0
        error_rate = candidate.management.group.error_rate if candidate.management is not None else None
        reliability_penalty = candidate.estimated_cost * min(max(error_rate or 0.0, 0.0), 1.0)
        return (candidate.estimated_cost + reliability_penalty - quality_discount + latency_penalty + quality_penalty, latency, candidate.provider.priority)

    candidates.sort(key=score)
    return ModelRouteDecision(candidates[0], tuple(candidates), "selected capable model/provider pair by cost, quality, latency, and priority")
