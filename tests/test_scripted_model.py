"""Unit tests for the deterministic offline ScriptedModel."""

from shellloop.models import ScriptedModel


def response(content: str) -> dict:
    return {"role": "assistant", "content": content}


def test_returns_scripted_responses_in_order():
    model = ScriptedModel([response("first"), response("second")])

    assert model.query([])["content"] == "first"
    assert model.query([])["content"] == "second"


def test_returns_fallback_message_when_responses_exhausted():
    model = ScriptedModel([])

    message = model.query([])

    assert message["content"] == "No scripted response remains."
    assert message["extra"]["actions"] == []


def test_query_does_not_mutate_scripted_responses():
    scripted = [response("keep me")]
    model = ScriptedModel(scripted)

    model.query([])

    assert scripted[0]["content"] == "keep me"
