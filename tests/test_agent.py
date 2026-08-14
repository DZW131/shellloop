import json
import sys
from pathlib import Path

from shellloop.agents import DefaultAgent
from shellloop.agents.default import SYSTEM_PROMPT
from shellloop.environments import LocalEnvironment
from shellloop.models import ScriptedModel


def response(command: str) -> dict:
    return {"role": "assistant", "content": command, "extra": {"actions": [{"command": command}]}}


class FakeEnvironment:
    """Return pre-scripted outputs without executing anything."""

    def __init__(self, outputs: list[dict]):
        self.outputs = list(outputs)
        self.calls: list[str] = []

    def execute(self, action: dict) -> dict:
        self.calls.append(action["command"])
        return self.outputs.pop(0)


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


def test_agent_emits_full_event_sequence_on_success():
    env = FakeEnvironment([{"output": "complete\n", "returncode": 0, "finished": True, "submission": "complete\n"}])
    agent = DefaultAgent(ScriptedModel([response("echo SHELLLOOP_DONE && echo complete")]), env, max_steps=2)

    result = agent.run("Finish the task")

    assert result["exit_status"] == "Submitted"
    assert [e["event"] for e in agent.events] == [
        "run_started",
        "model_request",
        "model_response",
        "action_selected",
        "command_finished",
        "run_finished",
    ]
    assert agent.events[0]["step"] == 0
    assert agent.events[-2]["finished"] is True
    assert agent.events[-1]["exit_status"] == "Submitted"


def test_agent_format_error_skips_execution_but_still_finishes():
    env = FakeEnvironment([])
    model = ScriptedModel([{"role": "assistant", "content": "No command", "extra": {"actions": []}}])
    agent = DefaultAgent(model, env, max_steps=1)

    result = agent.run("Do work")

    assert result["exit_status"] == "FormatError"
    assert env.calls == []
    assert [e["event"] for e in agent.events] == ["run_started", "model_request", "model_response", "run_finished"]
    assert agent.events[-1]["exit_status"] == "FormatError"


def test_agent_command_finished_reports_nonzero_returncode():
    env = FakeEnvironment(
        [
            {"output": "failed", "returncode": 2, "finished": False},
            {"output": "complete\n", "returncode": 0, "finished": True, "submission": "complete\n"},
        ]
    )
    model = ScriptedModel([response("exit 2"), response("echo SHELLLOOP_DONE && echo recovered")])
    agent = DefaultAgent(model, env, max_steps=2)

    result = agent.run("Recover from a failed command")

    assert result["exit_status"] == "Submitted"
    finished_events = [e for e in agent.events if e["event"] == "command_finished"]
    assert finished_events[0]["returncode"] == 2
    assert finished_events[0]["finished"] is False
    assert finished_events[1]["returncode"] == 0


def test_agent_emits_run_finished_on_step_limit():
    env = FakeEnvironment([{"output": "still working", "returncode": 0, "finished": False}])
    agent = DefaultAgent(ScriptedModel([response("echo still working")]), env, max_steps=1)

    result = agent.run("Keep going")

    assert result["exit_status"] == "StepLimitExceeded"
    assert agent.events[-1]["event"] == "run_finished"
    assert agent.events[-1]["exit_status"] == "StepLimitExceeded"


def test_agent_records_events_without_an_explicit_sink():
    env = FakeEnvironment([{"output": "complete\n", "returncode": 0, "finished": True, "submission": "complete\n"}])
    agent = DefaultAgent(ScriptedModel([response("echo SHELLLOOP_DONE && echo complete")]), env, max_steps=1)

    agent.run("Finish the task")

    assert agent.events[0]["event"] == "run_started"
    assert agent.events[-1]["event"] == "run_finished"


def test_agent_events_never_contain_task_or_sensitive_output():
    env = FakeEnvironment(
        [{"output": "TOOL_OUTPUT_SECRET\n", "returncode": 0, "finished": True, "submission": "TOOL_OUTPUT_SECRET\n"}]
    )
    model = ScriptedModel(
        [{"role": "assistant", "content": "sk-fake-key-12345", "extra": {"actions": [{"command": "echo ok"}]}}]
    )
    agent = DefaultAgent(model, env, max_steps=1)

    agent.run("SECRET_TASK_TEXT")

    serialized = json.dumps(agent.events)
    assert "SECRET_TASK_TEXT" not in serialized
    assert "sk-fake-key" not in serialized
    assert "TOOL_OUTPUT_SECRET" not in serialized


def test_agent_truncates_long_commands_in_events_only():
    long_command = "x" * 200
    env = FakeEnvironment([{"output": "", "returncode": 1, "finished": False}])
    agent = DefaultAgent(ScriptedModel([response(long_command)]), env, max_steps=1)

    agent.run("Run a long command")

    selected = next(e for e in agent.events if e["event"] == "action_selected")
    assert selected["command"] == "x" * 160 + "..."
    assert env.calls == [long_command]
