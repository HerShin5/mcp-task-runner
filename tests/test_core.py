from mcp_task_runner import (
    ApprovalDecision,
    EvidenceLog,
    RiskLevel,
    TaskRunner,
    ToolRegistry,
    ToolSpec,
    VerificationResult,
)


class LocalApproval:
    def __init__(self, decision: ApprovalDecision):
        self.decision = decision
        self.calls = []

    def request(self, task_id, tool, arguments):
        self.calls.append((task_id, tool.name, arguments))
        return self.decision


def make_runner(approval):
    registry = ToolRegistry()
    registry.register(ToolSpec("health", "read-only health check", RiskLevel.READ_ONLY, True, lambda _: {"ok": True}))
    registry.register(ToolSpec("repair", "repair service", RiskLevel.WRITE, True, lambda _: {"repaired": True}))
    return TaskRunner(registry, approval, EvidenceLog())


def test_read_only_tool_runs_without_approval():
    approval = LocalApproval(ApprovalDecision(False, "nobody", "not needed"))
    runner = make_runner(approval)

    result = runner.execute("health", {}, lambda value: VerificationResult(value["ok"], "health is ok"))

    assert result.status == "executed"
    assert result.value == {"ok": True}
    assert approval.calls == []
    assert [event["event"] for event in runner.evidence.events] == [
        "task_planned",
        "tool_executed",
        "verification_completed",
    ]


def test_write_tool_is_blocked_without_approval():
    approval = LocalApproval(ApprovalDecision(False, "owner", "manual approval required"))
    runner = make_runner(approval)

    result = runner.execute("repair", {})

    assert result.status == "rejected"
    assert "manual approval" in result.error
    assert len(approval.calls) == 1


def test_approved_write_tool_runs_and_can_fail_verification():
    approval = LocalApproval(ApprovalDecision(True, "owner", "approved for test"))
    runner = make_runner(approval)

    result = runner.execute("repair", {}, lambda _: VerificationResult(False, "post-check failed"))

    assert result.status == "verification_failed"
    assert result.value == {"repaired": True}
    assert runner.evidence.events[-1]["event"] == "verification_completed"
