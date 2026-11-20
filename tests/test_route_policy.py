import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from mcp_task_runner.capabilities import ModelProfile, TaskRequirements
from mcp_task_runner.gateway_catalog import GatewayCatalog
from mcp_task_runner.management import ManagementAdapterError, snapshot_from_generic_payload
from mcp_task_runner.providers import ProviderHealth


def catalog(tmp_path, **options):
    config = tmp_path / 'providers.json'
    config.write_text(json.dumps({'providers': [{'name': 'a', 'base_url': 'https://example.invalid',
        'model': 'm', 'models': [{'name': 'm'}, {'name': 'other'}], 'pricing': {'short': {'input': 1, 'output': 1}},
        **options}]}), encoding='utf-8')
    # Pricing records are per model.
    return GatewayCatalog(config)


@pytest.mark.parametrize('flag,expected', [('false', False), (None, False), ('invalid', False), (' TRUE ', True)])
def test_local_provider_flag(tmp_path, flag, expected):
    assert bool(catalog(tmp_path, enabled=flag).providers) is expected


def decisions(cat):
    params = {'input_tokens': 1, 'output_tokens': 1}
    return (cat.select(**params).selected is not None, cat.select_model_and_gateway(
        [ModelProfile('m', {})], TaskRequirements('test', {}), **params).selected is not None)


@pytest.mark.parametrize('policy,after_failure', [('required', False), ('advisory', True)])
def test_refresh_failure_policy_and_recovery(tmp_path, monkeypatch, policy, after_failure):
    cat = catalog(tmp_path, management_policy=policy)
    monkeypatch.setattr('mcp_task_runner.gateway_catalog.check_provider', lambda p:
                        ProviderHealth(p.name, True, 200, 'ok', 'm', True))
    clock = 1000.0
    monkeypatch.setattr('mcp_task_runner.management.time', lambda: clock)
    adapter = Mock(provider='a')
    def snap(flag):
        return snapshot_from_generic_payload('a', {'observed_at': datetime.fromtimestamp(clock, timezone.utc).isoformat(),
            'groups': [{'name': 'g', 'enabled': flag, 'models': ['m']}]})
    adapter.fetch.return_value = snap(False)
    cat.register_management_adapter(adapter, max_age_seconds=5)
    assert decisions(cat) == (False, False)
    clock += 10
    adapter.fetch.side_effect = ManagementAdapterError('offline')
    assert decisions(cat) == (after_failure, after_failure)
    adapter.fetch.side_effect = None
    adapter.fetch.return_value = snap(True)
    assert decisions(cat) == (True, True)


@pytest.mark.parametrize('inventory,expected', [((), False), (None, False), (('other',), True)])
def test_secondary_requires_confirmed_inventory(tmp_path, monkeypatch, inventory, expected):
    cat = catalog(tmp_path)
    monkeypatch.setattr('mcp_task_runner.gateway_catalog.check_provider', lambda p:
                        ProviderHealth(p.name, True, 200, 'ok', 'm', False, 10, inventory))
    result = cat.select_model_and_gateway([ModelProfile('other', {})], TaskRequirements('test', {}),
                                          input_tokens=1, output_tokens=1)
    assert (result.selected is not None) is expected
