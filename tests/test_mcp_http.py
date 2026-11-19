import json
from io import BytesIO
from unittest.mock import patch

from mcp_task_runner.mcp_http import McpEndpoint, StreamableHttpMcpClient
from mcp_task_runner.windows_diagnostics import build_read_only_plan


class FakeResponse:
    def __init__(self, payload, content_type="application/json"):
        self.headers = {"Content-Type": content_type, "Mcp-Session-Id": "test-session"}
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body

    def getcode(self):
        return 200


def test_client_initializes_and_lists_tools():
    responses = [
        FakeResponse({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18"}}),
        FakeResponse({"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "health"}]}}),
    ]

    with patch("mcp_task_runner.mcp_http.urlopen", side_effect=responses):
        client = StreamableHttpMcpClient(McpEndpoint("http://127.0.0.1:8766/mcp"))
        assert client.initialize()["protocolVersion"] == "2025-06-18"
        assert client.list_tools() == [{"name": "health"}]
        assert client.session_id == "test-session"


def test_read_only_call_requires_allowlist():
    with patch("mcp_task_runner.mcp_http.urlopen", return_value=FakeResponse({"result": {"ok": True}})):
        client = StreamableHttpMcpClient(McpEndpoint("http://example.invalid/mcp"))
        client._initialized = True
        assert client.call_read_only("health", {}, allowed_tools={"health"}) == {"ok": True}


def test_diagnostic_plan_is_read_only_and_does_not_call_network():
    plan = build_read_only_plan(endpoint="http://127.0.0.1:8766/mcp")
    assert plan["read_only"] is True
    assert [check["name"] for check in plan["checks"]] == ["process", "port", "handshake", "tools"]
    assert [check["tool"] for check in plan["checks"]] == [
        "local_process_probe",
        "local_tcp_probe",
        "mcp_initialize",
        "mcp_tools_list",
    ]
