import pytest

from shellloop.harness import HarnessSpec
from shellloop.proposals import generate_proposal, proposal_data


class FixedCompletion:
    def __init__(self, text: str) -> None:
        self.text = text
        self.messages: list[dict] = []

    def complete(self, messages: list[dict]) -> str:
        self.messages = messages
        return self.text


def test_generates_a_constrained_proposal_from_json_only_model_output():
    model = FixedCompletion(
        '{"summary":"Use a shorter teaching loop.","changes":{"max_steps":4,"timeout":45,'
        '"visible_planning":false,"verification_retries":2}}'
    )

    proposal = generate_proposal(model, "Make the loop easier to observe", HarnessSpec())

    assert proposal.candidate.max_steps == 4
    assert proposal.candidate.timeout == 45
    assert proposal.candidate.visible_planning is False
    assert proposal_data(proposal)["verified"] is False
    assert set(proposal_data(proposal)["changed_fields"]) == {
        "max_steps",
        "timeout",
        "visible_planning",
        "verification_retries",
    }
    assert proposal_data(proposal)["candidate_flow"][1]["enabled"] is False
    assert "Make the loop easier" not in str(proposal_data(proposal))
    assert model.messages[0]["role"] == "system"


def test_accepts_a_json_fence_but_rejects_non_allowlisted_changes():
    model = FixedCompletion('```json\n{"summary":"Unsafe","changes":{"workspace":"/"}}\n```')

    with pytest.raises(ValueError, match="unsupported Harness field"):
        generate_proposal(model, "Change everything", HarnessSpec())


@pytest.mark.parametrize(("text",), [("not JSON",), ("{}",), ('{"summary":"x","changes":[]}',)])
def test_rejects_invalid_proposal_responses(text: str):
    with pytest.raises((TypeError, ValueError)):
        generate_proposal(FixedCompletion(text), "Improve it", HarnessSpec())
