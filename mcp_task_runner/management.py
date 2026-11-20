"""Provider-neutral management-plane snapshots.

Adapters convert a gateway's private management response into this stable
shape. The core router never needs to know which gateway produced it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import time
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ModelSnapshot:
    name: str
    enabled: bool = True
    rate_multiplier: float | None = None
    long_context_pricing_enabled: bool | None = None


@dataclass(frozen=True)
class GroupSnapshot:
    id: str
    name: str
    platform: str | None
    enabled: bool
    rate_multiplier: float | None
    models: tuple[ModelSnapshot, ...]
    rpm_limit: int | None = None
    fallback_group_id: str | None = None
    health_state: str | None = None
    error_rate: float | None = None
    ttft_ms: float | None = None
    cache_rate: float | None = None


@dataclass(frozen=True)
class AccountSnapshot:
    balance: float | None
    frozen_balance: float | None = None
    concurrency: int | None = None
    status: str | None = None


@dataclass(frozen=True)
class ManagementSnapshot:
    provider: str
    groups: tuple[GroupSnapshot, ...]
    balance: AccountSnapshot | None = None
    observed_at: str | None = None

    def observed_epoch(self) -> float | None:
        if not self.observed_at:
            return None
        try:
            value = self.observed_at.replace("Z", "+00:00")
            return datetime.fromisoformat(value).astimezone(timezone.utc).timestamp()
        except (TypeError, ValueError, OverflowError):
            return None

    def is_fresh(self, max_age_seconds: float, *, now: float | None = None) -> bool:
        if max_age_seconds < 0:
            raise ValueError("management snapshot max age cannot be negative")
        observed = self.observed_epoch()
        if observed is None:
            return False
        age = (time() if now is None else now) - observed
        return 0 <= age <= max_age_seconds


@dataclass(frozen=True)
class ManagementRoute:
    group: GroupSnapshot
    model: ModelSnapshot
    rate_multiplier: float


class ManagementAdapterError(RuntimeError):
    """A management endpoint could not produce a valid snapshot."""


class ManagementAdapter(Protocol):
    provider: str

    def fetch(self) -> ManagementSnapshot:
        """Fetch and normalize one provider's management snapshot."""


class GenericHttpManagementAdapter:
    """Small provider-neutral adapter for JSON management endpoints.

    The endpoint and token are supplied by the caller; neither is logged or
    persisted. Provider-specific response mapping belongs in a subclass or
    wrapper that calls ``snapshot_from_generic_payload``.
    """

    def __init__(
        self,
        provider: str,
        endpoint: str,
        *,
        token: str | None = None,
        timeout: float = 8.0,
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
    ) -> None:
        if not provider or not endpoint:
            raise ValueError("provider and endpoint are required")
        if timeout <= 0:
            raise ValueError("management timeout must be positive")
        self.provider = provider
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout
        self.auth_header = auth_header
        self.auth_scheme = auth_scheme

    def fetch(self) -> ManagementSnapshot:
        headers = {
            "Accept": "application/json",
            "User-Agent": "mcp-task-runner-management/0.1",
        }
        if self.token:
            headers[self.auth_header] = f"{self.auth_scheme} {self.token}" if self.auth_scheme else self.token
        request = Request(self.endpoint, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                if not 200 <= status < 300:
                    raise ManagementAdapterError(f"management endpoint returned HTTP {status}")
                payload = json.loads(response.read().decode("utf-8"))
        except ManagementAdapterError:
            raise
        except HTTPError as exc:
            raise ManagementAdapterError(f"management endpoint rejected request ({exc.code})") from exc
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManagementAdapterError("management endpoint unavailable or invalid") from exc
        if not isinstance(payload, dict):
            raise ManagementAdapterError("management endpoint must return a JSON object")
        observed_at = payload.get("observed_at") or datetime.now(timezone.utc).isoformat()
        payload = {**payload, "observed_at": observed_at}
        return snapshot_from_generic_payload(self.provider, payload)


class ManagementSnapshotStore:
    """Refreshes one adapter and only exposes snapshots within its TTL."""

    def __init__(self, adapter: ManagementAdapter, *, max_age_seconds: float = 300.0) -> None:
        if max_age_seconds < 0:
            raise ValueError("management snapshot max age cannot be negative")
        self.adapter = adapter
        self.max_age_seconds = max_age_seconds
        self._snapshot: ManagementSnapshot | None = None
        self._last_error: ManagementAdapterError | None = None

    @property
    def last_error(self) -> ManagementAdapterError | None:
        return self._last_error

    def refresh(self) -> ManagementSnapshot:
        snapshot = self.adapter.fetch()
        if snapshot.provider != self.adapter.provider:
            raise ManagementAdapterError("management adapter returned the wrong provider")
        self._snapshot = snapshot
        self._last_error = None
        return snapshot

    def get(self, *, now: float | None = None) -> ManagementSnapshot | None:
        if self._snapshot is None:
            return None
        if not self._snapshot.is_fresh(self.max_age_seconds, now=now):
            return None
        return self._snapshot

    def refresh_if_stale(self, *, now: float | None = None) -> ManagementSnapshot | None:
        if self.get(now=now) is not None:
            return self.get(now=now)
        try:
            self.refresh()
        except ManagementAdapterError as exc:
            self._last_error = exc
            return None
        return self.get(now=now)


_BLOCKED_STATES = frozenset({
    "blocked",
    "disabled",
    "down",
    "exhausted",
    "offline",
    "suspended",
    "unhealthy",
})


def _enabled(value: Any) -> bool:
    """Only explicit true values enable a group or model."""
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def resolve_management_route(snapshot: ManagementSnapshot | None, model_name: str) -> ManagementRoute | None:
    """Resolve a model to an enabled, usable management-plane group.

    A snapshot with no groups means metadata is unavailable and is therefore
    non-binding. Once groups are reported, absence or a blocked state is
    treated conservatively and excludes that provider/model pair.
    """
    if snapshot is None or not snapshot.groups:
        return None
    matches: list[ManagementRoute] = []
    for group in snapshot.groups:
        state = str(group.health_state or "").strip().lower().replace("-", "_")
        if not group.enabled or state in _BLOCKED_STATES:
            continue
        for model in group.models:
            if model.name != model_name or not model.enabled:
                continue
            group_multiplier = group.rate_multiplier if group.rate_multiplier and group.rate_multiplier > 0 else 1.0
            model_multiplier = model.rate_multiplier if model.rate_multiplier and model.rate_multiplier > 0 else 1.0
            matches.append(ManagementRoute(group, model, group_multiplier * model_multiplier))
    return min(matches, key=lambda item: (item.rate_multiplier, item.group.id)) if matches else None


def snapshot_from_generic_payload(provider: str, payload: dict[str, Any]) -> ManagementSnapshot:
    """Normalize a redacted/generic payload with groups and optional account."""
    nested = payload.get("data")
    nested = nested if isinstance(nested, dict) else {}
    raw_groups = payload.get("groups", nested.get("groups", []))
    if not isinstance(raw_groups, list):
        raw_groups = []
    groups: list[GroupSnapshot] = []
    for raw in raw_groups:
        if not isinstance(raw, dict):
            continue
        raw_models = raw.get("models", [])
        models: list[ModelSnapshot] = []
        for model in raw_models if isinstance(raw_models, list) else []:
            if isinstance(model, str):
                models.append(ModelSnapshot(model))
            elif isinstance(model, dict) and model.get("name"):
                models.append(ModelSnapshot(
                    str(model["name"]),
                    _enabled(model.get("enabled", True)),
                    _number(model.get("rate_multiplier")),
                    model.get("long_context_pricing_enabled"),
                ))
        groups.append(GroupSnapshot(
            id=str(raw.get("id", raw.get("group_id", raw.get("name", "unknown")))),
            name=str(raw.get("name", "unnamed")),
            platform=raw.get("platform"),
            enabled=_enabled(raw.get("enabled", raw.get("status", "active") == "active")),
            rate_multiplier=_number(raw.get("rate_multiplier")),
            models=tuple(models),
            rpm_limit=_integer(raw.get("rpm_limit")),
            fallback_group_id=str(raw["fallback_group_id"]) if raw.get("fallback_group_id") is not None else None,
            health_state=raw.get("health_state", raw.get("serving_state")),
            error_rate=_number(raw.get("error_rate")),
            ttft_ms=_number(raw.get("ttft_ms", raw.get("ttft", {}).get("p50_ms") if isinstance(raw.get("ttft"), dict) else None)),
            cache_rate=_number(raw.get("cache_rate")),
        ))

    account = payload.get("account", nested.get("account", {}))
    balance = None
    if isinstance(account, dict) and any(key in account for key in ("balance", "frozen_balance", "concurrency", "status")):
        balance = AccountSnapshot(
            _number(account.get("balance")),
            _number(account.get("frozen_balance")),
            _integer(account.get("concurrency")),
            account.get("status"),
        )
    return ManagementSnapshot(provider, tuple(groups), balance, payload.get("observed_at"))


def load_snapshot_fixture(path: str | Path, *, provider: str | None = None) -> ManagementSnapshot:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        payload = {}
    inferred_provider = payload.get("provider") if isinstance(payload, dict) else None
    return snapshot_from_generic_payload(provider or str(inferred_provider or "fixture"), payload)
