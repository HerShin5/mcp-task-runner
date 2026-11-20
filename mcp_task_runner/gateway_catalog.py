"""Config-driven gateway catalog with optional management snapshots.

Gateway names are data, not code. Add, disable, or reorder providers in the
JSON file and call reload(); no source change is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from .management import ManagementSnapshot, load_snapshot_fixture
from .providers import ProviderConfig, ProviderHealth, check_provider, load_provider_configs
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

    def health(self) -> list[GatewaySnapshot]:
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
