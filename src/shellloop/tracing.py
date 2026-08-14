"""Safe lifecycle events shared by terminal and Studio views."""

from __future__ import annotations

import re
from collections.abc import Callable

from shellloop.core import TraceEvent

_SECRET_VALUE = re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*=\s*[^\s;&]+")
_BEARER_VALUE = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{8,}")
_KEY_VALUE = re.compile(r"(?i)\b(?:sk|key)-[a-z0-9_-]{8,}\b")
_FENCED_BLOCK = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)


def command_preview(command: str, limit: int = 160) -> str:
    """Return a bounded command preview without common inline secret values."""
    preview = safe_preview(" ".join(command.split()), limit)
    return preview


def safe_preview(text: str, limit: int = 600) -> str:
    """Redact common credentials and bound observable model or tool text."""
    preview = _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=***", text.strip())
    preview = _BEARER_VALUE.sub("Bearer ***", preview)
    preview = _KEY_VALUE.sub("key-***", preview)
    return preview if len(preview) <= limit else f"{preview[: limit - 3]}..."


def assistant_preview(text: str, limit: int = 600) -> str:
    """Expose a model's visible explanation while keeping its action separate."""
    return safe_preview(_FENCED_BLOCK.sub("[shell action shown separately]", text), limit)


def format_trace_event(event: TraceEvent) -> str:
    """Format one event for a compact terminal timeline."""
    detail = event["summary"]
    if "command" in event:
        detail = f"{detail}: {event['command']}"
    elif "returncode" in event:
        detail = f"{detail}: returncode={event['returncode']}, finished={event.get('finished', False)}"
    elif "exit_status" in event:
        detail = f"{detail}: {event['exit_status']}"
    return f"[trace] step {event['step']} {event['event']} — {detail}"


class CallbackTraceSink:
    """Forward trace events to a caller-owned callback."""

    def __init__(self, callback: Callable[[TraceEvent], None]) -> None:
        self._callback = callback

    def emit(self, event: TraceEvent) -> None:
        self._callback(event)
