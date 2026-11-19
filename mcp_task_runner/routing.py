"""Cost-aware and latency-aware model gateway routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from math import inf
from typing import Iterable

from .providers import ProviderConfig, ProviderHealth


class RouteObjective(str, Enum):
    COST = "cost"
    LATENCY = "latency"
    BALANCED = "balanced"


@dataclass(frozen=True)
class PricingBand:
    """Multipliers for one context band.

    Multipliers are intentionally explicit rather than inferred from a group
    label. This lets each gateway describe its own billing rules.
    """

    input_multiplier: float
    output_multiplier: float

    def __post_init__(self) -> None:
        if self.input_multiplier < 0 or self.output_multiplier < 0:
            raise ValueError("pricing multipliers cannot be negative")


@dataclass(frozen=True)
class RoutePricing:
    provider_name: str
    model: str
    short: PricingBand
    long: PricingBand | None = None
    long_context_threshold: int | None = None
    fixed_request_cost: float = 0.0

    def band_for(self, input_tokens: int, *, unknown_policy: str = "conservative") -> PricingBand:
        if self.long_context_threshold is None:
            if unknown_policy == "conservative" and self.long is not None:
                return self.long
            return self.short
        if input_tokens >= self.long_context_threshold and self.long is not None:
            return self.long
        return self.short

    def estimate(self, input_tokens: int, output_tokens: int, *, unknown_policy: str = "conservative") -> float:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token estimates cannot be negative")
        band = self.band_for(input_tokens, unknown_policy=unknown_policy)
        return self.fixed_request_cost + (
            input_tokens * band.input_multiplier + output_tokens * band.output_multiplier
        )


@dataclass(frozen=True)
class RouteCandidate:
    provider: ProviderConfig
    pricing: RoutePricing
    health: ProviderHealth
    estimated_cost: float
    score: float


@dataclass(frozen=True)
class RouteDecision:
    selected: RouteCandidate | None
    candidates: tuple[RouteCandidate, ...]
    reason: str


def select_route(
    providers: Iterable[ProviderConfig],
    health: Iterable[ProviderHealth],
    pricing: Iterable[RoutePricing],
    *,
    input_tokens: int,
    output_tokens: int,
    objective: RouteObjective = RouteObjective.COST,
    latency_weight: float = 0.001,
    unknown_threshold_policy: str = "conservative",
) -> RouteDecision:
    """Select an available route using explicit pricing and health evidence.

    A route is eligible only when its provider is reachable, its requested
    model is present in the provider's reported model list (when available),
    and a matching pricing record exists. Ping/latency never overrides an
    unavailable or unpriced route.
    """
    provider_map = {provider.name: provider for provider in providers if provider.enabled}
    health_map = {item.name: item for item in health}
    pricing_map = {(item.provider_name, item.model): item for item in pricing}
    candidates: list[RouteCandidate] = []

    for name, provider in provider_map.items():
        status = health_map.get(name)
        if status is None or not status.reachable:
            continue
        if status.model_available is False:
            continue
        route_pricing = pricing_map.get((name, provider.model))
        if route_pricing is None:
            continue
        estimated_cost = route_pricing.estimate(
            input_tokens,
            output_tokens,
            unknown_policy=unknown_threshold_policy,
        )
        latency_ms = status.latency_ms if status.latency_ms is not None else 10_000
        if objective is RouteObjective.LATENCY:
            score = float(latency_ms)
        elif objective is RouteObjective.BALANCED:
            score = estimated_cost + latency_weight * latency_ms
        else:
            score = estimated_cost
        candidates.append(RouteCandidate(provider, route_pricing, status, estimated_cost, score))

    candidates.sort(key=lambda item: (item.score, item.health.latency_ms if item.health.latency_ms is not None else inf, item.provider.priority))
    selected = candidates[0] if candidates else None
    reason = "selected lowest-scoring healthy route" if selected else "no healthy route with model and pricing data"
    return RouteDecision(selected, tuple(candidates), reason)


def load_route_pricing(path: str | Path) -> list[RoutePricing]:
    """Load per-provider billing bands from the same routing JSON file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    result: list[RoutePricing] = []
    for raw in payload.get("providers", []):
        models = raw.get("models")
        if not isinstance(models, list):
            models = [{"name": raw.get("model"), "pricing": raw.get("pricing")}]
        for model_config in models:
            if not isinstance(model_config, dict):
                continue
            pricing = model_config.get("pricing", raw.get("pricing"))
            model_name = model_config.get("name", raw.get("model"))
            if not isinstance(pricing, dict) or not model_name:
                continue

            def band(name: str) -> PricingBand:
                values = pricing.get(name)
                if not isinstance(values, dict):
                    raise ValueError(f"pricing.{name} must be an object for {raw.get('name')}/{model_name}")
                return PricingBand(float(values["input"]), float(values["output"]))

            long_values = pricing.get("long")
            long_band = None
            if long_values is not None:
                long_band = PricingBand(float(long_values["input"]), float(long_values["output"]))
            result.append(
                RoutePricing(
                    provider_name=str(raw["name"]),
                    model=str(model_name),
                    short=band("short"),
                    long=long_band,
                    long_context_threshold=(
                    int(pricing["long_context_threshold"])
                    if pricing.get("long_context_threshold") is not None
                    else None
                ),
                    fixed_request_cost=float(pricing.get("fixed_request_cost", 0.0)),
                )
            )
    return result
