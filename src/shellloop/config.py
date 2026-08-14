"""Runtime configuration loading."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RunConfig:
    workspace: Path
    max_steps: int = 8
    timeout: int = 30
    confirm: bool = True
    output_path: Path = Path("artifacts/run.traj.json")
    model_provider: str = "scripted"
    model_name: str | None = None
    ollama_base: str = "https://ollama.com/api"


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_run_config(
    values: dict[str, Any],
    *,
    workspace: Path | None = None,
    max_steps: int | None = None,
    timeout: int | None = None,
    confirm: bool | None = None,
    output_path: Path | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    ollama_base: str | None = None,
) -> RunConfig:
    return RunConfig(
        workspace=(workspace or Path(values.get("workspace", "."))).resolve(),
        max_steps=max_steps if max_steps is not None else int(values.get("max_steps", 8)),
        timeout=timeout if timeout is not None else int(values.get("timeout", 30)),
        confirm=confirm if confirm is not None else bool(values.get("confirm", True)),
        output_path=output_path or Path(values.get("output_path", "artifacts/run.traj.json")),
        model_provider=model_provider if model_provider is not None else str(values.get("model_provider", "scripted")),
        model_name=model_name if model_name is not None else values.get("model_name"),
        ollama_base=ollama_base
        if ollama_base is not None
        else str(values.get("ollama_base", "https://ollama.com/api")),
    )


def serialize_config(config: RunConfig) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, Path) else value for key, value in asdict(config).items()}
