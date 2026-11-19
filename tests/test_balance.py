import pytest

from mcp_task_runner.balance import BalancePolicy, BalanceSeverity, BalanceSnapshot, evaluate_balance


def test_balance_warning_and_critical_alerts():
    policy = BalancePolicy(warning_threshold=10, critical_threshold=2)
    assert evaluate_balance(BalanceSnapshot("loomex", 16.6), policy).severity is BalanceSeverity.NORMAL
    assert evaluate_balance(BalanceSnapshot("loomex", 8), policy).severity is BalanceSeverity.WARNING
    critical = evaluate_balance(BalanceSnapshot("loomex", 1.5), policy)
    assert critical.severity is BalanceSeverity.CRITICAL
    assert critical.should_exclude is True


def test_unknown_balance_is_not_silently_healthy():
    alert = evaluate_balance(BalanceSnapshot("unknown", None), BalancePolicy(10, 2))
    assert alert.severity is BalanceSeverity.UNKNOWN
    assert alert.should_exclude is False


def test_policy_threshold_order_is_checked():
    with pytest.raises(ValueError):
        BalancePolicy(warning_threshold=1, critical_threshold=2)
