"""Behavioral quality and suspected-degradation detection.

This cannot prove hidden model changes. It detects observable regressions in a
provider/model route and produces a conservative routing signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QualityState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    SUSPECT = "suspect"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class QualityObservation:
    route: str
    probe_passed: bool = True
    structured_output_valid: bool = True
    tool_call_expected: bool = False
    tool_call_observed: bool = True
    verification_passed: bool = True
    task_completed: bool = True
    refusal_anomaly: bool = False
    latency_ms: float | None = None
    expected_latency_ms: float | None = None
    error: bool = False


@dataclass(frozen=True)
class QualityAssessment:
    route: str
    state: QualityState
    score: float
    signals: tuple[str, ...]
    should_deprioritize: bool
    should_circuit_break: bool


def assess_quality(observation: QualityObservation) -> QualityAssessment:
    """Score observable behavior; do not infer hidden model internals."""
    score = 100.0
    signals: list[str] = []

    def penalize(points: float, signal: str) -> None:
        nonlocal score
        score -= points
        signals.append(signal)

    if not observation.probe_passed:
        penalize(45, "canary_probe_failed")
    if not observation.structured_output_valid:
        penalize(25, "structured_output_invalid")
    if observation.tool_call_expected and not observation.tool_call_observed:
        penalize(25, "expected_tool_call_missing")
    if not observation.verification_passed:
        penalize(30, "verification_failed")
    if not observation.task_completed:
        penalize(30, "task_incomplete")
    if observation.refusal_anomaly:
        penalize(20, "unexpected_refusal")
    if observation.error:
        penalize(35, "request_error")
    if (
        observation.latency_ms is not None
        and observation.expected_latency_ms is not None
        and observation.latency_ms > observation.expected_latency_ms * 3
    ):
        penalize(10, "latency_regression")

    score = max(0.0, min(100.0, score))
    if score < 35 or observation.error and not observation.probe_passed:
        state = QualityState.BLOCKED
    elif score < 60:
        state = QualityState.SUSPECT
    elif score < 80:
        state = QualityState.DEGRADED
    else:
        state = QualityState.HEALTHY

    return QualityAssessment(
        route=observation.route,
        state=state,
        score=score,
        signals=tuple(signals),
        should_deprioritize=state in {QualityState.DEGRADED, QualityState.SUSPECT},
        should_circuit_break=state is QualityState.BLOCKED,
    )
