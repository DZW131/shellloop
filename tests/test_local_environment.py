"""Unit tests for the LocalEnvironment command executor."""

import os
import sys
from pathlib import Path

from shellloop.environments.local import LocalEnvironment


def test_executes_command_and_returns_output(tmp_path: Path):
    result = LocalEnvironment(tmp_path, timeout=30).execute({"command": "echo hello"})

    assert result["output"] == "hello\n"
    assert result["returncode"] == 0
    assert result["exception_info"] == ""


def test_records_nonzero_returncode_for_failed_command(tmp_path: Path):
    command = f'"{sys.executable}" -c "import sys; sys.exit(3)"'
    result = LocalEnvironment(tmp_path, timeout=30).execute({"command": command})

    assert result["returncode"] == 3
    assert result["exception_info"] == ""


def test_marks_finished_when_first_output_line_is_sentinel(tmp_path: Path):
    result = LocalEnvironment(tmp_path, timeout=30).execute({"command": "echo SHELLLOOP_DONE && echo task complete"})

    assert result["finished"] is True
    assert result["submission"] == "task complete\n"


def test_does_not_mark_finished_without_sentinel(tmp_path: Path):
    result = LocalEnvironment(tmp_path, timeout=30).execute({"command": "echo plain output"})

    assert "finished" not in result


def test_runs_command_inside_configured_workspace(tmp_path: Path):
    env = LocalEnvironment(tmp_path, timeout=30)
    command = f'"{sys.executable}" -c "import os; print(os.getcwd())"'
    result = env.execute({"command": command})

    assert os.path.normcase(result["output"].strip()) == os.path.normcase(str(env.workspace))


def test_reports_timeout_with_exception_info(tmp_path: Path):
    command = f'"{sys.executable}" -c "import time; time.sleep(5)"'
    result = LocalEnvironment(tmp_path, timeout=1).execute({"command": command})

    assert result["returncode"] == -1
    assert "timed out" in result["exception_info"]
