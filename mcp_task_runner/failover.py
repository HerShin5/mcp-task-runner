"""Retry, fallback, and circuit-breaker policy for model routes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import Callable, Iterable, TypeVar


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class Circuit:
    failures: int = 0
    state: CircuitState = CircuitState.CLOSED
    opened_at: float | None = None


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 3, cooldown_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._circuits: dict[str, Circuit] = {}

    def state(self, route: str) -> CircuitState:
        circuit = self._circuits.setdefault(route, Circuit())
        if circuit.state is CircuitState.OPEN and circuit.opened_at is not None:
            if monotonic() - circuit.opened_at >= self.cooldown_seconds:
                circuit.state = CircuitState.HALF_OPEN
        return circuit.state

    def allow(self, route: str) -> bool:
        return self.state(route) is not CircuitState.OPEN

    def record_success(self, route: str) -> None:
        self._circuits[route] = Circuit()

    def record_failure(self, route: str) -> CircuitState:
        circuit = self._circuits.setdefault(route, Circuit())
        circuit.failures += 1
        if circuit.failures >= self.failure_threshold:
            circuit.state = CircuitState.OPEN
            circuit.opened_at = monotonic()
        return circuit.state


T = TypeVar("T")


@dataclass(frozen=True)
class FailoverResult:
    value: T | None
    route: str | None
    attempts: tuple[str, ...]
    errors: tuple[str, ...]


def is_retryable_error(error: BaseException) -> bool:
    """Transport-like failures may fail over; policy/input errors may not."""
    text = str(error).lower()
    if any(code in text for code in ("400", "401", "403", "404", "422")):
        return False
    return any(marker in text for marker in ("timeout", "429", "502", "503", "504", "connection", "temporarily"))


def execute_with_failover(
    routes: Iterable[str],
    call: Callable[[str], T],
    breaker: CircuitBreaker,
) -> FailoverResult[T]:
    attempts: list[str] = []
    errors: list[str] = []
    for route in routes:
        if not breaker.allow(route):
            continue
        attempts.append(route)
        try:
            value = call(route)
            breaker.record_success(route)
            return FailoverResult(value, route, tuple(attempts), tuple(errors))
        except Exception as exc:
            errors.append(f"{route}: {exc}")
            breaker.record_failure(route)
            if not is_retryable_error(exc):
                break
    return FailoverResult(None, None, tuple(attempts), tuple(errors))
