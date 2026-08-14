"""Trajectory persistence."""

import json
from pathlib import Path
from typing import Any


def save_trajectory(path: Path, *, messages: list[dict], result: dict[str, Any], config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"messages": messages, "result": result, "config": config}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
