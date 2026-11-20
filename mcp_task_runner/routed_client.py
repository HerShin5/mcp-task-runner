"""OpenAI-compatible model client with bounded route failover."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .failover import CircuitBreaker, FailoverResult, execute_with_failover
from .model_client import ModelReply, OpenAICompatibleClient
from .providers import ProviderConfig


@dataclass(frozen=True)
class RoutedChatResult:
    reply: ModelReply | None
    route: str | None
    attempts: tuple[str, ...]
    errors: tuple[str, ...]


class RoutedModelClient:
    """Select from pre-ranked providers and fail over before first output."""

    def __init__(self, providers: list[ProviderConfig], *, breaker: CircuitBreaker | None = None):
        self.providers = providers
        self.breaker = breaker or CircuitBreaker()

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_format: dict[str, Any] | None = None,
        route_order: list[str] | None = None,
        client_factory: Callable[[ProviderConfig], OpenAICompatibleClient] | None = None,
    ) -> RoutedChatResult:
        candidates = route_order or [provider.name for provider in self.providers if provider.supports_model(model)]
        by_name = {provider.name: provider for provider in self.providers}
        factory = client_factory or (lambda provider: OpenAICompatibleClient(
            base_url=provider.base_url,
            api_key=provider.api_key,
            provider=provider.name,
            model=model,
            timeout=provider.timeout,
        ))

        def call(route: str) -> ModelReply:
            provider = by_name[route]
            return factory(provider).chat(messages, response_format=response_format)

        result: FailoverResult[ModelReply] = execute_with_failover(candidates, call, self.breaker)
        return RoutedChatResult(result.value, result.route, result.attempts, result.errors)
