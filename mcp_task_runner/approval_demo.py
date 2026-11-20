"""End-to-end local approval demo with no external side effects."""

from __future__ import annotations

from typing import Any

from .approval_callbacks import ApprovalCallbackHandler
from .approvals import ApprovalStore
from .core import RiskLevel, ToolSpec
from .feishu_card import build_approval_card
from .mock_executor import MockApprovedExecutor
from .repair_plan import build_repair_plan


def run_local_approval_demo(*, approve: bool = True) -> dict[str, Any]:
    """Exercise card creation, callback authorization, and mock execution."""
    store = ApprovalStore()
    store.create(
        "demo-task-1",
        ToolSpec("restart_desktop_bridge", "simulated bridge restart", RiskLevel.DESTRUCTIVE),
        {},
    )
    report = {
        "state": "degraded",
        "results": [{"tool": "snapshot", "status": "failed", "error": "timeout"}],
    }
    plan = build_repair_plan(report)
    card = build_approval_card(task_id="demo-task-1", plan=plan)
    callback = ApprovalCallbackHandler(store, allowed_approvers={"demo-owner"})
    decision = callback.handle(
        {"task_id": "demo-task-1", "action": "approve" if approve else "reject"},
        approver="demo-owner",
    )
    execution = MockApprovedExecutor(store).execute("demo-task-1")
    return {
        "plan": plan,
        "card": card,
        "callback": decision.__dict__,
        "execution": execution.__dict__,
        "network_or_system_side_effect": False,
    }
