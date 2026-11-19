"""Model capability profiles and task-aware candidate scoring."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


CAPABILITY_NAMES = (
    "reasoning",
    "coding",
    "tool_calling",
    "long_context",
    "vision",
    "chinese",
    "structured_output",
)


@dataclass(frozen=True)
class ModelProfile:
    name: str
    capabilities: dict[str, int]
    known_limits: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    def value(self, capability: str) -> int:
        return int(self.capabilities.get(capability, 0))

    def matches(self, requirements: "TaskRequirements") -> bool:
        return all(self.value(name) >= minimum for name, minimum in requirements.minimum.items())


@dataclass(frozen=True)
class TaskRequirements:
    task_type: str
    minimum: dict[str, int]
    quality_floor: str = "standard"
    cost_preference: str = "balanced"
    preferred_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelCandidate:
    profile: ModelProfile
    cost: float
    latency_ms: float | None = None
    quality_score: float = 100.0
    route_name: str | None = None

    @property
    def capability_margin(self) -> int:
        return sum(self.profile.capabilities.values())


def score_candidate(candidate: ModelCandidate, requirements: TaskRequirements) -> float:
    """Return a lower-is-better score after capability filtering."""
    if not candidate.profile.matches(requirements):
        return float("inf")

    score = candidate.cost
    if requirements.cost_preference == "quality":
        score -= candidate.quality_score * 0.01
        score -= candidate.capability_margin * 0.001
    elif requirements.cost_preference == "speed":
        score += (candidate.latency_ms or 10_000) * 0.001
    elif requirements.cost_preference == "cost":
        pass
    else:  # balanced
        score -= candidate.quality_score * 0.005
        score += (candidate.latency_ms or 10_000) * 0.0005

    if candidate.profile.name in requirements.preferred_models:
        score -= 0.1
    return score


def choose_model(candidates: Iterable[ModelCandidate], requirements: TaskRequirements) -> ModelCandidate | None:
    eligible = [candidate for candidate in candidates if candidate.profile.matches(requirements)]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda candidate: (
            score_candidate(candidate, requirements),
            candidate.latency_ms if candidate.latency_ms is not None else 10_000,
        ),
    )


def load_model_profiles(path: str | Path) -> list[ModelProfile]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    models = payload.get("models", [])
    if not isinstance(models, list):
        raise ValueError("models must be a list")
    return [profile_from_dict(item) for item in models]


def profile_from_dict(data: dict) -> ModelProfile:
    name = str(data["name"])
    capabilities = {key: int(value) for key, value in data.get("capabilities", {}).items()}
    unknown = set(capabilities) - set(CAPABILITY_NAMES)
    if unknown:
        raise ValueError(f"unknown capabilities for {name}: {sorted(unknown)}")
    if any(value < 0 or value > 5 for value in capabilities.values()):
        raise ValueError(f"capability scores for {name} must be between 0 and 5")
    return ModelProfile(
        name=name,
        capabilities=capabilities,
        known_limits=tuple(str(item) for item in data.get("known_limits", [])),
        aliases=tuple(str(item) for item in data.get("aliases", [])),
    )
