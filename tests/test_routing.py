from mcp_task_runner.providers import ProviderConfig, ProviderHealth
from mcp_task_runner.routing import PricingBand, RouteObjective, RoutePricing, select_route


def test_cost_route_uses_actual_input_output_bands():
    providers = [
        ProviderConfig("cheap-label", "https://a/v1", "GPT6.1Terra", priority=1),
        ProviderConfig("better-output", "https://b/v1", "GPT6.1Terra", priority=2),
    ]
    health = [
        ProviderHealth("cheap-label", True, 200, "ok", "GPT6.1Terra", True, 80),
        ProviderHealth("better-output", True, 200, "ok", "GPT6.1Terra", True, 100),
    ]
    pricing = [
        RoutePricing("cheap-label", "GPT6.1Terra", PricingBand(1 / 5, 1 / 5), PricingBand(4 / 5, 4 / 5), 100_000),
        RoutePricing("better-output", "GPT6.1Terra", PricingBand(2 / 7.5, 2 / 7.5), PricingBand(1 / 10, 1 / 10), 100_000),
    ]

    short = select_route(providers, health, pricing, input_tokens=10_000, output_tokens=2_000)
    long = select_route(providers, health, pricing, input_tokens=120_000, output_tokens=2_000)

    assert short.selected.provider.name == "cheap-label"
    assert long.selected.provider.name == "better-output"


def test_unhealthy_or_missing_model_is_excluded():
    provider = ProviderConfig("bad", "https://bad/v1", "model")
    health = [ProviderHealth("bad", False, 401, "rejected", "model", False, 30)]
    pricing = [RoutePricing("bad", "model", PricingBand(1, 1))]
    decision = select_route([provider], health, pricing, input_tokens=1, output_tokens=1)
    assert decision.selected is None


def test_latency_objective_can_override_cost():
    providers = [
        ProviderConfig("slow", "https://slow/v1", "model", priority=1),
        ProviderConfig("fast", "https://fast/v1", "model", priority=2),
    ]
    health = [
        ProviderHealth("slow", True, 200, "ok", "model", True, 300),
        ProviderHealth("fast", True, 200, "ok", "model", True, 30),
    ]
    pricing = [
        RoutePricing("slow", "model", PricingBand(0.01, 0.01)),
        RoutePricing("fast", "model", PricingBand(1, 1)),
    ]
    decision = select_route(providers, health, pricing, input_tokens=1, output_tokens=1, objective=RouteObjective.LATENCY)
    assert decision.selected.provider.name == "fast"
