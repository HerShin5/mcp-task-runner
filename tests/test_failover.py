from mcp_task_runner.failover import CircuitBreaker, CircuitState, execute_with_failover, is_retryable_error


def test_failover_uses_second_route_after_retryable_failure():
    breaker = CircuitBreaker(failure_threshold=2)
    calls = []

    def call(route):
        calls.append(route)
        if route == "bad":
            raise TimeoutError("request timeout")
        return "ok"

    result = execute_with_failover(["bad", "good"], call, breaker)
    assert result.value == "ok"
    assert result.route == "good"
    assert calls == ["bad", "good"]


def test_circuit_opens_after_repeated_failures():
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=1000)
    assert breaker.record_failure("bad") is CircuitState.CLOSED
    assert breaker.record_failure("bad") is CircuitState.OPEN
    assert breaker.allow("bad") is False


def test_non_retryable_auth_error_does_not_failover():
    assert is_retryable_error(RuntimeError("HTTP 401 invalid key")) is False
    assert is_retryable_error(RuntimeError("HTTP 503 upstream timeout")) is True


def test_started_response_does_not_failover_even_on_timeout():
    calls = []

    def call(route):
        calls.append(route)
        raise TimeoutError("upstream timeout after partial output")

    result = execute_with_failover(
        ["first", "second"],
        call,
        CircuitBreaker(),
        response_started=True,
    )
    assert result.value is None
    assert result.attempts == ("first",)
    assert calls == ["first"]


def test_external_side_effect_does_not_repeat_on_retryable_error():
    calls = []

    def call(route):
        calls.append(route)
        raise RuntimeError("HTTP 503 after external side effect")

    result = execute_with_failover(
        ["first", "second"],
        call,
        CircuitBreaker(),
        external_side_effect=True,
    )
    assert result.attempts == ("first",)
    assert calls == ["first"]
