import json
from unittest.mock import patch

import pytest

from mcp_task_runner.classifier import ClassificationError, HeuristicTaskClassifier, ModelTaskClassifier
from mcp_task_runner.model_client import OpenAICompatibleClient


def test_heuristic_classifier_maps_ops_task():
    result = HeuristicTaskClassifier().classify("检查 Windows-MCP 端口并修复")
    assert result.task_type == "ops_agent"
    assert result.minimum["tool_calling"] == 4


class FakeResponse:
    status = 200

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({
            "choices": [{"message": {"content": json.dumps({
                "task_type": "classification",
                "minimum": {"reasoning": 1, "structured_output": 3},
                "quality_floor": "standard",
                "cost_preference": "cost",
                "preferred_models": [],
            })}}],
            "usage": {},
        }).encode()


def test_model_classifier_validates_router_output():
    client = OpenAICompatibleClient(base_url="https://example.invalid/v1", api_key=None, provider="router", model="router-model")
    with patch("mcp_task_runner.model_client.urlopen", return_value=FakeResponse()):
        result = ModelTaskClassifier(client).classify("分类一批文本")
    assert result.task_type == "classification"
    assert result.cost_preference == "cost"


def test_model_classifier_rejects_unknown_capability():
    client = OpenAICompatibleClient(base_url="https://example.invalid/v1", api_key=None, provider="router", model="router-model")
    response = FakeResponse()
    response.read = lambda: json.dumps({
        "choices": [{"message": {"content": '{"task_type":"bad","minimum":{"magic":5}}'}}],
        "usage": {},
    }).encode()
    with patch("mcp_task_runner.model_client.urlopen", return_value=response):
        with pytest.raises(ClassificationError):
            ModelTaskClassifier(client).classify("bad")
