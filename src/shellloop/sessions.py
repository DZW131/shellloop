"""Create disposable copies of user workspaces for sandbox runs."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

_IGNORED = shutil.ignore_patterns(
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "artifacts",
    ".shellloop",
)


def create_session_workspace(source: Path, output_path: Path) -> Path:
    """Copy a source workspace into an artifact-owned sandbox session."""
    session = (output_path.resolve().parent / "sessions" / uuid4().hex).resolve()
    shutil.copytree(source.resolve(), session, ignore=_IGNORED)
    return session
