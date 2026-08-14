import sys
from pathlib import Path

from shellloop.agents import DefaultAgent
from shellloop.agents.default import SYSTEM_PROMPT
from shellloop.environments import LocalEnvironment
from shellloop.models import ScriptedModel


def response(command: str) -> dict:
    return {"role": "assistant", "content": command, "extra": {"actions": [{"command": command}]}}


def test_agent_saves_successful_submission(tmp_path: Path):
    model = ScriptedModel([response("echo SHELLLOOP_DONE && echo complete")])
    result = DefaultAgent(model, LocalEnvironment(tmp_path, 1), max_steps=2).run("Finish the task")

    assert result == {"exit_status": "Submitted", "submission": "complete\n", "steps": 1}


def test_agent_records_failed_command_before_completion(tmp_path: Path):
    failed_command = f'"{sys.executable}" -c "import sys; print(\u0027failed\u0027); sys.exit(1)"'
    model = ScriptedModel([response(failed_command), response("echo SHELLLOOP_DONE && echo recovered")])
    agent = DefaultAgent(model, LocalEnvironment(tmp_path, 1), max_steps=2)

    assert agent.run("Recover from a failed command")["submission"] == "recovered\n"
    assert agent.messages[3]["extra"]["returncode"] != 0


def test_agent_stops_at_step_limit(tmp_path: Path):
    result = DefaultAgent(
        ScriptedModel([response("echo still working")]), LocalEnvironment(tmp_path, 1), max_steps=1
    ).run("Keep going")

    assert result == {"exit_status": "StepLimitExceeded", "submission": "", "steps": 1}


def test_agent_rejects_zero_or_multiple_actions(tmp_path: Path):
    model = ScriptedModel([{"role": "assistant", "content": "No command", "extra": {"actions": []}}])

    assert (
        DefaultAgent(model, LocalEnvironment(tmp_path, 1), max_steps=1).run("Do work")["exit_status"] == "FormatError"
    )


def test_agent_instructs_models_to_return_one_fenced_shell_action(tmp_path: Path):
    agent = DefaultAgent(
        ScriptedModel([response("echo SHELLLOOP_DONE && echo complete")]), LocalEnvironment(tmp_path, 1), 1
    )

    agent.run("Finish the task")

    assert agent.messages[0]["content"] == SYSTEM_PROMPT
    assert "exactly one shell command" in SYSTEM_PROMPT
