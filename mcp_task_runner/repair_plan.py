"""Conservative remediation plans derived from normalized health reports.

These are proposals only. No action in this module invokes a tool or changes
system state; a later executor must validate and approve each action.
"""

from __future__ import annotations

from typing import Any


def build_repair_plan(report: dict[str, Any]) -> dict[str, Any]:
    state = report.get("state", "unknown")
    failed_tools = {
        item.get("tool")
        for item in report.get("results", [])
        if isinstance(item, dict) and item.get("status") == "failed"
    }
    steps: list[dict[str, Any]] = []

    if state == "healthy":
        return {
            "kind": "windows_mcp_remediation",
            "status": "not_needed",
            "requires_approval": False,
            "summary": "只读诊断健康，无需生成修复动作。",
            "steps": [],
        }

    steps.append({
        "id": "review-evidence",
        "action": "review_diagnostic_evidence",
        "risk": "read_only",
        "requires_approval": False,
        "purpose": "复核失败检查、协议版本、会话状态和最近错误信息。",
    })
    if "snapshot" in failed_tools:
        steps.append({
            "id": "inspect-interactive-session",
            "action": "inspect_interactive_desktop_session",
            "risk": "read_only",
            "requires_approval": False,
            "purpose": "检查 Windows 交互会话、UIA 可用性和 desktop-bridge 状态。",
        })
        steps.append({
            "id": "restart-bridge-after-approval",
            "action": "restart_desktop_bridge",
            "risk": "destructive",
            "requires_approval": True,
            "approval_channel": "feishu",
            "purpose": "只有前置排查确认桥接卡死后，才申请重启并随后复检。",
        })
    elif failed_tools:
        steps.append({
            "id": "inspect-failed-tools",
            "action": "inspect_mcp_server_logs",
            "risk": "read_only",
            "requires_approval": False,
            "purpose": "查看失败工具对应的服务日志和连接状态。",
        })

    return {
        "kind": "windows_mcp_remediation",
        "status": "proposed",
        "requires_approval": any(step["requires_approval"] for step in steps),
        "summary": "已生成排查/修复建议；未执行任何动作。",
        "steps": steps,
        "safety": "本计划只供人工审核；任何非只读动作必须通过审批并在执行后复检。",
    }


def render_repair_plan(plan: dict[str, Any]) -> str:
    lines = [
        "Windows-MCP 修复计划（仅提案，不执行）",
        "=" * 34,
        f"状态：{plan.get('status')}",
        f"结论：{plan.get('summary')}",
        f"需要审批：{'是' if plan.get('requires_approval') else '否'}",
        "",
        "步骤：",
    ]
    steps = plan.get("steps", [])
    if not steps:
        lines.append("  - 当前无需修复动作")
    for index, step in enumerate(steps, 1):
        approval = "需飞书审批" if step.get("requires_approval") else "只读"
        lines.append(f"  {index}. [{approval}] {step.get('action')}: {step.get('purpose')}")
    lines.extend(["", f"安全边界：{plan.get('safety', '未执行任何动作。')}"])
    return "\n".join(lines)
