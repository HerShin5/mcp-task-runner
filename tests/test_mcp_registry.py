from mcp_task_runner.core import RiskLevel, ToolRegistry
from mcp_task_runner.mcp_registry import register_discovered_tools


def test_discovered_tools_fail_closed_by_default():
    registry = ToolRegistry()
    registered = register_discovered_tools(registry, [
        {"name": "snapshot", "description": "read state"},
        {"name": "click", "description": "click UI"},
    ])
    assert [item.name for item in registered] == ["snapshot", "click"]
    assert registry.get("snapshot").risk_level is RiskLevel.READ_ONLY
    assert registry.get("click").risk_level is RiskLevel.DESTRUCTIVE
