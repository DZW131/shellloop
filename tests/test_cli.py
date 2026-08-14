import json
from pathlib import Path

from typer.testing import CliRunner

from shellloop.cli import app


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
    assert "Run the predefined offline demonstration command?" in result.output
