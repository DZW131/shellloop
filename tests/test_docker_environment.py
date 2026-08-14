import subprocess
from pathlib import Path

import pytest

from shellloop.environments.docker import DockerEnvironment


class AvailableDockerEnvironment(DockerEnvironment):
    @staticmethod
    def available(image: str | None = None) -> bool:
        return True


class UnavailableDockerEnvironment(DockerEnvironment):
    @staticmethod
    def available(image: str | None = None) -> bool:
        return False


class BrokenDockerEnvironment(DockerEnvironment):
    @staticmethod
    def available(image: str | None = None) -> bool:
        return True


@pytest.mark.parametrize(
    ("returncodes", "image", "expected"),
    [([1], None, False), ([0], None, True), ([0, 1], "shellloop:test", False), ([0, 0], "shellloop:test", True)],
)
def test_docker_availability_requires_a_live_engine_and_requested_image(
    returncodes: list[int], image: str | None, expected: bool, monkeypatch: pytest.MonkeyPatch
):
    results = iter(returncodes)
    monkeypatch.setattr("shellloop.environments.docker.shutil.which", lambda command: "docker")
    monkeypatch.setattr(
        "shellloop.environments.docker.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, next(results)),
    )

    assert DockerEnvironment.available(image) is expected


def test_docker_environment_uses_a_restricted_container(tmp_path: Path):
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "SHELLLOOP_DONE\ncomplete\n")

    result = AvailableDockerEnvironment(tmp_path, 30, "python:3.11-slim", runner).execute({"command": "echo done"})

    assert result["finished"] is True
    assert result["submission"] == "complete\n"
    assert calls == [
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
            f"type=bind,src={tmp_path.resolve()},dst=/workspace",
            "--workdir",
            "/workspace",
            "python:3.11-slim",
            "sh",
            "-lc",
            "echo done",
        ]
    ]


def test_docker_environment_never_runs_the_host_shell_when_docker_is_missing(tmp_path: Path):
    result = UnavailableDockerEnvironment(tmp_path, 30, "python:3.11-slim").execute({"command": "echo should-not-run"})

    assert result["returncode"] == -2
    assert "Docker is required" in result["exception_info"]


def test_docker_environment_fails_closed_when_the_docker_process_disappears(tmp_path: Path):
    def runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    result = BrokenDockerEnvironment(tmp_path, 30, "python:3.11-slim", runner).execute(
        {"command": "echo should-not-run"}
    )

    assert result["returncode"] == -2
    assert "unavailable" in result["exception_info"]
