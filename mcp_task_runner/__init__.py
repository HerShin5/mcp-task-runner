"""Safety-first MCP task execution core."""

from .mcp_http import McpEndpoint, McpProtocolError, StreamableHttpMcpClient
from .approvals import ApprovalStatus, ApprovalStore, FeishuApprovalGateway, LocalApprovalGateway
from .providers import ProviderConfig, ProviderHealth, check_provider, choose_first_healthy, load_provider_configs
from .planner import PlanStep, PlanValidationError, TaskPlan, parse_and_validate
from .routing import PricingBand, RouteCandidate, RouteDecision, RouteObjective, RoutePricing, load_route_pricing, select_route
from .gateway_catalog import GatewayCatalog, GatewaySnapshot
from .balance import BalanceAlert, BalancePolicy, BalanceSeverity, BalanceSnapshot, evaluate_balance
from .quality import QualityAssessment, QualityObservation, QualityState, assess_quality
from .capabilities import ModelCandidate, ModelProfile, TaskRequirements, choose_model, load_model_profiles, profile_from_dict, score_candidate
from .benchmarks import BenchmarkObservation, BenchmarkSummary, BenchmarkTask, summarize_observations
from .model_client import ModelClientError, ModelReply, OpenAICompatibleClient
from .planning import PlannedTask, plan_task
from .model_routing import ModelRouteCandidate, ModelRouteDecision, choose_model_and_gateway
from .orchestrator import RoutedPlan, RoutingDecision, StaticTaskClassifier, TaskClassifier, plan_with_route
from .mcp_registry import DEFAULT_READ_ONLY_TOOLS, register_discovered_tools
from .windows_report import DiagnosticResult, collect_read_only_report
from .health_report import normalize_health_report
from .repair_plan import build_repair_plan, render_repair_plan
from .feishu_card import build_approval_card, serialize_card
from .approval_callbacks import ApprovalCallbackHandler, CallbackResult, approval_request_dict
from .mock_executor import MockApprovedExecutor, MockExecutionResult
from .approval_demo import run_local_approval_demo
from .persistence import SQLiteApprovalStore
from .plan_executor import PlanExecutionResult, execute_read_only_plan
from .windows_workflow import WindowsWorkflowResult, run_read_only_workflow
from .failover import CircuitBreaker, CircuitState, FailoverResult, execute_with_failover, is_retryable_error
from .routed_client import RoutedChatResult, RoutedModelClient, RoutedPlanClient
from .management import AccountSnapshot, GenericHttpManagementAdapter, GroupSnapshot, ManagementAdapterError, ManagementRoute, ManagementSnapshot, ManagementSnapshotStore, ModelSnapshot, load_snapshot_fixture, resolve_management_route, snapshot_from_generic_payload
from .classifier import HeuristicTaskClassifier
from .core import (
    ApprovalDecision,
    ApprovalGateway,
    EvidenceLog,
    ExecutionResult,
    RiskLevel,
    TaskRunner,
    ToolRegistry,
    ToolSpec,
    VerificationResult,
)

__all__ = [
    "ApprovalDecision",
    "ApprovalGateway",
    "EvidenceLog",
    "ExecutionResult",
    "RiskLevel",
    "TaskRunner",
    "ToolRegistry",
    "ToolSpec",
    "VerificationResult",
    "McpEndpoint",
    "McpProtocolError",
    "StreamableHttpMcpClient",
    "ApprovalStatus",
    "ApprovalStore",
    "FeishuApprovalGateway",
    "LocalApprovalGateway",
    "ProviderConfig",
    "ProviderHealth",
    "check_provider",
    "choose_first_healthy",
    "load_provider_configs",
    "PlanStep",
    "PlanValidationError",
    "TaskPlan",
    "parse_and_validate",
    "PricingBand",
    "RouteCandidate",
    "RouteDecision",
    "RouteObjective",
    "RoutePricing",
    "load_route_pricing",
    "select_route",
    "GatewayCatalog",
    "GatewaySnapshot",
    "BalanceAlert",
    "BalancePolicy",
    "BalanceSeverity",
    "BalanceSnapshot",
    "evaluate_balance",
    "QualityAssessment",
    "QualityObservation",
    "QualityState",
    "assess_quality",
    "ModelCandidate",
    "ModelProfile",
    "TaskRequirements",
    "choose_model",
    "load_model_profiles",
    "profile_from_dict",
    "score_candidate",
    "BenchmarkObservation",
    "BenchmarkSummary",
    "BenchmarkTask",
    "summarize_observations",
    "ModelClientError",
    "ModelReply",
    "OpenAICompatibleClient",
    "PlannedTask",
    "plan_task",
    "ModelRouteCandidate",
    "ModelRouteDecision",
    "choose_model_and_gateway",
    "RoutedPlan",
    "RoutingDecision",
    "StaticTaskClassifier",
    "TaskClassifier",
    "plan_with_route",
    "DEFAULT_READ_ONLY_TOOLS",
    "register_discovered_tools",
    "DiagnosticResult",
    "collect_read_only_report",
    "normalize_health_report",
    "build_repair_plan",
    "render_repair_plan",
    "build_approval_card",
    "serialize_card",
    "ApprovalCallbackHandler",
    "CallbackResult",
    "approval_request_dict",
    "MockApprovedExecutor",
    "MockExecutionResult",
    "run_local_approval_demo",
    "SQLiteApprovalStore",
    "PlanExecutionResult",
    "execute_read_only_plan",
    "WindowsWorkflowResult",
    "run_read_only_workflow",
    "CircuitBreaker",
    "CircuitState",
    "FailoverResult",
    "execute_with_failover",
    "is_retryable_error",
    "RoutedChatResult",
    "RoutedModelClient",
    "RoutedPlanClient",
    "AccountSnapshot",
    "GenericHttpManagementAdapter",
    "GroupSnapshot",
    "ManagementAdapterError",
    "ManagementRoute",
    "ManagementSnapshot",
    "ManagementSnapshotStore",
    "ModelSnapshot",
    "load_snapshot_fixture",
    "resolve_management_route",
    "snapshot_from_generic_payload",
    "HeuristicTaskClassifier",
]
