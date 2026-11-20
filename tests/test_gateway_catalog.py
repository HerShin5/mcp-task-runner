import json
from unittest.mock import patch

from mcp_task_runner.gateway_catalog import GatewayCatalog
from mcp_task_runner.providers import ProviderHealth


def test_catalog_loads_arbitrary_gateways_and_can_reload(tmp_path):
    config = tmp_path / "gateways.json"
    config.write_text(
        json.dumps({
            "providers": [
                {
                    "name": "first",
                    "base_url": "https://first/v1",
                    "model": "model",
                    "pricing": {"short": {"input": 1, "output": 1}},
                }
            ]
        }),
        encoding="utf-8",
    )
    catalog = GatewayCatalog(config)
    assert [item.name for item in catalog.providers] == ["first"]

    config.write_text(
        json.dumps({
            "providers": [
                {
                    "name": "first",
                    "base_url": "https://first/v1",
                    "model": "model",
                    "pricing": {"short": {"input": 1, "output": 1}},
                },
                {
                    "name": "new-gateway",
                    "base_url": "https://new/v1",
                    "model": "model",
                    "pricing": {"short": {"input": 0.5, "output": 0.5}},
                },
            ]
        }),
        encoding="utf-8",
    )
    catalog.reload()
    assert [item.name for item in catalog.providers] == ["first", "new-gateway"]


def test_catalog_selection_uses_dynamic_provider_list(tmp_path):
    config = tmp_path / "gateways.json"
    config.write_text(
        json.dumps({
            "providers": [
                {
                    "name": "first",
                    "base_url": "https://first/v1",
                    "model": "model",
                    "pricing": {"short": {"input": 1, "output": 1}},
                },
                {
                    "name": "new-gateway",
                    "base_url": "https://new/v1",
                    "model": "model",
                    "pricing": {"short": {"input": 0.5, "output": 0.5}},
                },
            ]
        }),
        encoding="utf-8",
    )
    catalog = GatewayCatalog(config)
    healthy = [ProviderHealth("first", True, 200, "ok", "model", True, 50), ProviderHealth("new-gateway", True, 200, "ok", "model", True, 100)]
    with patch("mcp_task_runner.gateway_catalog.check_provider", side_effect=healthy):
        decision = catalog.select(input_tokens=100, output_tokens=100)
    assert decision.selected.provider.name == "new-gateway"


def test_catalog_attaches_optional_management_fixture(tmp_path):
    config = tmp_path / "gateways.json"
    config.write_text(json.dumps({
        "providers": [{
            "name": "first",
            "base_url": "https://first/v1",
            "model": "model",
            "pricing": {"short": {"input": 1, "output": 1}},
        }]
    }), encoding="utf-8")
    config.with_suffix(".management.json").write_text(json.dumps({
        "provider": "first",
        "groups": [{"id": "g1", "name": "primary", "models": ["model"]}],
    }), encoding="utf-8")

    catalog = GatewayCatalog(config)
    with patch("mcp_task_runner.gateway_catalog.check_provider", return_value=ProviderHealth("first", True, 200, "ok", "model", True, 50)):
        snapshots = catalog.health()
    assert snapshots[0].management.provider == "first"
    assert snapshots[0].management.groups[0].models[0].name == "model"
