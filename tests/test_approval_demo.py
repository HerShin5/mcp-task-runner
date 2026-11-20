from mcp_task_runner.approval_demo import run_local_approval_demo


def test_local_approval_demo_approved_path_is_simulated():
    result = run_local_approval_demo(approve=True)
    assert result["callback"]["status"] == "approved"
    assert result["execution"]["status"] == "executed"
    assert result["execution"]["simulated"] is True
    assert result["network_or_system_side_effect"] is False


def test_local_approval_demo_rejected_path_stays_blocked():
    result = run_local_approval_demo(approve=False)
    assert result["callback"]["status"] == "rejected"
    assert result["execution"]["status"] == "blocked"
