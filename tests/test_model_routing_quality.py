from mcp_task_runner.capabilities import ModelProfile, TaskRequirements
from mcp_task_runner.model_routing import choose_model_and_gateway
from mcp_task_runner.providers import ProviderConfig, ProviderHealth
from mcp_task_runner.quality import QualityAssessment, QualityState
from mcp_task_runner.routing import PricingBand, RoutePricing


def test_blocked_route_is_excluded_and_degraded_route_is_penalized():
    profiles = [
        ModelProfile("cheap", {"reasoning": 2}),
        ModelProfile("stable", {"reasoning": 2}),
        ModelProfile("blocked", {"reasoning": 2}),
    ]
    providers = [
        ProviderConfig("cheap-gw", "https://cheap/v1", "cheap", models=("cheap",)),
        ProviderConfig("stable-gw", "https://stable/v1", "stable", models=("stable",)),
        ProviderConfig("blocked-gw", "https://blocked/v1", "blocked", models=("blocked",)),
    ]
    health = [
        ProviderHealth("cheap-gw", True, 200, "ok", "cheap", True, 10),
        ProviderHealth("stable-gw", True, 200, "ok", "stable", True, 30),
        ProviderHealth("blocked-gw", True, 200, "ok", "blocked", True, 5),
    ]
    pricing = [
        RoutePricing("cheap-gw", "cheap", PricingBand(0.01, 0.01)),
        RoutePricing("stable-gw", "stable", PricingBand(0.02, 0.02)),
        RoutePricing("blocked-gw", "blocked", PricingBand(0.001, 0.001)),
    ]
    quality = [
        QualityAssessment("cheap@cheap-gw", QualityState.SUSPECT, 55, ("bad",), True, False),
        QualityAssessment("blocked@blocked-gw", QualityState.BLOCKED, 10, ("bad",), True, True),
    ]
    decision = choose_model_and_gateway(
        profiles,
        providers,
        health,
        pricing,
        TaskRequirements("general", {"reasoning": 1}, cost_preference="cost"),
        input_tokens=10,
        output_tokens=10,
        quality=quality,
    )
    assert decision.selected.model.name == "stable"
    assert all(candidate.model.name != "blocked" for candidate in decision.candidates)
