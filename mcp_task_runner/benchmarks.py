"""Fixed benchmark tasks for model/gateway comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class BenchmarkTask:
    id: str
    category: str
    prompt: str
    required_capabilities: dict[str, int]
    expected_tool: str | None = None
    requires_structured_output: bool = False
    expected_markers: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkObservation:
    task_id: str
    route: str
    structured_valid: bool
    tool_called: bool | None
    verification_passed: bool | None
    task_completed: bool
    latency_ms: float | None
    cost: float | None
    output_text: str = ""
    error: str | None = None


@dataclass(frozen=True)
class BenchmarkSummary:
    route: str
    task_count: int
    completion_rate: float
    structured_rate: float
    tool_call_rate: float | None
    verification_rate: float | None
    average_latency_ms: float | None
    total_cost: float
    score: float
    signals: tuple[str, ...] = ()


def summarize_observations(observations: Iterable[BenchmarkObservation]) -> BenchmarkSummary:
    rows = list(observations)
    if not rows:
        raise ValueError("at least one benchmark observation is required")
    route = rows[0].route
    if any(row.route != route for row in rows):
        raise ValueError("all observations must belong to the same route")

    completion = mean(row.task_completed for row in rows)
    structured = mean(row.structured_valid for row in rows)
    tool_rows = [row.tool_called for row in rows if row.tool_called is not None]
    verify_rows = [row.verification_passed for row in rows if row.verification_passed is not None]
    latency_rows = [row.latency_ms for row in rows if row.latency_ms is not None]
    total_cost = sum(row.cost or 0.0 for row in rows)
    score = 100 * (0.4 * completion + 0.25 * structured)
    if tool_rows:
        score += 20 * mean(tool_rows)
    if verify_rows:
        score += 15 * mean(verify_rows)
    if any(row.error for row in rows):
        score -= 15
    score = max(0.0, min(100.0, score))

    signals: list[str] = []
    if completion < 0.8:
        signals.append("completion_below_baseline")
    if structured < 0.8:
        signals.append("structured_output_below_baseline")
    if tool_rows and mean(tool_rows) < 0.8:
        signals.append("tool_call_rate_below_baseline")
    if verify_rows and mean(verify_rows) < 0.8:
        signals.append("verification_rate_below_baseline")
    if any(row.error for row in rows):
        signals.append("benchmark_errors")

    return BenchmarkSummary(
        route=route,
        task_count=len(rows),
        completion_rate=completion,
        structured_rate=structured,
        tool_call_rate=mean(tool_rows) if tool_rows else None,
        verification_rate=mean(verify_rows) if verify_rows else None,
        average_latency_ms=mean(latency_rows) if latency_rows else None,
        total_cost=total_cost,
        score=score,
        signals=tuple(signals),
    )
