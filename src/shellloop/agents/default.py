"""The minimal model-to-shell control loop."""

from time import perf_counter
from typing import Any

from shellloop.core import Environment, Message, Model, TraceEvent, TraceSink
from shellloop.tracing import assistant_preview, command_preview, safe_preview

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
        verification_command: str | None = None,
        verification_retries: int = 0,
    ):
        self.model = model
        self.environment = environment
        self.max_steps = max_steps
        self.trace_sink = trace_sink
        self.system_prompt = system_prompt
        self.verification_command = verification_command
        self.verification_retries = verification_retries
        self.messages: list[Message] = []
        self.events: list[TraceEvent] = []

    def run(self, task: str) -> dict[str, Any]:
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        self.events = []
        self._emit(
            "run_started",
            0,
            "task accepted",
            phase="agent",
            max_steps=self.max_steps,
            verification_enabled=self.verification_command is not None,
        )
        verification_failures = 0
        for step in range(1, self.max_steps + 1):
            self._emit("model_request", step, "waiting for model", phase="model", message_count=len(self.messages))
            model_started = perf_counter()
            try:
                message = self.model.query(self.messages)
            except Exception:
                self._emit("run_finished", step, "model request failed", phase="agent", exit_status="ModelError")
                raise
            self.messages.append(message)
            actions = message.get("extra", {}).get("actions", [])
            self._emit(
                "model_response",
                step,
                f"{len(actions)} shell action(s) parsed",
                phase="model",
                duration_ms=_milliseconds(model_started),
                action_count=len(actions),
                response_preview=assistant_preview(str(message.get("content", ""))),
            )
            if len(actions) != 1:
                return self._finish("FormatError", "", step)

            self._emit(
                "action_selected",
                step,
                "command selected",
                phase="agent",
                command=command_preview(actions[0]["command"]),
            )
            command_started = perf_counter()
            output = self.environment.execute(actions[0])
            self.messages.append({"role": "tool", "content": output["output"], "extra": output})
            self._emit(
                "command_finished",
                step,
                "command completed",
                phase="sandbox",
                returncode=output["returncode"],
                finished=bool(output.get("finished")),
                duration_ms=_milliseconds(command_started),
                output_line_count=len(str(output.get("output", "")).splitlines()),
                output_preview=safe_preview(str(output.get("output", ""))),
            )
            if output.get("finished"):
                if self.verification_command is None:
                    return self._finish("Submitted", output["submission"], step)
                verification = self._verify(step)
                if verification["returncode"] == 0:
                    return self._finish("Submitted", output["submission"], step)
                verification_failures += 1
                if verification_failures > self.verification_retries:
                    return self._finish("VerificationFailed", "", step)
        return self._finish("StepLimitExceeded", "", self.max_steps)

    def _verify(self, step: int) -> dict[str, Any]:
        command = self.verification_command or ""
        self._emit(
            "verification_started",
            step,
            "candidate verification started",
            phase="verification",
            command=command_preview(command),
        )
        started = perf_counter()
        output = self.environment.execute({"command": command})
        self.messages.append({"role": "tool", "content": output["output"], "extra": {**output, "verification": True}})
        self._emit(
            "verification_finished",
            step,
            "candidate verification completed",
            phase="verification",
            returncode=output["returncode"],
            duration_ms=_milliseconds(started),
            output_line_count=len(str(output.get("output", "")).splitlines()),
            output_preview=safe_preview(str(output.get("output", ""))),
        )
        return output

    def _finish(self, exit_status: str, submission: str, steps: int) -> dict[str, Any]:
        self._emit("run_finished", steps, "agent stopped", phase="agent", exit_status=exit_status)
        return {"exit_status": exit_status, "submission": submission, "steps": steps}

    def _emit(self, name: str, step: int, summary: str, **values: Any) -> None:
        event: TraceEvent = {"event": name, "step": step, "summary": summary, **values}
        self.events.append(event)
        if self.trace_sink is not None:
            self.trace_sink.emit(event)


def _milliseconds(started: float) -> int:
    return round((perf_counter() - started) * 1000)
