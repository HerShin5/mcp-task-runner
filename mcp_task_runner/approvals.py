"""Approval state machine shared by CLI, API, and Feishu adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from time import time
from typing import Any

from .core import ApprovalDecision, ApprovalGateway, ToolSpec


class AlreadyDecided(ValueError):
    """A concurrent or repeated decision lost the pending-state transition."""


class ApprovalStatus(str, Enum):
    PENDING = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    task_id: str
    tool: ToolSpec
    arguments: dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    requester: str = "system"
    approver: str | None = None
    reason: str = ""
    created_at: float = 0.0
    decided_at: float | None = None


class ApprovalStore:
    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = Lock()

    def create(self, task_id: str, tool: ToolSpec, arguments: dict[str, Any], *, requester: str = "system") -> ApprovalRequest:
        request = ApprovalRequest(task_id, tool, dict(arguments), requester=requester, created_at=time())
        with self._lock:
            if task_id in self._requests:
                raise ValueError("approval task ID already exists")
            self._requests[task_id] = request
        return request

    def get(self, task_id: str) -> ApprovalRequest:
        with self._lock:
            return self._requests[task_id]

    def decide(self, task_id: str, *, approved: bool, approver: str, reason: str = "") -> ApprovalRequest:
        with self._lock:
            request = self._requests[task_id]
            if request.status is not ApprovalStatus.PENDING:
                raise AlreadyDecided(f"approval is already {request.status.value}")
            request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            request.approver = approver
            request.reason = reason
            request.decided_at = time()
            return request


class LocalApprovalGateway(ApprovalGateway):
    """Deterministic adapter for tests and local CLI experiments."""

    def __init__(self, store: ApprovalStore, *, approve: bool = False, approver: str = "local-user"):
        self.store = store
        self.approve = approve
        self.approver = approver

    def request(self, task_id: str, tool: ToolSpec, arguments: dict[str, Any]) -> ApprovalDecision:
        self.store.create(task_id, tool, arguments)
        request = self.store.decide(
            task_id,
            approved=self.approve,
            approver=self.approver,
            reason="local adapter decision",
        )
        return ApprovalDecision(request.status is ApprovalStatus.APPROVED, self.approver, request.reason)


class FeishuApprovalGateway(ApprovalGateway):
    """Adapter seam for Feishu interactive cards.

    The actual Feishu HTTP client is intentionally injected later. This class
    records a pending request and delegates card delivery to `send_card`.
    """

    def __init__(self, store: ApprovalStore, send_card):
        self.store = store
        self.send_card = send_card

    def request(self, task_id: str, tool: ToolSpec, arguments: dict[str, Any]) -> ApprovalDecision:
        request = self.store.create(task_id, tool, arguments)
        self.send_card(request)
        return ApprovalDecision(False, "feishu-pending", "waiting for Feishu approval")
