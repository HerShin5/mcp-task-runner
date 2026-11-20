from mcp_task_runner.feishu_card import build_approval_card, serialize_card


def test_feishu_card_has_approval_actions_without_network():
    plan = {
        "status": "proposed",
        "requires_approval": True,
        "summary": "repair proposal",
        "steps": [{"action": "restart_desktop_bridge", "risk": "destructive", "requires_approval": True}],
        "safety": "approval required",
    }
    card = build_approval_card(task_id="task-1", plan=plan)
    actions = card["elements"][-1]["actions"]
    assert actions[0]["value"] == {"action": "approve", "task_id": "task-1"}
    assert actions[1]["value"] == {"action": "reject", "task_id": "task-1"}
    assert "repair proposal" in serialize_card(card)
