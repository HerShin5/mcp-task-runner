from mcp_task_runner.routing import PricingBand, RoutePricing


def test_unknown_threshold_uses_conservative_long_band():
    route = RoutePricing(
        "gateway", "model", PricingBand(1, 1), PricingBand(3, 4), long_context_threshold=None
    )
    assert route.estimate(10, 10) == 70


def test_unknown_threshold_can_use_short_policy_when_explicit():
    route = RoutePricing(
        "gateway", "model", PricingBand(1, 1), PricingBand(3, 4), long_context_threshold=None
    )
    assert route.estimate(10, 10, unknown_policy="short") == 20
