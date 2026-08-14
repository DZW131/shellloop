import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shellloop.cli import _build_model, app
from shellloop.config import RunConfig
from shellloop.models import OllamaCloudModel


def test_cli_writes_a_trajectory(tmp_path: Path):
    output = tmp_path / "run.traj.json"
    result = CliRunner().invoke(app, ["--task", "Demonstrate the loop", "--output", str(output), "--yolo"])

    assert result.exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["result"]["exit_status"] == "Submitted"
    assert "Trajectory saved to" in result.output


def test_cli_requires_confirmation_by_default(tmp_path: Path):
    output = tmp_path / "run.traj.json"
    result = CliRunner().invoke(app, ["--task", "Demonstrate the loop", "--output", str(output)], input="y\n")

    assert result.exit_code == 0
    assert "Run the agent command loop in the configured workspace?" in result.output


def test_cli_rejects_unsupported_model_provider():
    result = CliRunner().invoke(app, ["--task", "Demonstrate the loop", "--provider", "unknown", "--yolo"])

    assert result.exit_code == 2
    assert "unsupported model provider" in result.output


def test_ollama_cloud_requires_an_api_key():
    config = RunConfig(workspace=Path.cwd(), model_provider="ollama-cloud", model_name="gpt-oss:120b-cloud")

    with pytest.raises(ValueError, match="OLLAMA_API_KEY"):
        _build_model(config, None)


def test_ollama_cloud_model_is_built_without_network_access():
    config = RunConfig(workspace=Path.cwd(), model_provider="ollama-cloud", model_name="gpt-oss:120b-cloud")

    assert isinstance(_build_model(config, "test-key"), OllamaCloudModel)


# --- inspect subcommand tests ---


def _write_trajectory(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "run.traj.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _normal_trajectory() -> dict:
    return {
        "messages": [
            {"role": "system", "content": "You are Shellloop."},
            {"role": "user", "content": "Demonstrate the loop."},
            {
                "role": "assistant",
                "content": "Running a command.",
                "extra": {"actions": [{"command": "echo hello"}]},
            },
            {"role": "tool", "content": "hello", "extra": {"output": "hello"}},
            {
                "role": "assistant",
                "content": "Running a second command.",
                "extra": {"actions": [{"command": "echo world"}]},
            },
            {"role": "tool", "content": "world", "extra": {"output": "world"}},
        ],
        "result": {"exit_status": "Submitted", "submission": "done", "steps": 2},
        "config": {"workspace": ".", "max_steps": 8, "timeout": 30},
    }


def test_cli_inspect_normal_trajectory(tmp_path: Path):
    path = _write_trajectory(tmp_path, _normal_trajectory())
    result = CliRunner().invoke(app, ["inspect", str(path)])

    assert result.exit_code == 0
    assert "exit_status: Submitted" in result.output
    assert "steps: 2" in result.output
    assert "message_count: 6" in result.output
    assert "command_count: 2" in result.output


def test_cli_inspect_file_not_found(tmp_path: Path):
    missing = tmp_path / "nonexistent.traj.json"
    result = CliRunner().invoke(app, ["inspect", str(missing)])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_cli_inspect_invalid_json(tmp_path: Path):
    path = tmp_path / "broken.traj.json"
    path.write_text("{not valid json", encoding="utf-8")
    result = CliRunner().invoke(app, ["inspect", str(path)])

    assert result.exit_code == 1
    assert "invalid JSON" in result.output


def test_cli_inspect_excludes_sensitive_content(tmp_path: Path):
    data = {
        "messages": [
            {
                "role": "assistant",
                "content": "Using API key sk-secret-12345.",
                "extra": {"actions": [{"command": "export KEY=sk-secret-12345"}]},
            },
            {"role": "tool", "content": "ok", "extra": {"output": ""}},
        ],
        "result": {"exit_status": "Submitted", "submission": "", "steps": 1},
        "config": {"workspace": "/home/user", "max_steps": 8, "timeout": 30},
    }
    path = _write_trajectory(tmp_path, data)
    result = CliRunner().invoke(app, ["inspect", str(path)])

    assert result.exit_code == 0
    assert "sk-secret" not in result.output
    assert "export KEY" not in result.output
    assert "API key" not in result.output
    assert "command_count: 1" in result.output


# --- teaching trace tests ---


def test_cli_displays_trace_events_by_default(tmp_path: Path):
    output = tmp_path / "run.traj.json"
    result = CliRunner().invoke(app, ["--task", "Demonstrate the loop", "--output", str(output), "--yolo"])

    assert result.exit_code == 0
    assert "[trace] step 0 run_started:" in result.output
    assert "[trace] step 1 model_request:" in result.output
    assert "run_finished: run finished (exit_status=Submitted)" in result.output


def test_cli_no_trace_hides_display_but_saves_events(tmp_path: Path):
    output = tmp_path / "run.traj.json"
    result = CliRunner().invoke(
        app, ["--task", "Demonstrate the loop", "--output", str(output), "--yolo", "--no-trace"]
    )

    assert result.exit_code == 0
    assert "[trace]" not in result.output
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["events"]
    assert data["events"][0]["event"] == "run_started"
    assert data["events"][-1]["event"] == "run_finished"


def test_cli_trajectory_events_do_not_contain_the_task_text(tmp_path: Path):
    output = tmp_path / "run.traj.json"
    task = "Demonstrate the loop with a SECRET marker"
    result = CliRunner().invoke(app, ["--task", task, "--output", str(output), "--yolo"])

    assert result.exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert task not in json.dumps(data["events"])
