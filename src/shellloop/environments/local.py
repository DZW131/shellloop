"""Local command execution for a configured workspace."""

import subprocess
from pathlib import Path

from shellloop.core import Action, Output


class LocalEnvironment:
    """Execute one shell command at a time in a configured workspace."""

    def __init__(self, workspace: Path, timeout: int):
        self.workspace = workspace.resolve()
        self.timeout = timeout

    def execute(self, action: Action) -> Output:
        command = action.get("command", "")
        try:
            result = subprocess.run(
                command,
                cwd=self.workspace,
                shell=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout,
                check=False,
            )
            output = {"output": result.stdout, "returncode": result.returncode, "exception_info": ""}
        except subprocess.TimeoutExpired as error:
            output = {
                "output": error.stdout or "",
                "returncode": -1,
                "exception_info": f"Command timed out after {self.timeout} seconds.",
            }

        lines = output["output"].lstrip().splitlines(keepends=True)
        if output["returncode"] == 0 and lines and lines[0].strip() == "SHELLLOOP_DONE":
            output["finished"] = True
            output["submission"] = "".join(lines[1:])
        return output
