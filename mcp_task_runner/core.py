"""Small deterministic core for safe MCP/API task execution.

The model/planner and transport adapters are deliberately outside this module.
This layer owns the safety boundary and produces evidence that can be audited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Callable, Protocol
from uuid import uuid4


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.DESTRUCTIVE
    supports_verify: bool = False
    handler: Callable[[dict[str, Any]], Any] | None = field(default=None, repr=False, compare=False)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())


class ApprovalGateway(Protocol):
    def request(self, task_id: str, tool: ToolSpec, arguments: dict[str, Any]) -> "ApprovalDecision": ...


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    approver: str
    reason: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    tool_name: str
    status: str
    value: Any = None
    error: str | None = None


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


class EvidenceLog:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, event: str, **data: Any) -> None:
        self.events.append({"event": event, "timestamp": time(), **data})


class TaskRunner:
    def __init__(self, registry: ToolRegistry, approvals: ApprovalGateway, evidence: EvidenceLog | None = None) -> None:
        self.registry = registry
        self.approvals = approvals
        self.evidence = evidence or EvidenceLog()

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        verifier: Callable[[Any], VerificationResult] | None = None,
    ) -> ExecutionResult:
        task_id = str(uuid4())
        tool = self.registry.get(tool_name)
        self.evidence.append("task_planned", task_id=task_id, tool=tool.name, risk=tool.risk_level.value)

        if tool.handler is None:
            result = ExecutionResult(task_id, tool.name, "failed", error="tool has no handler")
            self.evidence.append("tool_failed", task_id=task_id, error=result.error)
            return result

        # Fail closed: only read-only work can run without a decision.
        if tool.risk_level is not RiskLevel.READ_ONLY:
            decision = self.approvals.request(task_id, tool, arguments)
            self.evidence.append(
                "approval_decided",
                task_id=task_id,
                approved=decision.approved,
                approver=decision.approver,
                reason=decision.reason,
            )
            if not decision.approved:
                return ExecutionResult(task_id, tool.name, "rejected", error=decision.reason or "approval denied")

        try:
            value = tool.handler(arguments)
        except Exception as exc:  # evidence boundary: handlers must not escape the runner
            self.evidence.append("tool_failed", task_id=task_id, error=str(exc))
            return ExecutionResult(task_id, tool.name, "failed", error=str(exc))

        result = ExecutionResult(task_id, tool.name, "executed", value=value)
        self.evidence.append("tool_executed", task_id=task_id, result=value)

        if verifier is not None:
            verification = verifier(value)
            self.evidence.append(
                "verification_completed",
                task_id=task_id,
                passed=verification.passed,
                summary=verification.summary,
                details=verification.details,
            )
            if not verification.passed:
                return ExecutionResult(task_id, tool.name, "verification_failed", value=value)

        return result
