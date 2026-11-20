from mcp_task_runner.failover import CircuitBreaker
from mcp_task_runner.model_client import ModelReply, ModelClientError
from mcp_task_runner.providers import ProviderConfig
from mcp_task_runner.routed_client import RoutedModelClient


def test_routed_model_client_fails_over_on_timeout():
    providers = [
        ProviderConfig("bad", "https://bad/v1", "model"),
        ProviderConfig("good", "https://good/v1", "model"),
    ]
    calls = []

    def factory(provider):
        class Fake:
            def chat(self, messages, *, response_format=None):
                calls.append(provider.name)
                if provider.name == "bad":
                    raise ModelClientError("request timeout")
                return ModelReply("ok", provider.name, "model", 1.0, 200, {})
        return Fake()

    result = RoutedModelClient(providers, breaker=CircuitBreaker()).chat(
        [{"role": "user", "content": "hi"}], model="model", client_factory=factory
    )
    assert result.reply.text == "ok"
    assert result.route == "good"
    assert calls == ["bad", "good"]


def test_routed_model_client_does_not_fail_over_on_auth_error():
    providers = [
        ProviderConfig("bad", "https://bad/v1", "model"),
        ProviderConfig("good", "https://good/v1", "model"),
    ]
    calls = []

    def factory(provider):
        class Fake:
            def chat(self, messages, *, response_format=None):
                calls.append(provider.name)
                raise ModelClientError("HTTP 401 invalid key")
        return Fake()

    result = RoutedModelClient(providers).chat(
        [{"role": "user", "content": "hi"}], model="model", client_factory=factory
    )
    assert result.reply is None
    assert calls == ["bad"]
