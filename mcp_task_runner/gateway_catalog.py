"""Config-driven gateway catalog with optional management snapshots.

Gateway names are data, not code. Add, disable, or reorder providers in the
JSON file and call reload(); no source change is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .capabilities import ModelProfile, TaskRequirements
from .management import ManagementAdapter, ManagementSnapshot, ManagementSnapshotStore, load_snapshot_fixture
from .model_routing import ModelRouteDecision, choose_model_and_gateway
from .providers import ProviderConfig, ProviderHealth, check_provider, load_provider_configs
from .quality import QualityAssessment
from .routing import RouteDecision, RouteObjective, RoutePricing, load_route_pricing, select_route


@dataclass(frozen=True)
class GatewaySnapshot:
    name: str
    backend: str
    health: ProviderHealth
    management: ManagementSnapshot | None = None


class GatewayCatalog:
    """Hot-reloadable, file-backed collection of arbitrary gateways."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.providers: list[ProviderConfig] = []
        self.pricing: list[RoutePricing] = []
        self.management: dict[str, ManagementSnapshot] = {}
        self.management_stores: dict[str, ManagementSnapshotStore] = {}
        self.reload()

    def reload(self) -> None:
        self.providers = load_provider_configs(self.config_path)
        self.pricing = load_route_pricing(self.config_path)
        self.management = {}
        payload_path = self.config_path.with_suffix(".management.json")
        if payload_path.exists():
            # The fixture is a local development seam; real adapters can update
            # the same in-memory snapshot through an authorized management API.
            snapshot = load_snapshot_fixture(payload_path)
            self.management[snapshot.provider] = snapshot

    def register_management_adapter(self, adapter: ManagementAdapter, *, max_age_seconds: float = 300.0) -> None:
        """Attach a runtime adapter without placing credentials in config files."""
        self.management_stores[adapter.provider] = ManagementSnapshotStore(
            adapter,
            max_age_seconds=max_age_seconds,
        )

    def refresh_management(self, *, now: float | None = None) -> dict[str, ManagementSnapshot]:
        """Refresh registered adapters and discard snapshots that are stale."""
        for provider, store in self.management_stores.items():
            snapshot = store.refresh_if_stale(now=now)
            if snapshot is None:
                self.management.pop(provider, None)
            else:
                self.management[provider] = snapshot
        return dict(self.management)

    def health(self) -> list[GatewaySnapshot]:
        self.refresh_management()
        snapshots: list[GatewaySnapshot] = []
        for provider in self.providers:
            status = check_provider(provider)
            snapshots.append(GatewaySnapshot(provider.name, "openai_compatible", status, self.management.get(provider.name)))
        return snapshots

    def select(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        objective: RouteObjective = RouteObjective.COST,
    ) -> RouteDecision:
        statuses = [snapshot.health for snapshot in self.health()]
        return select_route(
            self.providers,
            statuses,
            self.pricing,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            objective=objective,
            management=self.management.values(),
        )

    def select_model_and_gateway(
        self,
        profiles: Iterable[ModelProfile],
        requirements: TaskRequirements,
        *,
        input_tokens: int,
        output_tokens: int,
        quality: Iterable[QualityAssessment] = (),
    ) -> ModelRouteDecision:
        """Select a capable model using one consistent catalog snapshot."""
        snapshots = self.health()
        return choose_model_and_gateway(
            profiles,
            self.providers,
            [item.health for item in snapshots],
            self.pricing,
            requirements,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            quality=quality,
            management=[item.management for item in snapshots if item.management is not None],
        )
