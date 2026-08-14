import json
import urllib.error
import urllib.request

import pytest

from shellloop.models.openai_compatible import OpenAICompatibleModel, OpenAIModelError, UrllibJsonTransport
from shellloop.models.text_actions import TextActionFormatError


class FakeTransport:
    """In-memory transport that records the request and returns a canned response."""

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


def _ok_response(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _model(transport: FakeTransport) -> OpenAICompatibleModel:
    return OpenAICompatibleModel(
        api_base="https://api.example.com/v1",
        model_name="test-model",
        api_key="sk-test-secret-key",
        transport=transport,
    )


def test_builds_well_formed_chat_completion_request():
    transport = FakeTransport(_ok_response("```bash\nls\n```"))
    model = _model(transport)

    model.query(
        [
            {"role": "system", "content": "You are Shellloop, a minimal coding agent."},
            {"role": "user", "content": "list files", "extra": {"anything": 1}},
        ]
    )

    assert transport.url == "https://api.example.com/v1/chat/completions"
    assert transport.headers["Authorization"] == "Bearer sk-test-secret-key"
    assert transport.payload["model"] == "test-model"
    assert transport.payload["messages"] == [
        {"role": "system", "content": "You are Shellloop, a minimal coding agent."},
        {"role": "user", "content": "list files"},
    ]


def test_parses_model_text_into_single_action():
    model = _model(FakeTransport(_ok_response("```bash\necho hello\n```")))

    message = model.query([{"role": "user", "content": "hi"}])

    assert message["role"] == "assistant"
    assert message["content"] == "```bash\necho hello\n```"
    assert message["extra"]["actions"] == [{"command": "echo hello"}]


def test_invalid_model_text_raises_parser_error():
    model = _model(FakeTransport(_ok_response("```python\nprint('hi')\n```")))

    with pytest.raises(TextActionFormatError):
        model.query([{"role": "user", "content": "hi"}])


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": ""}}]},
    ],
)
def test_missing_assistant_content_fails(response):
    model = _model(FakeTransport(response))

    with pytest.raises(OpenAIModelError):
        model.query([{"role": "user", "content": "hi"}])


def test_api_key_never_leaks_into_message_or_error():
    model = _model(FakeTransport(_ok_response("```bash\nls\n```")))

    message = model.query([{"role": "user", "content": "hi"}])
    assert "sk-test-secret-key" not in repr(message)
    assert "sk-test-secret-key" not in json.dumps(message)

    failing = _model(FakeTransport(_ok_response("x"), error=OpenAIModelError("HTTP 401 Unauthorized")))
    with pytest.raises(OpenAIModelError) as excinfo:
        failing.query([{"role": "user", "content": "hi"}])
    assert "sk-test-secret-key" not in str(excinfo.value)


def test_default_transport_hides_http_error_body(monkeypatch):
    class Boom(urllib.error.HTTPError):
        def __init__(self) -> None:
            super().__init__("https://api.example.com/v1/chat/completions", 401, "Unauthorized", None, None)

        def read(self) -> bytes:
            return b'{"error": {"message": "sk-test-secret-key leaked in body"}}'

    def fake_urlopen(_request, timeout):
        raise Boom()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(OpenAIModelError) as excinfo:
        UrllibJsonTransport().post_json(
            "https://api.example.com/v1/chat/completions",
            {"Authorization": "Bearer sk-test-secret-key"},
            {},
        )
    assert "sk-test-secret-key" not in str(excinfo.value)
