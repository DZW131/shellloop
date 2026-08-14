"""The minimal model-to-shell control loop."""

from typing import Any

from shellloop.core import Environment, Message, Model, TraceEvent, TraceSink
from shellloop.tracing import command_preview

SYSTEM_PROMPT = (
    "You are Shellloop, a beginner-friendly coding agent running inside a Linux Docker sandbox. "
    "Respond with exactly one POSIX shell command inside one fenced bash code block. You may give a short visible "
    "plan before the code block, but never include a second code block. Commands only affect the disposable "
    "workspace copy. When the task is complete, make the first output line of your final command exactly "
    "SHELLLOOP_DONE, then print a concise result on later lines."
)


class DefaultAgent:
    """Run one model action per step until completion or a step limit."""

    def __init__(
        self,
        model: Model,
        environment: Environment,
        max_steps: int,
        trace_sink: TraceSink | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self.model = model
        self.environment = environment
        self.max_steps = max_steps
        self.trace_sink = trace_sink
        self.system_prompt = system_prompt
        self.messages: list[Message] = []
        self.events: list[TraceEvent] = []

    def run(self, task: str) -> dict[str, Any]:
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        self.events = []
        self._emit("run_started", 0, "task accepted")
        for step in range(1, self.max_steps + 1):
            self._emit("model_request", step, "waiting for model")
            try:
                message = self.model.query(self.messages)
            except Exception:
                self._emit("run_finished", step, "model request failed", exit_status="ModelError")
                raise
            self.messages.append(message)
            actions = message.get("extra", {}).get("actions", [])
            self._emit("model_response", step, f"{len(actions)} shell action(s) parsed")
            if len(actions) != 1:
                return self._finish("FormatError", "", step)

            self._emit("action_selected", step, "command selected", command=command_preview(actions[0]["command"]))
            output = self.environment.execute(actions[0])
            self.messages.append({"role": "tool", "content": output["output"], "extra": output})
            self._emit(
                "command_finished",
                step,
                "command completed",
                returncode=output["returncode"],
                finished=bool(output.get("finished")),
            )
            if output.get("finished"):
                return self._finish("Submitted", output["submission"], step)
        return self._finish("StepLimitExceeded", "", self.max_steps)

    def _finish(self, exit_status: str, submission: str, steps: int) -> dict[str, Any]:
        self._emit("run_finished", steps, "agent stopped", exit_status=exit_status)
        return {"exit_status": exit_status, "submission": submission, "steps": steps}

    def _emit(self, name: str, step: int, summary: str, **values: Any) -> None:
        event: TraceEvent = {"event": name, "step": step, "summary": summary, **values}
        self.events.append(event)
        if self.trace_sink is not None:
            self.trace_sink.emit(event)
