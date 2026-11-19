import pytest

from mcp_task_runner.core import RiskLevel, ToolRegistry, ToolSpec
from mcp_task_runner.planner import PlanValidationError, parse_and_validate


def registry():
    tools = ToolRegistry()
    tools.register(ToolSpec("health", "read-only check", RiskLevel.READ_ONLY, True))
    tools.register(ToolSpec("restart", "restart service", RiskLevel.DESTRUCTIVE, True))
    return tools


def test_valid_read_only_plan_is_normalized():
    plan = parse_and_validate(
        {
            "goal": "check service",
            "requires_approval": False,
            "steps": [
                {"id": "s1", "tool": "health", "arguments": {}, "purpose": "inspect state", "verify": True}
            ],
        },
        registry(),
    )
    assert plan.requires_approval is False
    assert plan.steps[0].tool == "health"


def test_model_cannot_hide_destructive_tool():
    plan = parse_and_validate(
        {
            "goal": "repair service",
            "requires_approval": False,
            "steps": [
                {"id": "s1", "tool": "restart", "arguments": {}, "purpose": "restart it", "verify": True}
            ],
        },
        registry(),
    )
    assert plan.requires_approval is True


def test_unknown_tool_is_rejected():
    with pytest.raises(PlanValidationError, match="unknown tool"):
        parse_and_validate(
            {"goal": "bad", "steps": [{"id": "s1", "tool": "missing", "purpose": "do it"}]},
            registry(),
        )


def test_verification_cannot_be_skipped_for_verifiable_tool():
    with pytest.raises(PlanValidationError, match="verification"):
        parse_and_validate(
            {
                "goal": "check",
                "steps": [{"id": "s1", "tool": "health", "purpose": "inspect", "verify": False}],
            },
            registry(),
        )
