import json
from unittest.mock import Mock, patch

from mcp_task_runner.capabilities import ModelProfile, TaskRequirements
from mcp_task_runner.providers import ProviderConfig, ProviderHealth
from mcp_task_runner.model_client import ModelReply
from mcp_task_runner.routing import PricingBand, RoutePricing
from mcp_task_runner.windows_workflow import run_read_only_workflow


class FakeResponse:
    status = 200

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        content = {
            "goal": "read-only health check",
            "requires_approval": False,
            "steps": [{"id": "s1", "tool": "snapshot", "arguments": {}, "purpose": "read state", "verify": True}],
        }
        return json.dumps({"choices": [{"message": {"content": json.dumps(content)}}], "usage": {}}).encode()


def test_windows_workflow_plans_then_executes_only_read_only_tool():
    client = Mock()
    client.initialize.return_value = {"protocolVersion": "2025-06-18"}
    client.list_tools.return_value = [{"name": "snapshot", "description": "read"}, {"name": "click", "description": "write"}]
    client.session_id = "session"
    client.call_read_only.return_value = {"ok": True}
    client.chat.return_value = ModelReply(
        '{"goal":"inspect","requires_approval":false,"steps":[{"id":"s1","tool":"snapshot","arguments":{},"purpose":"read state","verify":true}]}',
        "fake", "model", 0.0, 200, {},
    )
    profiles = [ModelProfile("model", {"reasoning": 2, "tool_calling": 2, "structured_output": 3})]
    providers = [ProviderConfig("gateway", "https://example.invalid/v1", "model", models=("model",))]
    health = [ProviderHealth("gateway", True, 200, "ok", "model", True, 10)]
    pricing = [RoutePricing("gateway", "model", PricingBand(0.01, 0.01))]
    with patch("mcp_task_runner.model_client.urlopen", return_value=FakeResponse()):
        result = run_read_only_workflow(
            goal="检查状态",
            client=client,
            profiles=profiles,
            providers=providers,
            health=health,
            pricing=pricing,
            classifier=type("Classifier", (), {"classify": lambda self, goal: TaskRequirements("health", {"reasoning": 1, "tool_calling": 1, "structured_output": 2})})(),
        )
    assert result.execution.status == "executed"
    assert [item.tool for item in result.execution.results] == ["snapshot"]
    client.call_read_only.assert_called_once()
    assert client.call_read_only.call_args.args[0] == "snapshot"
