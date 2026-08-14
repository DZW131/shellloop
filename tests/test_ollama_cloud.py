import json

import pytest

from shellloop.models.ollama_cloud import OllamaCloudError, OllamaCloudModel
from shellloop.models.text_actions import TextActionFormatError


class FakeTransport:
    def __init__(self, response: dict, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.url: str | None = None
        self.headers: dict[str, str] | None = None
        self.payload: dict | None = None

    def post_json(self, url: str, headers: dict[str, str], payload: dict) -> dict:
        if self.error is not None:
            raise self.error
        self.url = url
        self.headers = headers
        self.payload = payload
        return self.response


def _model(transport: FakeTransport) -> OllamaCloudModel:
    return OllamaCloudModel("https://ollama.com/api", "gpt-oss:120b-cloud", "ollama-test-key", transport)


def test_builds_a_non_streaming_ollama_cloud_request():
    transport = FakeTransport({"message": {"content": "```bash\npwd\n```"}})

    _model(transport).query([{"role": "user", "content": "show the working directory"}])

    assert transport.url == "https://ollama.com/api/chat"
    assert transport.headers == {"Authorization": "Bearer ollama-test-key", "Content-Type": "application/json"}
    assert transport.payload == {
        "model": "gpt-oss:120b-cloud",
        "messages": [{"role": "user", "content": "show the working directory"}],
        "stream": False,
    }


def test_converts_a_compliant_response_to_one_shell_action():
    message = _model(FakeTransport({"message": {"content": "```bash\necho hello\n```"}})).query(
        [{"role": "user", "content": "say hello"}]
    )

    assert message == {
        "role": "assistant",
        "content": "```bash\necho hello\n```",
        "extra": {"actions": [{"command": "echo hello"}]},
    }


@pytest.mark.parametrize(
    ("response",),
    [({},), ({"message": {}},), ({"message": {"content": None}},), ({"message": {"content": ""}},)],
)
def test_rejects_a_response_without_assistant_content(response):
    with pytest.raises(OllamaCloudError):
        _model(FakeTransport(response)).query([{"role": "user", "content": "hi"}])


def test_invalid_model_text_raises_parser_error():
    with pytest.raises(TextActionFormatError):
        _model(FakeTransport({"message": {"content": "plain text"}})).query([{"role": "user", "content": "hi"}])


def test_api_key_does_not_leak_into_a_message_or_error():
    message = _model(FakeTransport({"message": {"content": "```bash\nls\n```"}})).query(
        [{"role": "user", "content": "hi"}]
    )

    assert "ollama-test-key" not in json.dumps(message)
    with pytest.raises(OllamaCloudError) as excinfo:
        _model(FakeTransport({}, OllamaCloudError("request failed"))).query([{"role": "user", "content": "hi"}])
    assert "ollama-test-key" not in str(excinfo.value)
