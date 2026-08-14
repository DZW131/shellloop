"""Deterministic offline model for development and tests."""

from copy import deepcopy

from shellloop.core import Message


class ScriptedModel:
    """Return pre-written messages in sequence."""

    def __init__(self, responses: list[Message]):
        self.responses = deepcopy(responses)

    def query(self, messages: list[Message]) -> Message:
        if not self.responses:
            return {"role": "assistant", "content": "No scripted response remains.", "extra": {"actions": []}}
        return self.responses.pop(0)


def demo_model() -> ScriptedModel:
    return ScriptedModel(
        [
            {
                "role": "assistant",
                "content": "I will demonstrate one safe shell action and finish.",
                "extra": {"actions": [{"command": "echo SHELLLOOP_DONE && echo Offline scripted run completed."}]},
            }
        ]
    )
