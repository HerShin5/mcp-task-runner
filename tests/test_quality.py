from mcp_task_runner.quality import QualityObservation, QualityState, assess_quality


def test_healthy_route_stays_eligible():
    result = assess_quality(QualityObservation("terra@gateway-a"))
    assert result.state is QualityState.HEALTHY
    assert result.should_deprioritize is False


def test_missing_tool_call_and_verification_failure_suspect_route():
    result = assess_quality(
        QualityObservation(
            "terra@gateway-a",
            tool_call_expected=True,
            tool_call_observed=False,
            verification_passed=False,
        )
    )
    assert result.state in {QualityState.SUSPECT, QualityState.DEGRADED}
    assert "expected_tool_call_missing" in result.signals
    assert result.should_deprioritize is True


def test_canary_and_request_failure_can_circuit_break():
    result = assess_quality(QualityObservation("astra@gateway-c", probe_passed=False, error=True))
    assert result.state is QualityState.BLOCKED
    assert result.should_circuit_break is True
