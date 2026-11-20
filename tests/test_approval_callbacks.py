from mcp_task_runner.approval_callbacks import ApprovalCallbackHandler
from mcp_task_runner.approvals import ApprovalStore
from mcp_task_runner.core import RiskLevel, ToolSpec


def test_callback_approval_is_recorded_and_authorized():
    store = ApprovalStore()
    tool = ToolSpec("restart", "restart bridge", RiskLevel.DESTRUCTIVE)
    store.create("task-1", tool, {})
    result = ApprovalCallbackHandler(store, allowed_approvers={"owner"}).handle(
        {"task_id": "task-1", "action": "approve"}, approver="owner"
    )
    assert result.accepted is True
    assert result.status == "approved"


def test_callback_rejects_unknown_approver_and_bad_action():
    store = ApprovalStore()
    tool = ToolSpec("restart", "restart bridge", RiskLevel.DESTRUCTIVE)
    store.create("task-1", tool, {})
    handler = ApprovalCallbackHandler(store, allowed_approvers={"owner"})
    assert handler.handle({"task_id": "task-1", "action": "approve"}, approver="other").status == "forbidden"
    assert handler.handle({"task_id": "task-1", "action": "delete"}, approver="owner").status == "invalid"
