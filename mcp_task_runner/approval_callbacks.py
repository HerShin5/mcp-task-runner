"""Provider-neutral approval callback handling.

This module processes button-like approval payloads locally. A future Feishu
adapter can translate its callback JSON into the same shape without moving
approval policy into the provider integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .approvals import AlreadyDecided, ApprovalRequest, ApprovalStore


@dataclass(frozen=True)
class CallbackResult:
    accepted: bool
    task_id: str
    status: str
    message: str


class ApprovalCallbackHandler:
    def __init__(self, store: ApprovalStore, *, allowed_approvers: set[str] | None = None):
        self.store = store
        self.allowed_approvers = allowed_approvers

    def handle(self, payload: dict[str, Any], *, approver: str) -> CallbackResult:
        task_id = payload.get("task_id")
        action = payload.get("action")
        if not isinstance(task_id, str) or not task_id:
            return CallbackResult(False, "", "invalid", "task_id is required")
        if action not in {"approve", "reject"}:
            return CallbackResult(False, task_id, "invalid", "action must be approve or reject")
        if self.allowed_approvers is not None and approver not in self.allowed_approvers:
            return CallbackResult(False, task_id, "forbidden", "approver is not allowed")
        try:
            updated = self.store.decide(task_id, approved=action == "approve", approver=approver,
                                        reason=f"callback action: {action}")
        except KeyError:
            return CallbackResult(False, task_id, "not_found", "approval request not found")
        except AlreadyDecided:
            return CallbackResult(False, task_id, self.store.get(task_id).status.value, "approval is already decided")
        return CallbackResult(True, task_id, updated.status.value, "approval recorded")


def approval_request_dict(request: ApprovalRequest) -> dict[str, Any]:
    return {
        "task_id": request.task_id,
        "tool": request.tool.name,
        "risk": request.tool.risk_level.value,
        "status": request.status.value,
        "approver": request.approver,
        "reason": request.reason,
    }
