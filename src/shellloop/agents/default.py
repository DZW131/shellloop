"""The minimal model-to-shell control loop."""

from typing import Any

from shellloop.core import Environment, Message, Model, TraceSink
from shellloop.tracing import (
    ACTION_SELECTED,
    COMMAND_FINISHED,
    MODEL_REQUEST,
    MODEL_RESPONSE,
    RUN_FINISHED,
    RUN_STARTED,
    TraceRecorder,
    build_event,
)

SYSTEM_PROMPT = (
    "You are Shellloop, a minimal coding agent. Respond with exactly one shell command "
    "inside a fenced bash code block and do not include another code block."
)


def _action_summary(count: int) -> str:
    if count == 0:
        return "no shell action parsed"
    if count == 1:
        return "one shell action parsed"
    return f"{count} shell actions parsed"


class DefaultAgent:
    """Run one model action per step until completion or a step limit.

    A teaching-trace event is emitted for every observable state change of the
    loop: task start, model request/response, action selection, command
    completion, and the final exit status. Events are always recorded on the
    agent (``agent.events``); an optional ``trace_sink`` receives the same
    events for live display without the agent knowing how they are rendered.
    """

    def __init__(
        self,
        model: Model,
        environment: Environment,
        max_steps: int,
        trace_sink: TraceSink | None = None,
    ):
        self.model = model
        self.environment = environment
        self.max_steps = max_steps
        self.messages: list[Message] = []
        self._recorder = TraceRecorder()
        self.events: list[dict[str, Any]] = self._recorder.events
        self._trace_sink = trace_sink

    def _emit(self, event: dict[str, Any]) -> None:
        self._recorder.emit(event)
        if self._trace_sink is not None:
            self._trace_sink.emit(event)

    def run(self, task: str) -> dict[str, Any]:
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
        self._emit(build_event(RUN_STARTED, 0, "task accepted"))
        for step in range(1, self.max_steps + 1):
            self._emit(build_event(MODEL_REQUEST, step, "waiting for model"))
            message = self.model.query(self.messages)
            self.messages.append(message)
            actions = message.get("extra", {}).get("actions", [])
            self._emit(build_event(MODEL_RESPONSE, step, _action_summary(len(actions))))
            if len(actions) != 1:
                result = {"exit_status": "FormatError", "submission": "", "steps": step}
                self._emit(build_event(RUN_FINISHED, step, "run finished", exit_status="FormatError"))
                return result

            self._emit(build_event(ACTION_SELECTED, step, "command selected", command=actions[0]["command"]))
            output = self.environment.execute(actions[0])
            self.messages.append({"role": "tool", "content": output["output"], "extra": output})
            self._emit(
                build_event(
                    COMMAND_FINISHED,
                    step,
                    "command finished",
                    returncode=output["returncode"],
                    finished=output.get("finished", False),
                )
            )
            if output.get("finished"):
                result = {"exit_status": "Submitted", "submission": output["submission"], "steps": step}
                self._emit(build_event(RUN_FINISHED, step, "run finished", exit_status="Submitted"))
                return result
        result = {"exit_status": "StepLimitExceeded", "submission": "", "steps": self.max_steps}
        self._emit(build_event(RUN_FINISHED, self.max_steps, "run finished", exit_status="StepLimitExceeded"))
        return result
