import json
from urllib.request import Request, urlopen
from threading import Thread

from mcp_task_runner.api import ApiState, make_handler
from http.server import ThreadingHTTPServer


def test_api_health_and_approval_demo():
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ApiState()))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/health") as response:
            assert json.loads(response.read())["ok"] is True
        request = Request(
            base + "/approval-demo",
            data=json.dumps({"approved": False}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            body = json.loads(response.read())
        assert body["result"]["status"] == "rejected"
    finally:
        server.shutdown()
        server.server_close()
