"""Minimal OpenAI-compatible planner client.

The client returns raw model text. Callers must pass it through
`planner.parse_and_validate` before any tool execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelReply:
    text: str
    provider: str
    model: str
    latency_ms: float
    status_code: int
    usage: dict[str, Any]


class OpenAICompatibleClient:
    def __init__(self, *, base_url: str, api_key: str | None, provider: str, model: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider = provider
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]], *, response_format: dict[str, Any] | None = None) -> ModelReply:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False}
        if response_format is not None:
            payload["response_format"] = response_format
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = perf_counter()
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, "status", response.getcode())
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ModelClientError(f"model request rejected: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ModelClientError(f"model request failed: {exc}") from exc

        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelClientError("model response has no choices[0].message.content") from exc
        if not isinstance(text, str):
            raise ModelClientError("model content is not text")
        return ModelReply(
            text=text,
            provider=self.provider,
            model=self.model,
            latency_ms=(perf_counter() - started) * 1000,
            status_code=status,
            usage=body.get("usage", {}),
        )
