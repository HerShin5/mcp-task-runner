from mcp_task_runner.repair_plan import build_repair_plan, render_repair_plan


def test_healthy_report_needs_no_repair():
    plan = build_repair_plan({"state": "healthy", "results": []})
    assert plan["status"] == "not_needed"
    assert plan["steps"] == []


def test_snapshot_failure_creates_approval_gated_proposal_without_execution():
    plan = build_repair_plan({
        "state": "degraded",
        "results": [{"tool": "snapshot", "status": "failed", "error": "timeout"}],
    })
    assert plan["status"] == "proposed"
    assert plan["requires_approval"] is True
    actions = [step["action"] for step in plan["steps"]]
    assert "inspect_interactive_desktop_session" in actions
    assert "restart_desktop_bridge" in actions
    assert "执行" in render_repair_plan(plan)
