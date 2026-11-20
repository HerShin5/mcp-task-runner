"""Safe local executor for testing approval-to-execution flow.

This module intentionally performs no OS, shell, network, or desktop action.
It records a simulated effect and returns a verification result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .approvals import ApprovalStatus, ApprovalStore


@dataclass(frozen=True)
class MockExecutionResult:
    task_id: str
    status: str
    action: str
    simulated: bool
    verified: bool
    message: str


class MockApprovedExecutor:
    def __init__(self, store: ApprovalStore):
        self.store = store

    def execute(self, task_id: str) -> MockExecutionResult:
        request = self.store.get(task_id)
        if request.status is not ApprovalStatus.APPROVED:
            return MockExecutionResult(
                task_id, "blocked", request.tool.name, True, False,
                f"approval status is {request.status.value}; execution blocked",
            )
        return MockExecutionResult(
            task_id, "executed", request.tool.name, True, True,
            "simulated action completed and simulated post-check passed",
        )
