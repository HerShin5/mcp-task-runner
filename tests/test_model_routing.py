from mcp_task_runner.capabilities import ModelProfile, TaskRequirements
from mcp_task_runner.model_routing import choose_model_and_gateway
from mcp_task_runner.providers import ProviderConfig, ProviderHealth
from mcp_task_runner.routing import PricingBand, RoutePricing
from mcp_task_runner.management import GroupSnapshot, ManagementSnapshot, ModelSnapshot


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
    assert len(decision.candidates) == 1
    assert decision.selected.provider.name == "expensive-gateway"


def test_joint_router_uses_management_model_and_group_metadata():
    profile = ModelProfile("model", {"tool_calling": 4})
    provider = ProviderConfig("gateway", "https://gateway/v1", "model")
    health = [ProviderHealth("gateway", True, 200, "ok", "model", True, 20)]
    pricing = [RoutePricing("gateway", "model", PricingBand(1, 1))]
    management = [ManagementSnapshot("gateway", (
        GroupSnapshot("live", "live", "openai", True, 0.5, (ModelSnapshot("model"),), health_state="healthy"),
    ))]
    decision = choose_model_and_gateway(
        [profile], [provider], health, pricing,
        TaskRequirements("ops", {"tool_calling": 4}),
        input_tokens=2, output_tokens=1, management=management,
    )
    assert decision.selected.provider.name == "gateway"
    assert decision.selected.estimated_cost == 1.5
    assert decision.selected.management.group.id == "live"
