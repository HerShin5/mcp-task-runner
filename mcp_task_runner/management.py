"""Provider-neutral management-plane snapshots.

Adapters convert a gateway's private management response into this stable
shape. The core router never needs to know which gateway produced it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
                    bool(model.get("enabled", True)),
                    _number(model.get("rate_multiplier")),
                    model.get("long_context_pricing_enabled"),
                ))
        groups.append(GroupSnapshot(
            id=str(raw.get("id", raw.get("group_id", raw.get("name", "unknown")))),
            name=str(raw.get("name", "unnamed")),
            platform=raw.get("platform"),
            enabled=bool(raw.get("enabled", raw.get("status", "active") == "active")),
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
    inferred_provider = payload.get("provider") if isinstance(payload, dict) else None
    return snapshot_from_generic_payload(provider or str(inferred_provider or "fixture"), payload)
