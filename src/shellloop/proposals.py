"""Constrained natural-language proposals for Harness evolution."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from shellloop.core import Message
from shellloop.harness import HarnessSpec, flow_data, update_harness


class CompletionModel(Protocol):
    """Return raw model text without requiring an executable action."""

    def complete(self, messages: list[Message]) -> str: ...


@dataclass
class HarnessProposal:
    """A candidate config revision that cannot write itself to the active Harness."""

    summary: str
    current: HarnessSpec
    candidate: HarnessSpec
    id: str = field(default_factory=lambda: uuid4().hex)
    verification_returncode: int | None = None
    verification_duration_ms: int | None = None
    applied: bool = False
    comparison: dict[str, Any] | None = None
    origin: str = "natural-language"
    source_version_id: str | None = None

    @property
    def verified(self) -> bool:
        return self.verification_returncode == 0


def generate_proposal(model: CompletionModel, request: str, current: HarnessSpec) -> HarnessProposal:
    """Ask a real model for a JSON-only change within the Harness allowlist."""
    text = model.complete(
        [
            {
                "role": "system",
                "content": (
                    "You improve a beginner-friendly Agent Harness. Return JSON only with a concise summary and a "
                    "changes object. The only allowed keys are system_prompt, max_steps, timeout, visible_planning, "
                    "verification_enabled, verification_command, and verification_retries. The verification command "
                    "runs only in a disposable Docker workspace. Do not include API keys, file paths, markdown, or "
                    "extra keys."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"current_harness": asdict(current), "improvement_request": request}, ensure_ascii=False
                ),
            },
        ]
    )
    data = _json_object(text)
    summary = data.get("summary")
    changes = data.get("changes")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("proposal response must include a non-empty summary")
    if not isinstance(changes, dict):
        raise TypeError("proposal response must include a changes object")
    return HarnessProposal(summary=summary.strip(), current=current, candidate=update_harness(current, changes))


def proposal_data(proposal: HarnessProposal) -> dict[str, Any]:
    """Return the safe, displayable proposal state without request or credential data."""
    current = asdict(proposal.current)
    candidate = asdict(proposal.candidate)
    return {
        "id": proposal.id,
        "summary": proposal.summary,
        "current": current,
        "candidate": candidate,
        "changed_fields": [key for key in current if current[key] != candidate[key]],
        "current_flow": flow_data(proposal.current),
        "candidate_flow": flow_data(proposal.candidate),
        "verified": proposal.verified,
        "verification": {
            "returncode": proposal.verification_returncode,
            "duration_ms": proposal.verification_duration_ms,
            "command": proposal.candidate.verification_command,
        },
        "applied": proposal.applied,
        "comparison": proposal.comparison,
        "origin": proposal.origin,
        "source_version_id": proposal.source_version_id,
    }


def _json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise ValueError("proposal response is not a complete JSON code block")
        stripped = "\n".join(lines[1:-1])
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as error:
        raise ValueError("proposal response is not valid JSON") from error
    if not isinstance(data, dict):
        raise TypeError("proposal response must be a JSON object")
    return data
