"""Versioned, user-approvable settings for the teaching Harness."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from shellloop.agents.default import SYSTEM_PROMPT


@dataclass(frozen=True)
class HarnessSpec:
    """The small, explicit surface an Agent may propose to improve."""

    system_prompt: str = SYSTEM_PROMPT
    max_steps: int = 8
    timeout: int = 30


def load_harness(path: Path) -> HarnessSpec:
    """Load a Harness spec or return the stable default before first approval."""
    if not path.exists():
        return HarnessSpec()
    values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(values, dict):
        raise TypeError("harness configuration must be a mapping")
    return _validated_spec(values)


def update_harness(current: HarnessSpec, changes: dict[str, Any]) -> HarnessSpec:
    """Apply only approved, bounded fields to a candidate Harness spec."""
    unexpected = set(changes) - set(asdict(current))
    if unexpected:
        raise ValueError(f"unsupported Harness field(s): {', '.join(sorted(unexpected))}")
    return _validated_spec({**asdict(current), **changes})


def save_harness(path: Path, spec: HarnessSpec) -> None:
    """Persist a user-approved Harness configuration without credentials."""
    path.write_text(yaml.safe_dump(asdict(spec), allow_unicode=True, sort_keys=False), encoding="utf-8")


def spec_data(spec: HarnessSpec) -> dict[str, Any]:
    """Return JSON-ready public Harness fields."""
    return asdict(spec)


def _validated_spec(values: dict[str, Any]) -> HarnessSpec:
    spec = HarnessSpec(
        system_prompt=str(values.get("system_prompt", SYSTEM_PROMPT)),
        max_steps=int(values.get("max_steps", 8)),
        timeout=int(values.get("timeout", 30)),
    )
    if not spec.system_prompt.strip():
        raise ValueError("Harness system_prompt must not be empty")
    if not 1 <= spec.max_steps <= 20:
        raise ValueError("Harness max_steps must be between 1 and 20")
    if not 5 <= spec.timeout <= 120:
        raise ValueError("Harness timeout must be between 5 and 120 seconds")
    return spec
