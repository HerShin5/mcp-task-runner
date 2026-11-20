"""Normalize raw read-only MCP results into health reports."""

from __future__ import annotations

from typing import Any


_STATE_LABELS = {
    "healthy": "健康",
    "degraded": "降级",
    "unknown": "未知",
}
_STATE_ICONS = {
    "healthy": "🟢",
    "degraded": "🟡",
    "unknown": "⚪",
}


def normalize_health_report(raw: dict[str, Any]) -> dict[str, Any]:
    results = raw.get("results", [])
    ok_count = sum(item.get("status") == "ok" for item in results if isinstance(item, dict))
    failed_count = sum(item.get("status") == "failed" for item in results if isinstance(item, dict))
    discovered = int(raw.get("discovered_tool_count", 0))
    executed = len(raw.get("executed_tools", []))

    if not raw.get("session_id_present") or not raw.get("protocol"):
        state = "unknown"
        summary = "MCP 会话或协议数据不完整"
    elif failed_count:
        state = "degraded"
        summary = f"有 {failed_count} 项只读诊断检查失败"
    elif executed == 0:
        state = "unknown"
        summary = "没有可用的已审核只读工具"
    else:
        state = "healthy"
        summary = f"{ok_count} 项只读诊断检查通过"

    return {
        "state": state,
        "summary": summary,
        "protocol": raw.get("protocol"),
        "server": raw.get("server"),
        "discovered_tool_count": discovered,
        "executed_tools": raw.get("executed_tools", []),
        "passed_checks": ok_count,
        "failed_checks": failed_count,
        "results": results,
        "read_only": True,
    }


def render_human_report(report: dict[str, Any]) -> str:
    """Render a concise Chinese report for a human operator."""
    state = str(report.get("state", "unknown"))
    icon = _STATE_ICONS.get(state, "⚪")
    label = _STATE_LABELS.get(state, state)
    lines = [
        "Windows-MCP 只读诊断报告",
        "=" * 28,
        f"总体状态：{icon} {label}",
        f"结论：{report.get('summary', '无结论')}",
        f"协议版本：{report.get('protocol') or '未知'}",
        f"发现工具：{report.get('discovered_tool_count', 0)} 个",
        f"检查结果：{report.get('passed_checks', 0)} 项通过，{report.get('failed_checks', 0)} 项失败",
        "",
        "检查明细：",
    ]
    results = report.get("results", [])
    if results:
        for item in results:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            item_icon = "🟢" if status == "ok" else "🔴"
            detail = item.get("error") if status == "failed" else "检查通过"
            lines.append(f"  {item_icon} {item.get('tool', 'unknown')}: {detail}")
    else:
        lines.append("  ⚪ 没有执行只读检查")
    lines.extend([
        "",
        "安全说明：",
        "  本次仅允许已审核的只读工具。",
        "  未点击、未输入、未启动程序、未修改文件或服务。",
    ])
    return "\n".join(lines)
