from mcp_task_runner.capabilities import (
    ModelCandidate,
    ModelProfile,
    TaskRequirements,
    choose_model,
    profile_from_dict,
)


def test_model_with_insufficient_capability_is_excluded_even_when_cheaper():
    cheap = ModelCandidate(
        ModelProfile("cheap", {"coding": 2, "tool_calling": 1}), cost=0.01, quality_score=100
    )
    capable = ModelCandidate(
        ModelProfile("capable", {"coding": 4, "tool_calling": 4}), cost=0.05, quality_score=80
    )
    requirements = TaskRequirements("code_agent", {"coding": 4, "tool_calling": 4})
    assert choose_model([cheap, capable], requirements).profile.name == "capable"


def test_economy_task_can_choose_cheap_model():
    cheap = ModelCandidate(ModelProfile("cheap", {"reasoning": 2}), cost=0.01, quality_score=70)
    expensive = ModelCandidate(ModelProfile("expensive", {"reasoning": 5}), cost=0.05, quality_score=95)
    requirements = TaskRequirements("classification", {"reasoning": 1}, cost_preference="cost")
    assert choose_model([cheap, expensive], requirements).profile.name == "cheap"


def test_profile_rejects_unknown_or_out_of_range_scores():
    try:
        profile_from_dict({"name": "bad", "capabilities": {"magic": 3}})
    except ValueError as exc:
        assert "unknown capabilities" in str(exc)
    else:
        raise AssertionError("unknown capability was accepted")
