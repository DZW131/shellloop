"""Create disposable copies of user workspaces for sandbox runs."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
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


@contextmanager
def temporary_session_workspace(source: Path) -> Iterator[Path]:
    """Yield an isolated workspace that is destroyed after private evaluation."""
    with TemporaryDirectory(prefix="shellloop-evaluation-") as directory:
        session = Path(directory) / "workspace"
        shutil.copytree(source.resolve(), session, ignore=_IGNORED)
        yield session
