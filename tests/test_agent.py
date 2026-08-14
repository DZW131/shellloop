import sys
from pathlib import Path

from shellloop.agents import DefaultAgent
from shellloop.agents.default import SYSTEM_PROMPT
from shellloop.environments.local import LocalEnvironment


class FixedModel:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses

    def query(self, messages: list[dict]) -> dict:
        return self.responses.pop(0)


def response(command: str) -> dict:
    return {"role": "assistant", "content": command, "extra": {"actions": [{"command": command}]}}


def test_agent_saves_successful_submission(tmp_path: Path):
    model = FixedModel([response("echo SHELLLOOP_DONE && echo complete")])
    result = DefaultAgent(model, LocalEnvironment(tmp_path, 1), max_steps=2).run("Finish the task")

    assert result == {"exit_status": "Submitted", "submission": "complete\n", "steps": 1}


def test_agent_records_failed_command_before_completion(tmp_path: Path):
    failed_command = f'"{sys.executable}" -c "import sys; print(\u0027failed\u0027); sys.exit(1)"'
    model = FixedModel([response(failed_command), response("echo SHELLLOOP_DONE && echo recovered")])
    agent = DefaultAgent(model, LocalEnvironment(tmp_path, 1), max_steps=2)

    assert agent.run("Recover from a failed command")["submission"] == "recovered\n"
    assert agent.messages[3]["extra"]["returncode"] != 0


def test_agent_stops_at_step_limit(tmp_path: Path):
    result = DefaultAgent(FixedModel([response("echo still working")]), LocalEnvironment(tmp_path, 1), max_steps=1).run(
        "Keep going"
    )

    assert result == {"exit_status": "StepLimitExceeded", "submission": "", "steps": 1}


def test_agent_rejects_zero_or_multiple_actions(tmp_path: Path):
    model = FixedModel([{"role": "assistant", "content": "No command", "extra": {"actions": []}}])

    assert (
        DefaultAgent(model, LocalEnvironment(tmp_path, 1), max_steps=1).run("Do work")["exit_status"] == "FormatError"
    )


def test_agent_instructs_models_to_return_one_fenced_shell_action(tmp_path: Path):
    agent = DefaultAgent(
        FixedModel([response("echo SHELLLOOP_DONE && echo complete")]), LocalEnvironment(tmp_path, 1), 1
    )

    agent.run("Finish the task")

    assert agent.messages[0]["content"] == SYSTEM_PROMPT
    assert "exactly one POSIX shell command" in SYSTEM_PROMPT
    assert "SHELLLOOP_DONE" in SYSTEM_PROMPT


def test_agent_records_safe_lifecycle_events(tmp_path: Path):
    agent = DefaultAgent(
        FixedModel([response("echo SHELLLOOP_DONE && echo complete")]), LocalEnvironment(tmp_path, 1), max_steps=1
    )

    agent.run("A task that should not be stored in trace events")

    assert [event["event"] for event in agent.events] == [
        "run_started",
        "model_request",
        "model_response",
        "action_selected",
        "command_finished",
        "run_finished",
    ]
    assert agent.events[3]["command"] == "echo SHELLLOOP_DONE && echo complete"
    assert "should not be stored" not in str(agent.events)


def test_agent_verifies_completion_before_submitting(tmp_path: Path):
    agent = DefaultAgent(
        FixedModel([response("echo SHELLLOOP_DONE && echo complete")]),
        LocalEnvironment(tmp_path, 3),
        max_steps=1,
        verification_command=f'"{sys.executable}" -c "print(\'verified\')"',
    )

    assert agent.run("Finish and verify")["exit_status"] == "Submitted"
    assert [event["event"] for event in agent.events][-3:] == [
        "verification_started",
        "verification_finished",
        "run_finished",
    ]
    assert agent.messages[-1]["extra"]["verification"] is True


def test_agent_reports_verification_failure_after_bounded_retries(tmp_path: Path):
    agent = DefaultAgent(
        FixedModel([response("echo SHELLLOOP_DONE"), response("echo SHELLLOOP_DONE")]),
        LocalEnvironment(tmp_path, 3),
        max_steps=2,
        verification_command=f'"{sys.executable}" -c "import sys; sys.exit(2)"',
        verification_retries=1,
    )

    assert agent.run("Try verification twice") == {
        "exit_status": "VerificationFailed",
        "submission": "",
        "steps": 2,
    }
    assert sum(event["event"] == "verification_finished" for event in agent.events) == 2
