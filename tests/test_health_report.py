from mcp_task_runner.health_report import normalize_health_report


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
