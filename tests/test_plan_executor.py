from unittest.mock import Mock

from mcp_task_runner.core import RiskLevel, ToolRegistry, ToolSpec
from mcp_task_runner.plan_executor import execute_read_only_plan


def test_executor_runs_registered_read_only_steps_and_blocks_write_steps():
    client = Mock()
    client.list_tools.return_value = [{"name": "snapshot"}, {"name": "click"}]
    client.initialize.return_value = {"protocolVersion": "2025-06-18"}
    client.call_read_only.return_value = {"ok": True}
    registry = ToolRegistry()
    registry.register(ToolSpec("snapshot", "read", RiskLevel.READ_ONLY, True))
    registry.register(ToolSpec("click", "click", RiskLevel.DESTRUCTIVE, True))
    plan = {"steps": [
        {"id": "r", "tool": "snapshot", "arguments": {}},
        {"id": "w", "tool": "click", "arguments": {"x": 1}},
    ]}
    result = execute_read_only_plan(plan, client, registry)
    assert result.status == "blocked"
    assert result.blocked_steps == ("w",)
    client.call_read_only.assert_called_once()


def test_mcp_error_fails_step_and_cli_report(monkeypatch, capsys):
    import json
    from mcp_task_runner.cli import run

    client = Mock()
    client.initialize.return_value = {'protocolVersion': 'test'}
    client.list_tools.return_value = [{'name': 'snapshot'}]
    client.call_read_only.return_value = {'isError': True, 'content': []}
    registry = ToolRegistry()
    registry.register(ToolSpec('snapshot', 'read', RiskLevel.READ_ONLY, True))
    result = execute_read_only_plan({'steps': [{'tool': 'snapshot'}]}, client, registry)
    assert (result.status, result.results[0].status) == ('degraded', 'failed')
    monkeypatch.setattr('mcp_task_runner.cli._client_from_args', lambda _: client)
    assert run(['windows-report']) == 2
    report = json.loads(capsys.readouterr().out)
    assert (report['state'], report['failed_checks'], report['passed_checks']) == ('degraded', 1, 0)
