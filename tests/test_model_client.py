import json
from unittest.mock import patch

from mcp_task_runner.model_client import OpenAICompatibleClient


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
            "choices": [{"message": {"content": '{"goal":"check"}'}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4},
        }).encode()


def test_openai_compatible_client_parses_non_streaming_reply():
    client = OpenAICompatibleClient(
        base_url="https://example.invalid/v1",
        api_key=None,
        provider="fake",
        model="model",
    )
    with patch("mcp_task_runner.model_client.urlopen", return_value=FakeResponse()):
        reply = client.chat([{"role": "user", "content": "make a plan"}])
    assert reply.text.startswith("{")
    assert reply.usage["prompt_tokens"] == 3
    assert reply.provider == "fake"
