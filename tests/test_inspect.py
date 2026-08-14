"""Tests for the trajectory summary tool."""

import json
from pathlib import Path

import pytest

from shellloop.inspect import summarize_trajectory


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


def test_summarize_normal_trajectory(tmp_path: Path):
    path = _write_trajectory(tmp_path, _normal_trajectory())
    summary = summarize_trajectory(path)

    assert summary["exit_status"] == "Submitted"
    assert summary["steps"] == 2
    assert summary["message_count"] == 6
    assert summary["command_count"] == 2


def test_summarize_missing_result_key(tmp_path: Path):
    data = _normal_trajectory()
    del data["result"]
    path = _write_trajectory(tmp_path, data)

    with pytest.raises(ValueError, match="result"):
        summarize_trajectory(path)


def test_summarize_missing_messages_key(tmp_path: Path):
    data = _normal_trajectory()
    del data["messages"]
    path = _write_trajectory(tmp_path, data)

    with pytest.raises(ValueError, match="messages"):
        summarize_trajectory(path)


def test_summary_excludes_sensitive_content(tmp_path: Path):
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
    summary = summarize_trajectory(path)
    summary_text = json.dumps(summary, ensure_ascii=False)

    assert "sk-secret" not in summary_text
    assert "export KEY" not in summary_text
    assert "API key" not in summary_text
    assert summary["command_count"] == 1
