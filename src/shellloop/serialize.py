"""Trajectory persistence."""

import json
from pathlib import Path
from typing import Any


def save_trajectory(
    path: Path,
    *,
    messages: list[dict],
    result: dict[str, Any],
    config: dict[str, Any],
    events: list[dict] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"messages": messages, "result": result, "config": config}
    if events is not None:
        data["events"] = events
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
