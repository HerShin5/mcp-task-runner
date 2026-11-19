import json
from unittest.mock import patch

from mcp_task_runner.capabilities import ModelProfile, TaskRequirements
from mcp_task_runner.core import RiskLevel, ToolRegistry, ToolSpec
from mcp_task_runner.model_client import OpenAICompatibleClient
from mcp_task_runner.orchestrator import StaticTaskClassifier, plan_with_route
from mcp_task_runner.providers import ProviderConfig, ProviderHealth
from mcp_task_runner.routing import PricingBand, RoutePricing


class FakeResponse:
    status = 200

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        body = {
            "choices": [{"message": {"content": json.dumps({
                "goal": "inspect",
                "requires_approval": False,
                "steps": [{"id": "s1", "tool": "health", "arguments": {}, "purpose": "check", "verify": True}],
            })}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 20},
        }
        return json.dumps(body).encode()


def test_orchestrator_selects_route_before_planning():
    registry = ToolRegistry()
    registry.register(ToolSpec("health", "health check", RiskLevel.READ_ONLY, True))
    profiles = [ModelProfile("cheap", {"reasoning": 1, "tool_calling": 1, "structured_output": 3})]
    providers = [ProviderConfig("gateway", "https://example.invalid/v1", "cheap", models=("cheap",))]
    health = [ProviderHealth("gateway", True, 200, "ok", "cheap", True, 20)]
    pricing = [RoutePricing("gateway", "cheap", PricingBand(0.01, 0.01))]
    client = OpenAICompatibleClient(base_url="https://example.invalid/v1", api_key=None, provider="gateway", model="cheap")
    with patch("mcp_task_runner.model_client.urlopen", return_value=FakeResponse()):
        result = plan_with_route(
            user_goal="inspect",
            classifier=StaticTaskClassifier(TaskRequirements("simple", {"reasoning": 1, "tool_calling": 1})),
            profiles=profiles,
            providers=providers,
            health=health,
            pricing=pricing,
            registry=registry,
            client_factory=lambda _: client,
            input_tokens=10,
            output_tokens=20,
        )
    assert result.model == "cheap"
    assert result.plan.steps[0].tool == "health"
