"""Normalize raw read-only MCP results into a small health report."""

from __future__ import annotations

from typing import Any


def normalize_health_report(raw: dict[str, Any]) -> dict[str, Any]:
    results = raw.get("results", [])
    ok_count = sum(item.get("status") == "ok" for item in results if isinstance(item, dict))
    failed_count = sum(item.get("status") == "failed" for item in results if isinstance(item, dict))
    discovered = int(raw.get("discovered_tool_count", 0))
    executed = len(raw.get("executed_tools", []))

    if not raw.get("session_id_present") or not raw.get("protocol"):
        state = "unknown"
        summary = "MCP session or protocol information is incomplete"
    elif failed_count:
        state = "degraded"
        summary = f"{failed_count} read-only diagnostic check(s) failed"
    elif executed == 0:
        state = "unknown"
        summary = "No reviewed read-only tools were available"
    else:
        state = "healthy"
        summary = f"{ok_count} read-only diagnostic check(s) passed"

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
