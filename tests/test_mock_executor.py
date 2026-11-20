from mcp_task_runner.approvals import ApprovalStatus, ApprovalStore
from mcp_task_runner.core import RiskLevel, ToolSpec
from mcp_task_runner.mock_executor import MockApprovedExecutor


def test_mock_executor_blocks_pending_request():
    store = ApprovalStore()
    store.create("task", ToolSpec("restart", "restart", RiskLevel.DESTRUCTIVE), {})
    result = MockApprovedExecutor(store).execute("task")
    assert result.status == "blocked"
    assert result.verified is False


def test_mock_executor_runs_only_after_approval():
    store = ApprovalStore()
    store.create("task", ToolSpec("restart", "restart", RiskLevel.DESTRUCTIVE), {})
    store.decide("task", approved=True, approver="owner")
    result = MockApprovedExecutor(store).execute("task")
    assert result.status == "executed"
    assert result.simulated is True
    assert result.verified is True
