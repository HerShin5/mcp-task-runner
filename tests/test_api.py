import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from mcp_task_runner.api import ApiState, make_handler


def test_api_health_and_approval_demo():
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ApiState(allowed_approvers={"api-demo"})))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/health") as response:
            health = json.loads(response.read())
        assert health["ok"] is True
        assert health["mode"] == "development"

        request = Request(
            base + "/approval-demo",
            data=json.dumps({"approved": False}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            body = json.loads(response.read())
        assert body["result"]["status"] == "rejected"

        with urlopen(base + "/approval-demo/pending") as response:
            pending = json.loads(response.read())
        assert pending["status"] == "pending_approval"

        callback = Request(
            base + "/approval-callback",
            data=json.dumps({"task_id": pending["task_id"], "action": "approve", "approver": "forged"}).encode(),
            headers={"Content-Type": "application/json", "X-Approver-Id": "api-demo"},
            method="POST",
        )
        with urlopen(callback) as response:
            result = json.loads(response.read())
        assert result["accepted"] is True
        assert result["status"] == "approved"
    finally:
        server.shutdown()
        server.server_close()


def test_api_rejects_string_approval_and_unconfigured_callback_approver():
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ApiState()))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        request = Request(base + "/approval-demo", data=b'{"approved":"false"}',
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            urlopen(request)
        except HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("string approval was accepted")

        with urlopen(base + "/approval-demo/pending") as response:
            pending = json.loads(response.read())
        callback = Request(base + "/approval-callback", data=json.dumps({
            "task_id": pending["task_id"], "action": "approve", "approver": "forged",
        }).encode(), headers={"Content-Type": "application/json", "X-Approver-Id": "forged"}, method="POST")
        try:
            urlopen(callback)
        except HTTPError as error:
            assert error.code == 403
        else:
            raise AssertionError("unconfigured approver was accepted")
    finally:
        server.shutdown()
        server.server_close()
