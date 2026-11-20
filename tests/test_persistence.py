from mcp_task_runner.core import RiskLevel, ToolSpec
from mcp_task_runner.approvals import ApprovalStatus
from mcp_task_runner.persistence import SQLiteApprovalStore


def test_sqlite_approval_survives_store_reopen(tmp_path):
    path = tmp_path / "approvals.sqlite"
    tool = ToolSpec("restart", "restart bridge", RiskLevel.DESTRUCTIVE, True)
    store = SQLiteApprovalStore(path)
    store.create("task-1", tool, {"reason": "demo"})
    store.decide("task-1", approved=True, approver="owner")

    reopened = SQLiteApprovalStore(path)
    request = reopened.get("task-1")
    assert request.status is ApprovalStatus.APPROVED
    assert request.arguments == {"reason": "demo"}
    assert request.approver == "owner"
