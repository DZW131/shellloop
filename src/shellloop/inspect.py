"""Offline trajectory summary tool.

Reads a trajectory JSON file and produces a compact summary:
exit_status, steps, message count, and command count.

No raw message content, environment variables, API keys, or full model
responses are included in the summary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REQUIRED_KEYS = ("messages", "result", "config")


def summarize_trajectory(path: str | Path) -> dict[str, Any]:
    """Load and summarize a trajectory JSON file.

    Parameters
    ----------
    path:
        Path to a trajectory JSON file produced by ``save_trajectory``.

    Returns
    -------
    dict with keys:
        - ``exit_status`` (str): agent exit status from ``result``.
        - ``steps`` (int): number of steps taken from ``result``.
        - ``message_count`` (int): total number of messages.
        - ``command_count`` (int): number of shell commands executed.

    Raises
    ------
    ValueError
        If the file is missing required top-level keys (``messages``,
        ``result``, or ``config``).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"Trajectory file is missing required key(s): {', '.join(missing)}")

    result = data["result"]
    messages: list[dict[str, Any]] = data["messages"]

    command_count = 0
    for msg in messages:
        actions = msg.get("extra", {}).get("actions", [])
        command_count += sum(1 for action in actions if action.get("command"))

    return {
        "exit_status": result.get("exit_status", "unknown"),
        "steps": result.get("steps", 0),
        "message_count": len(messages),
        "command_count": command_count,
    }
