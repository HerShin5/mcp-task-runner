"""Balance monitoring and alert policy for gateway management adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BalanceSeverity(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BalanceSnapshot:
    gateway: str
    balance: float | None
    currency: str = "USD"
    source: str = "management_api"
    observed_at: float | None = None


@dataclass(frozen=True)
class BalancePolicy:
    warning_threshold: float
    critical_threshold: float
    exclude_below_critical: bool = True

    def __post_init__(self) -> None:
        if self.warning_threshold < self.critical_threshold:
            raise ValueError("warning threshold must be >= critical threshold")
        if self.critical_threshold < 0:
            raise ValueError("critical threshold cannot be negative")


@dataclass(frozen=True)
class BalanceAlert:
    gateway: str
    severity: BalanceSeverity
    balance: float | None
    message: str
    should_exclude: bool


def evaluate_balance(snapshot: BalanceSnapshot, policy: BalancePolicy) -> BalanceAlert:
    if snapshot.balance is None:
        return BalanceAlert(snapshot.gateway, BalanceSeverity.UNKNOWN, None, "balance unavailable", False)
    if snapshot.balance <= policy.critical_threshold:
        return BalanceAlert(
            snapshot.gateway,
            BalanceSeverity.CRITICAL,
            snapshot.balance,
            f"balance {snapshot.balance:.4f} {snapshot.currency} is at or below critical threshold",
            policy.exclude_below_critical,
        )
    if snapshot.balance <= policy.warning_threshold:
        return BalanceAlert(
            snapshot.gateway,
            BalanceSeverity.WARNING,
            snapshot.balance,
            f"balance {snapshot.balance:.4f} {snapshot.currency} is at or below warning threshold",
            False,
        )
    return BalanceAlert(snapshot.gateway, BalanceSeverity.NORMAL, snapshot.balance, "balance is healthy", False)
