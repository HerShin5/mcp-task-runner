"""Minimal read-only MCP Streamable HTTP client.

This adapter intentionally supports only discovery and tool calls. It never
starts a server, touches the desktop, or executes a tool without an explicit
read-only allowlist supplied by the caller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from http.client import HTTPResponse
from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class McpProtocolError(RuntimeError):
    """Raised when an MCP endpoint returns an invalid or failed response."""


@dataclass(frozen=True)
class McpEndpoint:
    url: str
    timeout: float = 10.0
    bearer_token: str | None = None


class StreamableHttpMcpClient:
    """Small JSON-RPC client for an already-running MCP HTTP endpoint."""

    def __init__(self, endpoint: McpEndpoint):
        self.endpoint = endpoint
        self._request_id = 0
        self._session_id: str | None = None
        self._initialized = False

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def initialize(self, *, client_name: str = "mcp-task-runner", client_version: str = "0.1.0") -> dict[str, Any]:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": client_name, "version": client_version},
            },
        )
        self._initialized = True
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        self._require_initialized()
        result = self._rpc("tools/list", {})
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise McpProtocolError("tools/list response has no tools list")
        return [tool for tool in tools if isinstance(tool, dict)]

    def call_read_only(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        allowed_tools: set[str],
        retries: int = 1,
        retry_delay: float = 0.25,
    ) -> Any:
        """Call an allowlisted read-only tool with bounded timeout retries.

        Retries are safe here because the local policy only permits reviewed
        read-only tools. Write/destructive tools never pass this method.
        """
        self._require_initialized()
        if tool_name not in allowed_tools:
            raise PermissionError(f"tool is not in the read-only allowlist: {tool_name}")
        attempts = max(0, retries) + 1
        for attempt in range(attempts):
            try:
                return self._rpc("tools/call", {"name": tool_name, "arguments": arguments})
            except McpProtocolError:
                if attempt >= attempts - 1:
                    raise
                sleep(max(0.0, retry_delay) * (attempt + 1))
        raise McpProtocolError(f"read-only tool did not return: {tool_name}")

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise McpProtocolError("initialize() must be called first")

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        if self.endpoint.bearer_token:
            headers["Authorization"] = f"Bearer {self.endpoint.bearer_token}"

        request = Request(self.endpoint.url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.endpoint.timeout) as response:
                self._remember_session(response)
                body = response.read().decode("utf-8", errors="replace")
                result = _decode_response(response, body)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise McpProtocolError(f"MCP request failed: {exc}") from exc

        if "error" in result:
            raise McpProtocolError(str(result["error"]))
        rpc_result = result.get("result")
        if not isinstance(rpc_result, dict):
            raise McpProtocolError("MCP response has no JSON-RPC result object")
        return rpc_result

    def _remember_session(self, response: HTTPResponse) -> None:
        self._session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("mcp-session-id") or self._session_id


def _decode_response(response: HTTPResponse, body: str) -> dict[str, Any]:
    content_type = _get_content_type(response.headers)
    if content_type == "text/event-stream":
        for line in body.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    return json.loads(data)
        raise McpProtocolError("MCP SSE response did not contain a data event")
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise McpProtocolError("MCP response was not JSON or SSE") from exc
    if not isinstance(decoded, dict):
        raise McpProtocolError("MCP response was not a JSON object")
    return decoded


def _get_content_type(headers: Any) -> str:
    getter = getattr(headers, "get_content_type", None)
    if callable(getter):
        return getter().lower()
    value = headers.get("Content-Type", headers.get("content-type", "application/json"))
    return str(value).split(";", 1)[0].strip().lower()
