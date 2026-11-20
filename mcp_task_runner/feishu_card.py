"""Build Feishu approval-card payloads without making network calls."""

from __future__ import annotations

import json
from typing import Any


def build_approval_card(*, task_id: str, plan: dict[str, Any], title: str = "MCP Task Runner 操作审批") -> dict[str, Any]:
    steps = plan.get("steps", [])
    step_lines = []
    for index, step in enumerate(steps, 1):
        risk = step.get("risk", "unknown")
        approval = "需要审批" if step.get("requires_approval") else "只读"
        step_lines.append(f"{index}. [{risk}/{approval}] {step.get('action', 'unknown')}")
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "header": {"template": "orange" if plan.get("requires_approval") else "green", "title": {"tag": "plain_text", "content": title}},
        "elements": [
            {"tag": "markdown", "content": f"**任务 ID**: `{task_id}`\n**状态**: `{plan.get('status', 'proposed')}`\n**结论**: {plan.get('summary', '')}"},
            {"tag": "markdown", "content": "**计划步骤**\n" + ("\n".join(step_lines) or "无执行步骤")},
            {"tag": "markdown", "content": "**安全边界**\n" + str(plan.get("safety", "非只读操作必须审批，执行后需要复检。"))},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "批准"}, "type": "primary", "value": {"action": "approve", "task_id": task_id}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "拒绝"}, "type": "danger", "value": {"action": "reject", "task_id": task_id}},
            ]},
        ],
    }


def serialize_card(card: dict[str, Any]) -> str:
    return json.dumps(card, ensure_ascii=False, separators=(",", ":"))
