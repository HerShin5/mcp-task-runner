import json
from unittest.mock import patch

import pytest

from mcp_task_runner.approvals import ApprovalStatus, ApprovalStore, LocalApprovalGateway
from mcp_task_runner.core import RiskLevel, ToolSpec
from mcp_task_runner.providers import check_provider, choose_first_healthy, load_provider_configs


class FakeResponse:
    status = 200

    def read(self):
        return b'{"data": [{"id": "model"}]}'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return 200


def test_provider_config_supports_manual_base_url_and_model(tmp_path):
    path = tmp_path / "providers.json"
    path.write_text(json.dumps({"providers": [{"name": "one", "base_url": "https://one/v1", "model": "m", "priority": 2}]}), encoding="utf-8")
    providers = load_provider_configs(path)
    assert providers[0].models_url == "https://one/v1/models"
    assert providers[0].model == "m"


def test_provider_health_and_priority_selection():
    providers = [
        load_provider_configs_from("first", "https://first/v1", 1),
        load_provider_configs_from("second", "https://second/v1", 2),
    ]
    with patch("mcp_task_runner.providers.urlopen", return_value=FakeResponse()):
        health = [check_provider(provider) for provider in providers]
    assert all(item.reachable for item in health)
    assert choose_first_healthy(providers, health).name == "first"


def load_provider_configs_from(name, base_url, priority):
    from mcp_task_runner.providers import ProviderConfig
    return ProviderConfig(name, base_url, "model", priority=priority)


def test_local_approval_gateway_records_rejection():
    store = ApprovalStore()
    tool = ToolSpec("restart", "restart service", RiskLevel.DESTRUCTIVE)
    decision = LocalApprovalGateway(store, approve=False).request("task-1", tool, {})
    assert decision.approved is False
    assert store.get("task-1").status is ApprovalStatus.REJECTED


@pytest.mark.parametrize("body,availability,exit_code", [
    ({"data": [{"id": "different"}]}, False, 1), ({}, None, 1),
    ({"data": [{"id": "model"}]}, True, 0),
])
def test_cli_health_requires_confirmed_model(tmp_path, capsys, body, availability, exit_code):
    from mcp_task_runner.cli import run

    config = tmp_path / "providers.json"
    config.write_text(json.dumps({"providers": [{"name": "local", "base_url": "https://example.invalid/v1",
                                                 "model": "model"}]}), encoding="utf-8")
    response = FakeResponse()
    response.read = lambda: json.dumps(body).encode()
    with patch("mcp_task_runner.providers.urlopen", return_value=response):
        assert run(["providers-health", "--config", str(config)]) == exit_code
    result = json.loads(capsys.readouterr().out)
    assert result["providers"][0]["reachable"] is True
    assert result["providers"][0]["model_available"] is availability
    assert result["selected"] == ("local" if availability else None)
