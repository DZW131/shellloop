"""The minimal model-to-shell control loop."""

import os
from typing import Any

from shellloop.core import Environment, Message, Model


def build_system_prompt(*, is_windows: bool) -> str:
    """Build the agent system prompt with a platform-appropriate completion protocol."""
    join = "&" if is_windows else "&&"
    shell = "cmd.exe" if is_windows else "POSIX shell"
    return (
        "You are Shellloop, a minimal coding agent. Respond with exactly one shell command "
        "inside a single fenced bash code block and do not include explanation text outside "
        f"the code block. When the task is complete, the final action's first line of output "
        f"must be SHELLLOOP_DONE, followed by the result on the following lines. This machine "
        f"runs {shell}; complete a task with e.g. `echo SHELLLOOP_DONE {join} <command>`."
    )


SYSTEM_PROMPT = build_system_prompt(is_windows=os.name == "nt")


class DefaultAgent:
    """Run one model action per step until completion or a step limit."""

    def __init__(self, model: Model, environment: Environment, max_steps: int):
        self.model = model
        self.environment = environment
        self.max_steps = max_steps
        self.messages: list[Message] = []

    def run(self, task: str) -> dict[str, Any]:
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
        for step in range(1, self.max_steps + 1):
            message = self.model.query(self.messages)
            self.messages.append(message)
            actions = message.get("extra", {}).get("actions", [])
            if len(actions) != 1:
                return {"exit_status": "FormatError", "submission": "", "steps": step}

            output = self.environment.execute(actions[0])
            self.messages.append({"role": "tool", "content": output["output"], "extra": output})
            if output.get("finished"):
                return {"exit_status": "Submitted", "submission": output["submission"], "steps": step}
        return {"exit_status": "StepLimitExceeded", "submission": "", "steps": self.max_steps}
