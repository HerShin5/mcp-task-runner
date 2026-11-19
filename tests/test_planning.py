import json
from unittest.mock import patch

from mcp_task_runner.core import RiskLevel, ToolRegistry, ToolSpec
from mcp_task_runner.model_client import OpenAICompatibleClient
from mcp_task_runner.planning import plan_task


class FakeResponse:
    status = 200

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        payload = {
            "choices": [{"message": {"content": json.dumps({
                "goal": "inspect service",
                "requires_approval": False,
                "steps": [{"id": "s1", "tool": "health", "arguments": {}, "purpose": "inspect", "verify": True}],
            })}}],
            "usage": {},
        }
        return json.dumps(payload).encode()


def test_model_plan_is_validated_before_returning():
    registry = ToolRegistry()
    registry.register(ToolSpec("health", "read-only health check", RiskLevel.READ_ONLY, True, lambda _: {"ok": True}))
    client = OpenAICompatibleClient(base_url="https://example.invalid/v1", api_key=None, provider="fake", model="model")
    with patch("mcp_task_runner.model_client.urlopen", return_value=FakeResponse()):
        planned = plan_task(client, registry, "inspect service")
    assert planned.plan.goal == "inspect service"
    assert planned.plan.steps[0].tool == "health"
