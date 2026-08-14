"""Unit tests for trajectory serialization."""

import json
from pathlib import Path

from shellloop.serialize import save_trajectory


def test_saves_trajectory_with_messages_result_and_config(tmp_path: Path):
    path = tmp_path / "run.traj.json"
    save_trajectory(
        path,
        messages=[{"role": "user", "content": "task"}],
        result={"exit_status": "Submitted"},
        config={"max_steps": 8},
    )

    data = json.loads(path.read_text(encoding="utf-8"))

    assert set(data) == {"messages", "result", "config"}
    assert data["messages"][0]["content"] == "task"
    assert data["result"]["exit_status"] == "Submitted"
    assert data["config"]["max_steps"] == 8


def test_creates_parent_directories(tmp_path: Path):
    path = tmp_path / "nested" / "deeper" / "run.traj.json"
    save_trajectory(path, messages=[], result={}, config={})

    assert path.is_file()


def test_preserves_non_ascii_text_without_escaping(tmp_path: Path):
    path = tmp_path / "run.traj.json"
    save_trajectory(path, messages=[{"role": "user", "content": "中文任务"}], result={}, config={})

    assert "中文任务" in path.read_text(encoding="utf-8")
