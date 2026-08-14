"""Shared protocols and message types."""

from typing import Any, Protocol

Message = dict[str, Any]
Action = dict[str, str]
Output = dict[str, Any]
TraceEvent = dict[str, Any]


class Model(Protocol):
    """Return one assistant message for the current history."""

    def query(self, messages: list[Message]) -> Message: ...


class Environment(Protocol):
    """Execute one action and return a structured observation."""

    def execute(self, action: Action) -> Output: ...


class Agent(Protocol):
    """Run a task until it finishes or reaches a limit."""

    def run(self, task: str) -> dict[str, Any]: ...


class TraceSink(Protocol):
    """Receive one safe, observable Agent lifecycle event."""

    def emit(self, event: TraceEvent) -> None: ...
