"""Command-line entry point for local inspection and safe MVP flows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .approvals import ApprovalStore, LocalApprovalGateway
from .core import EvidenceLog, RiskLevel, TaskRunner, ToolRegistry, ToolSpec, VerificationResult
from .mcp_http import McpEndpoint, StreamableHttpMcpClient
from .providers import ProviderConfig, ProviderHealth, check_provider, choose_first_healthy, load_provider_configs
from .planner import PlanValidationError, parse_and_validate
from .model_client import ModelClientError, ModelReply, OpenAICompatibleClient
from .routing import PricingBand, RouteObjective, RoutePricing, load_route_pricing, select_route
from .windows_diagnostics import build_read_only_plan, discover_endpoint
from .windows_report import collect_read_only_report
from .health_report import normalize_health_report, render_human_report
from .repair_plan import build_repair_plan, render_repair_plan
from .capabilities import ModelProfile, load_model_profiles
from .classifier import HeuristicTaskClassifier
from .model_routing import choose_model_and_gateway
from .orchestrator import plan_with_route
from .quality import QualityAssessment
from .mcp_registry import register_discovered_tools
from .gateway_catalog import GatewayCatalog
from .management import GenericHttpManagementAdapter
from .routed_client import RoutedModelClient, RoutedPlanClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-task-runner")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("providers-health", help="check configured OpenAI-compatible providers")
    health.add_argument("--config", default="providers.json")

    route = sub.add_parser("route-select", help="select the cheapest healthy model route")
    route.add_argument("--config", default="providers.json")
    route.add_argument("--input-tokens", type=int, required=True)
    route.add_argument("--output-tokens", type=int, required=True)
    route.add_argument("--objective", choices=[item.value for item in RouteObjective], default=RouteObjective.COST.value)

    tools = sub.add_parser("mcp-tools", help="discover tools from an already-running MCP endpoint")
    _add_endpoint_options(tools)

    report = sub.add_parser("windows-report", help="run reviewed read-only Windows-MCP checks")
    _add_endpoint_options(report)
    report.add_argument("--format", choices=["json", "text"], default="json")
    report.add_argument("--ascii", action="store_true", help="use ASCII status markers for legacy Windows consoles")
    report.add_argument("--repair-plan", action="store_true", help="also print a non-executable remediation proposal")

    plan = sub.add_parser("diagnose-plan", help="print the read-only Windows-MCP diagnostic plan")
    plan.add_argument("--url", default="http://127.0.0.1:8766/mcp")

    demo = sub.add_parser("approval-demo", help="run the local approval and verification demo")
    demo.add_argument("--approve", action="store_true", help="approve the simulated write action")

    route_demo = sub.add_parser("orchestrate-demo", help="offline task-to-model-to-plan demonstration")
    route_demo.add_argument("goal", nargs="+", help="task in plain language")

    validate = sub.add_parser("plan-validate", help="validate an AI-generated JSON plan against the tool registry")
    validate.add_argument("plan", type=Path)

    live_plan = sub.add_parser("live-plan", help="select a route and generate a plan without executing tools")
    live_plan.add_argument("goal", nargs="+")
    live_plan.add_argument("--providers", default="providers.json")
    live_plan.add_argument("--profiles", default="model_profiles.example.json")
    live_plan.add_argument("--input-tokens", type=int, default=4000)
    live_plan.add_argument("--output-tokens", type=int, default=1000)
    live_plan.add_argument("--management-url", help="optional authorized JSON management endpoint")
    live_plan.add_argument("--management-provider", help="provider name for --management-url")
    live_plan.add_argument("--management-token-env", default="MCP_TASK_RUNNER_MANAGEMENT_TOKEN")
    live_plan.add_argument("--management-max-age", type=float, default=300.0)

    return parser


def _add_endpoint_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", default="http://127.0.0.1:8766/mcp")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--timeout", type=float, default=8.0)


def _client_from_args(args: argparse.Namespace) -> StreamableHttpMcpClient:
    token = args.token_file.read_text(encoding="utf-8").strip() if args.token_file else None
    return StreamableHttpMcpClient(McpEndpoint(args.url, timeout=args.timeout, bearer_token=token))


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "providers-health":
        catalog = GatewayCatalog(args.config)
        snapshots = catalog.health()
        health = [item.health for item in snapshots]
        selected = choose_first_healthy(catalog.providers, health)
        print(json.dumps({"providers": [item.__dict__ for item in health], "selected": selected.name if selected else None}, indent=2))
        return 0 if selected else 1

    if args.command == "route-select":
        catalog = GatewayCatalog(args.config)
        decision = catalog.select(
            input_tokens=args.input_tokens,
            output_tokens=args.output_tokens,
            objective=RouteObjective(args.objective),
        )
        print(json.dumps({
            "selected": decision.selected.provider.name if decision.selected else None,
            "reason": decision.reason,
            "candidates": [
                {
                    "provider": item.provider.name,
                    "model": item.provider.model,
                    "estimated_cost": item.estimated_cost,
                    "score": item.score,
                    "latency_ms": item.health.latency_ms,
                }
                for item in decision.candidates
            ],
        }, ensure_ascii=False, indent=2))
        return 0 if decision.selected else 1

    if args.command == "mcp-tools":
        discovery = discover_endpoint(_client_from_args(args))
        registry = ToolRegistry()
        registered = register_discovered_tools(registry, discovery["tools"])
        discovery["local_registry"] = [
            {"name": item.name, "risk": item.risk_level.value, "supports_verify": item.supports_verify}
            for item in registered
        ]
        print(json.dumps(discovery, ensure_ascii=False, indent=2))
        return 0

    if args.command == "windows-report":
        raw_report = collect_read_only_report(_client_from_args(args))
        report = normalize_health_report(raw_report)
        if args.format == "text":
            ascii_only = args.ascii or (sys.stdout.encoding or "").lower() not in {"utf-8", "utf8"}
            print(render_human_report(report, ascii_only=ascii_only))
            if args.repair_plan:
                print("\n" + render_repair_plan(build_repair_plan(report)))
        else:
            payload = {"report": report}
            if args.repair_plan:
                payload["repair_plan"] = build_repair_plan(report)
            print(json.dumps(payload if args.repair_plan else report, ensure_ascii=False, indent=2))
        return 0

    if args.command == "diagnose-plan":
        print(json.dumps(build_read_only_plan(endpoint=args.url), ensure_ascii=False, indent=2))
        return 0

    if args.command == "approval-demo":
        store = ApprovalStore()
        evidence = EvidenceLog()
        approvals = LocalApprovalGateway(store, approve=args.approve)
        registry = ToolRegistry()
        registry.register(ToolSpec("restart_demo", "simulated service restart", RiskLevel.WRITE, True, lambda _: {"restarted": True}))
        result = TaskRunner(registry, approvals, evidence).execute(
            "restart_demo",
            {},
            lambda value: VerificationResult(value.get("restarted") is True, "simulated post-check"),
        )
        print(json.dumps({"result": result.__dict__, "evidence": evidence.events}, ensure_ascii=False, indent=2))
        return 0 if result.status in {"executed", "verification_failed"} else 2

    if args.command == "orchestrate-demo":
        goal = " ".join(args.goal)
        registry = ToolRegistry()
        registry.register(ToolSpec("health", "read-only health check", RiskLevel.READ_ONLY, True))
        registry.register(ToolSpec("inspect_repository", "read-only repository inspection", RiskLevel.READ_ONLY, True))
        profiles = [
            ModelProfile("gpt-astra", {"reasoning": 2, "coding": 2, "tool_calling": 2, "structured_output": 3, "chinese": 4}),
            ModelProfile("gpt-terra", {"reasoning": 5, "coding": 5, "tool_calling": 5, "structured_output": 5, "chinese": 4}),
        ]
        providers = [
            ProviderConfig("gateway-low", "https://demo.invalid/v1", "gpt-astra", models=("gpt-astra",), priority=1),
            ProviderConfig("gateway-quality", "https://demo.invalid/v1", "gpt-terra", models=("gpt-terra",), priority=2),
        ]
        health = [
            ProviderHealth("gateway-low", True, 200, "offline demo healthy", "gpt-astra", True, 80),
            ProviderHealth("gateway-quality", True, 200, "offline demo healthy", "gpt-terra", True, 110),
        ]
        pricing = [
            RoutePricing("gateway-low", "gpt-astra", PricingBand(0.01, 0.01)),
            RoutePricing("gateway-quality", "gpt-terra", PricingBand(0.05, 0.05)),
        ]

        class LocalPlanClient:
            provider = "offline-demo"
            model = "selected-model-simulated"

            def chat(self, messages, *, response_format=None):
                content = '{"goal":"' + goal.replace('"', "'") + '","requires_approval":false,"steps":[{"id":"step-1","tool":"health","arguments":{},"purpose":"run read-only health check","verify":true}]}'
                return ModelReply(content, self.provider, self.model, 0.0, 200, {})

        try:
            result = plan_with_route(
                user_goal=goal,
                classifier=HeuristicTaskClassifier(),
                profiles=profiles,
                providers=providers,
                health=health,
                pricing=pricing,
                registry=registry,
                client_factory=lambda _: LocalPlanClient(),
                input_tokens=500,
                output_tokens=300,
            )
        except RuntimeError as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
            return 2
        print(json.dumps({
            "task_type": result.decision.task_requirements.task_type,
            "requirements": result.decision.task_requirements.minimum,
            "selected_model": result.decision.model_route.selected.model.name,
            "selected_gateway": result.decision.model_route.selected.provider.name,
            "estimated_cost": result.decision.model_route.selected.estimated_cost,
            "plan": result.plan.to_dict(),
            "mode": "offline simulation; no network requests",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "plan-validate":
        registry = ToolRegistry()
        registry.register(ToolSpec("health", "read-only health check", RiskLevel.READ_ONLY, True))
        registry.register(ToolSpec("restart_demo", "simulated service restart", RiskLevel.WRITE, True))
        try:
            plan = parse_and_validate(args.plan.read_text(encoding="utf-8"), registry)
        except (OSError, PlanValidationError) as exc:
            print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
            return 2
        print(json.dumps({"valid": True, "plan": plan.to_dict()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "live-plan":
        goal = " ".join(args.goal)
        catalog = GatewayCatalog(args.providers)
        if args.management_url:
            if not args.management_provider:
                print(json.dumps({"error": "--management-provider is required with --management-url"}, ensure_ascii=False))
                return 2
            catalog.register_management_adapter(
                GenericHttpManagementAdapter(
                    args.management_provider,
                    args.management_url,
                    token=os.environ.get(args.management_token_env),
                ),
                max_age_seconds=args.management_max_age,
            )
        snapshots = catalog.health()
        providers = catalog.providers
        profiles = load_model_profiles(args.profiles)
        health = [item.health for item in snapshots]
        pricing = catalog.pricing
        management = [item.management for item in snapshots if item.management is not None]
        registry = ToolRegistry()
        registry.register(ToolSpec("health", "read-only health check", RiskLevel.READ_ONLY, True))
        registry.register(ToolSpec("inspect_repository", "read-only repository inspection", RiskLevel.READ_ONLY, True))
        requirements = HeuristicTaskClassifier().classify(goal)
        quality: list[QualityAssessment] = []
        decision = choose_model_and_gateway(
            profiles, providers, health, pricing, requirements,
            input_tokens=args.input_tokens, output_tokens=args.output_tokens, quality=quality,
        )
        if decision.selected is None:
            print(json.dumps({"error": "no capable healthy model/gateway route"}, ensure_ascii=False))
            return 2
        selected = decision.selected
        route_order = [
            item.provider.name
            for item in decision.candidates
            if item.model.name == selected.model.name
        ]
        client = RoutedPlanClient(RoutedModelClient(providers), selected.model.name, route_order)
        try:
            result = plan_with_route(
                user_goal=goal,
                classifier=HeuristicTaskClassifier(),
                profiles=profiles,
                providers=providers,
                health=health,
                pricing=pricing,
                registry=registry,
                client_factory=lambda _: client,
                input_tokens=args.input_tokens,
                output_tokens=args.output_tokens,
                management=management,
            )
        except (ModelClientError, PlanValidationError) as exc:
            print(json.dumps({"error": "model_plan_rejected", "detail": str(exc)}, ensure_ascii=False))
            return 2
        print(json.dumps({
            "selected_model": result.model,
            "selected_gateway": result.provider,
            "task_type": result.decision.task_requirements.task_type,
            "requirements": result.decision.task_requirements.minimum,
            "usage": result.usage,
            "latency_ms": result.latency_ms,
            "plan": result.plan.to_dict(),
            "execution": "not_started",
            "failover": {
                "attempts": list(client.last_result.attempts) if client.last_result else [],
                "route": client.last_result.route if client.last_result else None,
                "errors": list(client.last_result.errors) if client.last_result else [],
            },
        }, ensure_ascii=False, indent=2))
        return 0

    return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
