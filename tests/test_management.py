import json
from unittest.mock import patch

from mcp_task_runner import BalanceSnapshot
from mcp_task_runner.management import (
    AccountSnapshot,
    GenericHttpManagementAdapter,
    ManagementAdapterError,
    ManagementSnapshot,
    ManagementSnapshotStore,
    load_snapshot_fixture,
    snapshot_from_generic_payload,
)


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


class _FakeAdapter:
    provider = "gateway"

    def __init__(self, snapshot=None, error=None):
        self.snapshot = snapshot
        self.error = error
        self.calls = 0

    def fetch(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.snapshot


def test_snapshot_store_refreshes_once_then_serves_fresh_data():
    snapshot = ManagementSnapshot("gateway", (), observed_at="2026-11-20T10:00:00+00:00")
    adapter = _FakeAdapter(snapshot)
    store = ManagementSnapshotStore(adapter, max_age_seconds=60)
    assert store.refresh_if_stale(now=1795168800) is snapshot
    assert store.refresh_if_stale(now=1795168830) is snapshot
    assert adapter.calls == 1


def test_snapshot_store_drops_stale_data_when_refresh_fails():
    snapshot = ManagementSnapshot("gateway", (), observed_at="2026-11-20T10:00:00+00:00")
    adapter = _FakeAdapter(snapshot)
    store = ManagementSnapshotStore(adapter, max_age_seconds=60)
    assert store.refresh_if_stale(now=1795168800) is snapshot
    adapter.error = ManagementAdapterError("offline")
    assert store.refresh_if_stale(now=1795168900) is None
    assert isinstance(store.last_error, ManagementAdapterError)


def test_snapshot_store_rejects_wrong_provider():
    adapter = _FakeAdapter(ManagementSnapshot("other", ()))
    store = ManagementSnapshotStore(adapter)
    try:
        store.refresh()
    except ManagementAdapterError as error:
        assert "wrong provider" in str(error)
    else:
        raise AssertionError("wrong provider was accepted")


def test_generic_http_adapter_normalizes_json_without_persisting_token():
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({
                "groups": [{"id": "g1", "name": "live", "models": ["model"]}],
            }).encode("utf-8")

    adapter = GenericHttpManagementAdapter("gateway", "https://example.invalid/manage", token="secret")
    with patch("mcp_task_runner.management.urlopen", return_value=_Response()) as open_url:
        snapshot = adapter.fetch()
    request = open_url.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer secret"
    assert snapshot.provider == "gateway"
    assert snapshot.observed_at is not None
    assert "secret" not in repr(snapshot)
