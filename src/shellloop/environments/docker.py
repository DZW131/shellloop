"""Disposable Docker execution for untrusted Agent shell actions."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from shellloop.core import Action, Output


class DockerEnvironment:
    """Execute one command in a network-isolated, disposable Docker container."""

    def __init__(
        self,
        workspace: Path,
        timeout: int,
        image: str,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.workspace = workspace.resolve()
        self.timeout = timeout
        self.image = image
        self._runner = runner

    @staticmethod
    def available() -> bool:
        return shutil.which("docker") is not None

    def execute(self, action: Action) -> Output:
        if not self.available():
            return {
                "output": "",
                "returncode": -2,
                "exception_info": "Docker is required for Shellloop sandbox execution.",
                "duration_ms": 0,
            }
        command = action.get("command", "")
        started = perf_counter()
        try:
            result = self._runner(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,size=64m",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--pids-limit",
                    "128",
                    "--memory",
                    "512m",
                    "--cpus",
                    "1",
                    "--mount",
                    f"type=bind,src={self.workspace},dst=/workspace",
                    "--workdir",
                    "/workspace",
                    self.image,
                    "sh",
                    "-lc",
                    command,
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout,
                check=False,
            )
            output: Output = {"output": result.stdout, "returncode": result.returncode, "exception_info": ""}
        except subprocess.TimeoutExpired as error:
            output = {
                "output": error.stdout or "",
                "returncode": -1,
                "exception_info": f"Command timed out after {self.timeout} seconds.",
            }
        except OSError:
            output = {
                "output": "",
                "returncode": -2,
                "exception_info": "Docker sandbox execution is unavailable.",
            }

        output["duration_ms"] = round((perf_counter() - started) * 1000)

        lines = output["output"].lstrip().splitlines(keepends=True)
        if output["returncode"] == 0 and lines and lines[0].strip() == "SHELLLOOP_DONE":
            output["finished"] = True
            output["submission"] = "".join(lines[1:])
        return output
