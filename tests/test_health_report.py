from mcp_task_runner.health_report import normalize_health_report, render_human_report


def test_health_report_is_healthy_when_read_only_checks_pass():
    report = normalize_health_report({
        "protocol": "2025-06-18",
        "session_id_present": True,
        "discovered_tool_count": 3,
        "executed_tools": ["snapshot"],
        "results": [{"tool": "snapshot", "status": "ok"}],
    })
    assert report["state"] == "healthy"
    assert report["passed_checks"] == 1


def test_health_report_marks_failed_check_degraded():
    report = normalize_health_report({
        "protocol": "2025-06-18",
        "session_id_present": True,
        "discovered_tool_count": 3,
        "executed_tools": ["snapshot"],
        "results": [{"tool": "snapshot", "status": "failed"}],
    })
    assert report["state"] == "degraded"
    assert report["failed_checks"] == 1


def test_health_report_marks_missing_session_unknown():
    report = normalize_health_report({"protocol": None, "session_id_present": False, "results": []})
    assert report["state"] == "unknown"


def test_human_report_contains_chinese_status_and_safety_boundary():
    report = normalize_health_report({
        "protocol": "2025-06-18",
        "session_id_present": True,
        "discovered_tool_count": 1,
        "executed_tools": ["snapshot"],
        "results": [{"tool": "snapshot", "status": "ok"}],
    })
    text = render_human_report(report)
    assert "🟢 健康" in text
    assert "安全说明" in text
    assert "未点击" in text
