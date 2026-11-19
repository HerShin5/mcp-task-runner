import json

from mcp_task_runner.cli import run


def test_diagnose_plan_cli(capsys):
    assert run(["diagnose-plan", "--url", "http://example.test/mcp"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["read_only"] is True
    assert output["endpoint"] == "http://example.test/mcp"


def test_approval_demo_defaults_to_rejection(capsys):
    assert run(["approval-demo"]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["result"]["status"] == "rejected"


def test_approval_demo_can_run_when_explicitly_approved(capsys):
    assert run(["approval-demo", "--approve"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["result"]["status"] == "executed"


def test_orchestrate_demo_selects_capable_model_for_ops(capsys):
    assert run(["orchestrate-demo", "检查", "Windows-MCP", "并修复"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["selected_model"] == "gpt-terra"
    assert output["selected_gateway"] == "gateway-quality"


def test_orchestrate_demo_selects_cheaper_model_for_simple_text(capsys):
    assert run(["orchestrate-demo", "总结", "这段文本"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["selected_model"] == "gpt-astra"
    assert output["selected_gateway"] == "gateway-low"


def test_plan_validate_cli(tmp_path, capsys):
    plan = tmp_path / "plan.json"
    plan.write_text(
        '{"goal":"check","steps":[{"id":"s1","tool":"health","arguments":{},"purpose":"inspect","verify":true}]}',
        encoding="utf-8",
    )
    assert run(["plan-validate", str(plan)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True


def test_live_plan_without_real_gateway_returns_safe_error(tmp_path, capsys):
    providers = tmp_path / "providers.json"
    providers.write_text('{"providers": []}', encoding="utf-8")
    assert run(["live-plan", "检查", "服务", "--providers", str(providers)]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "no capable healthy model/gateway route"
