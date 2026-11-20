"""OpenAI-compatible provider configuration and health checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key: str | None = None
    group_key: str | None = None
    models: tuple[str, ...] = ()
    priority: int = 100
    enabled: bool = True
    timeout: float = 8.0

    def supports_model(self, model: str) -> bool:
        return model == self.model or model in self.models

    @property
    def models_url(self) -> str:
        return self.base_url.rstrip("/") + "/models"


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    reachable: bool
    status_code: int | None
    detail: str
    model: str
    model_available: bool | None = None
    latency_ms: float | None = None
    available_models: tuple[str, ...] = ()


def load_provider_configs(path: str | Path) -> list[ProviderConfig]:
    """Load providers from JSON without logging or returning secret values."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_providers = payload.get("providers", [])
    if not isinstance(raw_providers, list):
        raise ValueError("providers must be a list")
    result: list[ProviderConfig] = []
    for raw in raw_providers:
        if not isinstance(raw, dict):
            raise ValueError("each provider must be an object")
        result.append(
            ProviderConfig(
                name=str(raw["name"]),
                base_url=str(raw["base_url"]),
                model=str(raw.get("model", "")),
                api_key=raw.get("api_key") or None,
                group_key=raw.get("group_key") or None,
                models=tuple(
                    str(item.get("name")) if isinstance(item, dict) else str(item)
                    for item in raw.get("models", [])
                ),
                priority=int(raw.get("priority", 100)),
                enabled=bool(raw.get("enabled", True)),
                timeout=float(raw.get("timeout", 8.0)),
            )
        )
    return sorted((provider for provider in result if provider.enabled), key=lambda item: item.priority)


def check_provider(provider: ProviderConfig) -> ProviderHealth:
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36",
    }
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    request = Request(provider.models_url, headers=headers, method="GET")
    started = perf_counter()
    try:
        with urlopen(request, timeout=provider.timeout) as response:
            status = getattr(response, "status", response.getcode())
            latency_ms = (perf_counter() - started) * 1000
            if 200 <= status < 300:
                available_models = _model_ids(response)
                model_available = provider.model in available_models if available_models is not None else None
                if model_available is None:
                    detail = "models endpoint reachable; model availability unknown"
                else:
                    detail = "models endpoint reachable" if model_available else "model not reported by endpoint"
                return ProviderHealth(provider.name, True, status, detail, provider.model, model_available, latency_ms, tuple(available_models or ()))
            return ProviderHealth(provider.name, False, status, "models endpoint returned a non-success status", provider.model, False, latency_ms)
    except HTTPError as exc:
        # A 401/403 proves the endpoint is reachable but credentials are invalid.
        return ProviderHealth(provider.name, False, exc.code, f"endpoint reachable but rejected request ({exc.code})", provider.model, False, (perf_counter() - started) * 1000)
    except (URLError, TimeoutError, OSError) as exc:
        return ProviderHealth(provider.name, False, None, f"unreachable: {exc}", provider.model, False, (perf_counter() - started) * 1000)


def _model_ids(response: Any) -> set[str] | None:
    try:
        payload = json.loads(response.read().decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return None
    return {item.get("id") for item in data if isinstance(item, dict) and item.get("id")}


def choose_first_healthy(providers: list[ProviderConfig], health: list[ProviderHealth]) -> ProviderConfig | None:
    by_name = {item.name: item for item in health}
    for provider in sorted(providers, key=lambda item: item.priority):
        status = by_name.get(provider.name)
        if provider.enabled and status and status.reachable and status.model == provider.model and status.model_available is True:
            return provider
    return None
