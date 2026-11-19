from mcp_task_runner.capabilities import ModelProfile, TaskRequirements
from mcp_task_runner.model_routing import choose_model_and_gateway
from mcp_task_runner.providers import ProviderConfig, ProviderHealth
from mcp_task_runner.routing import PricingBand, RoutePricing


def test_joint_router_filters_capability_before_price():
    profiles = [
        ModelProfile("cheap-weak", {"coding": 2, "tool_calling": 1}),
        ModelProfile("expensive-capable", {"coding": 4, "tool_calling": 4}),
    ]
    providers = [
        ProviderConfig("cheap-gateway", "https://cheap/v1", "cheap-weak", models=("cheap-weak",)),
        ProviderConfig("expensive-gateway", "https://expensive/v1", "expensive-capable", models=("expensive-capable",)),
    ]
    health = [
        ProviderHealth("cheap-gateway", True, 200, "ok", "cheap-weak", True, 30),
        ProviderHealth("expensive-gateway", True, 200, "ok", "expensive-capable", True, 60),
    ]
    pricing = [
        RoutePricing("cheap-gateway", "cheap-weak", PricingBand(0.01, 0.01)),
        RoutePricing("expensive-gateway", "expensive-capable", PricingBand(0.05, 0.05)),
    ]
    requirements = TaskRequirements("code_agent", {"coding": 4, "tool_calling": 4}, cost_preference="cost")
    decision = choose_model_and_gateway(profiles, providers, health, pricing, requirements, input_tokens=10, output_tokens=10)
    assert decision.selected.model.name == "expensive-capable"
    assert decision.selected.provider.name == "expensive-gateway"
