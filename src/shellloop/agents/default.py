"""The minimal model-to-shell control loop."""

from typing import Any

from shellloop.core import Environment, Message, Model


class DefaultAgent:
    """Run one model action per step until completion or a step limit."""

    def __init__(self, model: Model, environment: Environment, max_steps: int):
        self.model = model
        self.environment = environment
        self.max_steps = max_steps
        self.messages: list[Message] = []

    def run(self, task: str) -> dict[str, Any]:
        self.messages = [
            {"role": "system", "content": "You are Shellloop, a minimal coding agent."},
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
