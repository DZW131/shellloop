"""Teaching-trace event sinks and helpers.

Events are plain JSON-serializable dictionaries with a fixed protocol:
``event``, ``step`` and ``summary`` are always present; the only optional
safe fields are ``command``, ``returncode``, ``finished`` and ``exit_status``.
No task text, API keys, environment variables, full model messages or tool
outputs are ever stored in an event.
"""

from __future__ import annotations

from typing import Any

from shellloop.core import TraceSink

# Fixed event names, in the order they are emitted by the agent loop.
RUN_STARTED = "run_started"
MODEL_REQUEST = "model_request"
MODEL_RESPONSE = "model_response"
ACTION_SELECTED = "action_selected"
COMMAND_FINISHED = "command_finished"
RUN_FINISHED = "run_finished"

_MAX_COMMAND_CHARS = 160

_SAFE_FIELDS = ("command", "returncode", "finished", "exit_status")


def build_event(event: str, step: int, summary: str, **fields: Any) -> dict[str, Any]:
    """Build an event dict, keeping only the fixed protocol fields.

    ``command`` is truncated to 160 characters with a trailing ``...`` when it
    is longer; unknown keyword arguments are dropped so nothing sensitive can
    leak into the event.
    """
    safe = {key: fields[key] for key in _SAFE_FIELDS if key in fields and fields[key] is not None}
    if "command" in safe:
        command = safe["command"]
        if len(command) > _MAX_COMMAND_CHARS:
            safe["command"] = command[:_MAX_COMMAND_CHARS] + "..."
    return {"event": event, "step": step, "summary": summary, **safe}


class TraceRecorder:
    """Append events to an in-memory list."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)


class ConsoleTraceSink:
    """Print one event as a single ``[trace] ...`` line."""

    def emit(self, event: dict[str, Any]) -> None:
        tail = ", ".join(f"{key}={event[key]}" for key in _SAFE_FIELDS if key in event)
        suffix = f" ({tail})" if tail else ""
        print(f"[trace] step {event.get('step', 0)} {event['event']}: {event['summary']}{suffix}")


class CompositeTraceSink:
    """Forward each event to every child sink, in order."""

    def __init__(self, *sinks: TraceSink) -> None:
        self.sinks = list(sinks)

    def emit(self, event: dict[str, Any]) -> None:
        for sink in self.sinks:
            sink.emit(event)
