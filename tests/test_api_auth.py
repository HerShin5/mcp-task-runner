import json
import os
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mcp_task_runner.api import ApiState, make_handler


def test_api_token_protects_control_endpoints(monkeypatch):
    monkeypatch.setenv("MCP_TASK_RUNNER_API_TOKEN", "test-token")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ApiState()))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        try:
            urlopen(base + "/health")
        except HTTPError as exc:
            assert exc.code == 401
        request = Request(base + "/health", headers={"Authorization": "Bearer test-token"})
        with urlopen(request) as response:
            assert json.loads(response.read())["ok"] is True
    finally:
        server.shutdown()
        server.server_close()
