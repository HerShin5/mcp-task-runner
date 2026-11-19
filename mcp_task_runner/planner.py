"""Validated structured plans produced by an AI planner.

The model may propose a plan, but it cannot define tool risk or approval
requirements. Those facts come from the local ToolRegistry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .core import RiskLevel, ToolRegistry


class PlanValidationError(ValueError):
    """Raised when a model plan is malformed or unsafe."""


@dataclass(frozen=True)
class PlanStep:
    id: str
    tool: str
    arguments: dict[str, Any]
    purpose: str
    verify: bool


@dataclass(frozen=True)
class TaskPlan:
    goal: str
    steps: tuple[PlanStep, ...]
    requires_approval: bool
    source: str = "model"

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "requires_approval": self.requires_approval,
            "source": self.source,
            "steps": [
                {
                    "id": step.id,
                    "tool": step.tool,
                    "arguments": step.arguments,
                    "purpose": step.purpose,
                    "verify": step.verify,
                }
                for step in self.steps
            ],
        }


def parse_and_validate(raw: str | dict[str, Any], registry: ToolRegistry) -> TaskPlan:
    """Parse a model JSON object and enforce registry-owned safety metadata."""
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise PlanValidationError(f"plan is not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise PlanValidationError("plan must be a JSON object")

    goal = payload.get("goal")
    raw_steps = payload.get("steps")
    if not isinstance(goal, str) or not goal.strip():
        raise PlanValidationError("goal must be a non-empty string")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise PlanValidationError("steps must be a non-empty list")
    if len(raw_steps) > 32:
        raise PlanValidationError("plan contains too many steps")

    steps: list[PlanStep] = []
    unsafe = False
    seen_ids: set[str] = set()
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            raise PlanValidationError("each step must be an object")
        step_id = raw_step.get("id")
        tool_name = raw_step.get("tool")
        arguments = raw_step.get("arguments", {})
        purpose = raw_step.get("purpose")
        verify = raw_step.get("verify", True)
        if not isinstance(step_id, str) or not step_id.strip() or step_id in seen_ids:
            raise PlanValidationError("step ids must be unique non-empty strings")
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise PlanValidationError("step tool must be a non-empty string")
        if not isinstance(arguments, dict):
            raise PlanValidationError(f"arguments for {step_id} must be an object")
        if not isinstance(purpose, str) or not purpose.strip():
            raise PlanValidationError(f"purpose for {step_id} must be a non-empty string")
        if not isinstance(verify, bool):
            raise PlanValidationError(f"verify for {step_id} must be boolean")

        try:
            spec = registry.get(tool_name)
        except KeyError as exc:
            raise PlanValidationError(str(exc)) from exc

        # The registry, never the model, owns the risk classification.
        if spec.risk_level is not RiskLevel.READ_ONLY:
            unsafe = True
        if spec.supports_verify and not verify:
            raise PlanValidationError(f"step {step_id} must request verification for {tool_name}")

        seen_ids.add(step_id)
        steps.append(PlanStep(step_id, tool_name, arguments, purpose, verify))

    requested_approval = payload.get("requires_approval", False)
    if not isinstance(requested_approval, bool):
        raise PlanValidationError("requires_approval must be boolean")
    # A model cannot suppress approval for a write/destructive tool.
    return TaskPlan(goal.strip(), tuple(steps), unsafe or requested_approval, str(payload.get("source", "model")))
