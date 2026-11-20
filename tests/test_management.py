import json

from mcp_task_runner import BalanceSnapshot
from mcp_task_runner.management import AccountSnapshot, load_snapshot_fixture, snapshot_from_generic_payload


def test_management_payload_normalizes_groups_models_health_and_balance():
    snapshot = snapshot_from_generic_payload("example", {
        "groups": [{
            "group_id": 7,
            "name": "cheap",
            "platform": "openai",
            "status": "active",
            "rate_multiplier": 0.02,
            "rpm_limit": 60,
            "models": [{"name": "model", "long_context_pricing_enabled": True}],
            "health_state": "healthy",
            "error_rate": 0.01,
            "ttft": {"p50_ms": 1200},
            "cache_rate": 0.9,
        }],
        "account": {"balance": 20, "frozen_balance": 0, "concurrency": 10, "status": "active"},
    })
    assert snapshot.groups[0].id == "7"
    assert snapshot.groups[0].models[0].name == "model"
    assert snapshot.groups[0].ttft_ms == 1200
    assert snapshot.balance.concurrency == 10


def test_management_account_snapshot_does_not_replace_balance_alert_snapshot():
    assert BalanceSnapshot("gateway", 1.0).balance == 1.0
    assert AccountSnapshot(1.0, concurrency=2).concurrency == 2


def test_fixture_loader_infers_provider_and_tolerates_non_object_data(tmp_path):
    fixture = tmp_path / "management.json"
    fixture.write_text(json.dumps({"provider": "gateway", "data": []}), encoding="utf-8")
    snapshot = load_snapshot_fixture(fixture)
    assert snapshot.provider == "gateway"
    assert snapshot.groups == ()
