"""Versioned, user-approvable settings for the teaching Harness."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from shellloop.agents.default import SYSTEM_PROMPT

_EDITABLE_FIELDS = {
    "system_prompt",
    "max_steps",
    "timeout",
    "visible_planning",
    "verification_enabled",
    "verification_command",
    "verification_retries",
}


@dataclass(frozen=True)
class HarnessSpec:
    """The small, explicit surface an Agent may propose to improve."""

    system_prompt: str = SYSTEM_PROMPT
    max_steps: int = 8
    timeout: int = 30
    visible_planning: bool = True
    verification_enabled: bool = True
    verification_command: str = "python -m pytest -q"
    verification_retries: int = 1


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
    unexpected = set(changes) - _EDITABLE_FIELDS
    if unexpected:
        raise ValueError(f"unsupported Harness field(s): {', '.join(sorted(unexpected))}")
    return _validated_spec({**asdict(current), **changes})


def save_harness(path: Path, spec: HarnessSpec) -> None:
    """Persist a user-approved Harness configuration without credentials."""
    path.write_text(yaml.safe_dump(asdict(spec), allow_unicode=True, sort_keys=False), encoding="utf-8")


def spec_data(spec: HarnessSpec) -> dict[str, Any]:
    """Return JSON-ready public Harness fields."""
    return asdict(spec)


def effective_system_prompt(spec: HarnessSpec) -> str:
    """Apply workflow-level teaching rules without mutating the stored prompt."""
    prompt = spec.system_prompt.strip()
    if spec.visible_planning:
        prompt += " Before the code block, state a short visible plan beginning with 'Plan:'."
    if spec.verification_enabled:
        prompt += " After you signal completion, the Harness will run its configured verification command."
    return prompt


def flow_data(spec: HarnessSpec) -> list[dict[str, Any]]:
    """Describe the executable Harness workflow for visual comparison."""
    return [
        {"id": "understand", "label": "Understand", "enabled": True},
        {"id": "plan", "label": "Visible plan", "enabled": spec.visible_planning},
        {"id": "act", "label": "Sandbox action", "enabled": True},
        {"id": "observe", "label": "Observe result", "enabled": True},
        {"id": "verify", "label": "Verify", "enabled": spec.verification_enabled},
        {
            "id": "retry",
            "label": f"Retry ×{spec.verification_retries}",
            "enabled": spec.verification_enabled and spec.verification_retries > 0,
        },
        {"id": "finish", "label": "Finish", "enabled": True},
    ]


def _validated_spec(values: dict[str, Any]) -> HarnessSpec:
    spec = HarnessSpec(
        system_prompt=str(values.get("system_prompt", SYSTEM_PROMPT)),
        max_steps=int(values.get("max_steps", 8)),
        timeout=int(values.get("timeout", 30)),
        visible_planning=_bool_value(values, "visible_planning", True),
        verification_enabled=_bool_value(values, "verification_enabled", True),
        verification_command=str(values.get("verification_command", "python -m pytest -q")),
        verification_retries=int(values.get("verification_retries", 1)),
    )
    if not spec.system_prompt.strip():
        raise ValueError("Harness system_prompt must not be empty")
    if not 1 <= spec.max_steps <= 20:
        raise ValueError("Harness max_steps must be between 1 and 20")
    if not 5 <= spec.timeout <= 120:
        raise ValueError("Harness timeout must be between 5 and 120 seconds")
    if not spec.verification_command.strip() or len(spec.verification_command) > 240:
        raise ValueError("Harness verification_command must contain 1 to 240 characters")
    if "\n" in spec.verification_command or "\r" in spec.verification_command:
        raise ValueError("Harness verification_command must be a single line")
    if not 0 <= spec.verification_retries <= 3:
        raise ValueError("Harness verification_retries must be between 0 and 3")
    return spec


def _bool_value(values: dict[str, Any], key: str, default: bool) -> bool:
    value = values.get(key, default)
    if not isinstance(value, bool):
        raise TypeError(f"Harness {key} must be true or false")
    return value
