from unittest.mock import Mock

from mcp_task_runner.windows_report import collect_read_only_report


def test_report_calls_only_reviewed_read_only_tools():
    client = Mock()
    client.initialize.return_value = {"protocolVersion": "2025-06-18", "serverInfo": {"name": "fake"}}
    client.list_tools.return_value = [
        {"name": "snapshot"},
        {"name": "click"},
        {"name": "screenshot"},
    ]
    client.session_id = "session"
    client.call_read_only.side_effect = lambda name, arguments, allowed_tools: {"tool": name, "ok": True}

    report = collect_read_only_report(client)

    assert report["read_only"] is True
    assert report["executed_tools"] == ["screenshot", "snapshot"]
    assert [call.args[0] for call in client.call_read_only.call_args_list] == ["screenshot", "snapshot"]
