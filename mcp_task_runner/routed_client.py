"""OpenAI-compatible model client with bounded route failover."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .failover import CircuitBreaker, FailoverResult, execute_with_failover
from .model_client import ModelClientError, ModelReply, OpenAICompatibleClient
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
        response_started: bool = False,
        external_side_effect: bool = False,
    ) -> RoutedChatResult:
        candidates = route_order if route_order is not None else [provider.name for provider in self.providers if provider.supports_model(model)]
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

        result: FailoverResult[ModelReply] = execute_with_failover(
            candidates,
            call,
            self.breaker,
            response_started=response_started,
            external_side_effect=external_side_effect,
        )
        return RoutedChatResult(result.value, result.route, result.attempts, result.errors)


class RoutedPlanClient:
    """Adapter that gives the planner a failover-aware ``chat`` interface."""

    def __init__(
        self,
        router: RoutedModelClient,
        model: str,
        route_order: list[str],
        *,
        client_factory: Callable[[ProviderConfig], OpenAICompatibleClient] | None = None,
        model_timeout: float = 30.0,
    ):
        if model_timeout <= 0:
            raise ValueError("model timeout must be positive")
        self.router = router
        self.model = model
        self.route_order = route_order
        self.client_factory = client_factory or (lambda provider: OpenAICompatibleClient(
            base_url=provider.base_url,
            api_key=provider.api_key,
            provider=provider.name,
            model=model,
            timeout=model_timeout,
        ))
        self.last_result: RoutedChatResult | None = None

    def chat(self, messages: list[dict[str, str]], *, response_format: dict[str, Any] | None = None) -> ModelReply:
        result = self.router.chat(
            messages,
            model=self.model,
            response_format=response_format,
            route_order=self.route_order,
            client_factory=self.client_factory,
        )
        self.last_result = result
        if result.reply is None:
            detail = "; ".join(result.errors) or "all candidate routes failed"
            raise ModelClientError(f"model plan request failed after failover: {detail}")
        return result.reply
