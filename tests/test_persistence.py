from mcp_task_runner.core import RiskLevel, ToolSpec
import pytest

from mcp_task_runner.approvals import ApprovalStatus, ApprovalStore
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


@pytest.mark.parametrize("sqlite", [True, False])
@pytest.mark.parametrize("decision", [None, True, False])
def test_duplicate_task_preserves_original_record(tmp_path, sqlite, decision):
    path = tmp_path / "approval-test.sqlite"
    store = SQLiteApprovalStore(path) if sqlite else ApprovalStore()
    original = store.create("task", ToolSpec("first", "first", RiskLevel.READ_ONLY), {"v": 1})
    if decision is not None:
        original = store.decide("task", approved=decision, approver="owner", reason="reviewed")
    with pytest.raises(ValueError, match="already exists"):
        store.create("task", ToolSpec("second", "second", RiskLevel.WRITE), {"v": 2}, requester="other")
    reader = SQLiteApprovalStore(path) if sqlite else store
    assert reader.get("task") == original


def test_api_demo_uses_independent_approval_records():
    from mcp_task_runner.api import ApiState

    state = ApiState()
    first = state.create_pending_demo()["task_id"]
    state.approvals.decide(first, approved=False, approver="owner")
    second = state.create_pending_demo()["task_id"]
    assert first != second
    assert state.approvals.get(first).status is ApprovalStatus.REJECTED
    assert state.approvals.get(second).status is ApprovalStatus.PENDING
