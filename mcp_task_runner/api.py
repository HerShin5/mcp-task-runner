"""Dependency-free JSON API surface for the MVP.

This is intentionally a small adapter around the same core used by the CLI.
It is not production auth or a final web console.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4

from .approvals import ApprovalStore, LocalApprovalGateway
from .approval_callbacks import ApprovalCallbackHandler, approval_request_dict
from .core import EvidenceLog, RiskLevel, TaskRunner, ToolRegistry, ToolSpec, VerificationResult
from .windows_diagnostics import build_read_only_plan


class ApiState:
    def __init__(self) -> None:
        self.approvals = ApprovalStore()
        self.evidence = EvidenceLog()
        self.callback_handler = ApprovalCallbackHandler(self.approvals)

    def create_pending_demo(self) -> dict[str, Any]:
        """Create a pending request for local callback testing only."""
        task_id = str(uuid4())
        request = self.approvals.create(
            task_id,
            ToolSpec("restart_demo", "simulated service restart", RiskLevel.WRITE, True),
            {},
            requester="api-demo",
        )
        return approval_request_dict(request)

    def run_demo(self, approved: bool) -> dict[str, Any]:
        registry = ToolRegistry()
        registry.register(ToolSpec("restart_demo", "simulated service restart", RiskLevel.WRITE, True, lambda _: {"restarted": True}))
        result = TaskRunner(registry, LocalApprovalGateway(self.approvals, approve=approved), self.evidence).execute(
            "restart_demo", {}, lambda value: VerificationResult(value.get("restarted") is True, "simulated post-check")
        )
        return {"result": result.__dict__, "evidence": self.evidence.events}


def make_handler(state: ApiState):
    class Handler(BaseHTTPRequestHandler):
        def _authorized(self) -> bool:
            expected = os.getenv("MCP_TASK_RUNNER_API_TOKEN")
            if not expected:
                return True
            provided = self.headers.get("Authorization", "")
            return provided == f"Bearer {expected}"

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            if self.path == "/health":

                self._json(200, {"ok": True, "service": "mcp-task-runner", "mode": "development"})
                return
            if self.path == "/approval-demo/pending":
                self._json(200, state.create_pending_demo())
                return
            if self.path.startswith("/diagnostic-plan"):
                self._json(200, build_read_only_plan(endpoint="http://127.0.0.1:8766/mcp"))
                return
            self._json(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            if self.path == "/approval-callback":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw)
                    result = state.callback_handler.handle(payload, approver=str(payload.get("approver", "unknown")))
                except (json.JSONDecodeError, AttributeError):
                    self._json(400, {"accepted": False, "status": "invalid", "message": "body must be JSON"})
                    return
                self._json(200 if result.accepted else 403, result.__dict__)
                return
            if self.path != "/approval-demo":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw)
                approved = bool(payload.get("approved", False))
            except (json.JSONDecodeError, AttributeError):
                self._json(400, {"error": "body must be JSON"})
                return
            self._json(200, state.run_demo(approved))

        def log_message(self, format, *args):
            return

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8767) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(ApiState()))
    print(f"mcp-task-runner API listening on http://{host}:{port}")
    server.serve_forever()
