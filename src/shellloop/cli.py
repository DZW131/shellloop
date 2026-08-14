"""Command-line interface for Shellloop."""

from pathlib import Path

import typer

from shellloop.agents import DefaultAgent
from shellloop.config import build_run_config, load_config, serialize_config
from shellloop.environments import LocalEnvironment
from shellloop.models import demo_model
from shellloop.serialize import save_trajectory

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def main(
    task: str = typer.Option(..., "--task", "-t", help="Task given to the agent."),
    config: Path | None = typer.Option(None, "--config", "-c", help="YAML configuration file."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Trajectory output path."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="Maximum model calls."),
    yolo: bool = typer.Option(False, "--yolo", help="Skip the teaching-mode confirmation notice."),
) -> None:
    run_config = build_run_config(
        load_config(config),
        output_path=output,
        max_steps=max_steps,
        confirm=False if yolo else None,
    )
    if run_config.confirm:
        typer.confirm("Run the predefined offline demonstration command?", abort=True)

    agent = DefaultAgent(demo_model(), LocalEnvironment(run_config.workspace, run_config.timeout), run_config.max_steps)
    result = agent.run(task)
    save_trajectory(
        run_config.output_path,
        messages=agent.messages,
        result=result,
        config=serialize_config(run_config),
    )
    typer.echo(f"{result['exit_status']}: {result['submission'].strip()}")
    typer.echo(f"Trajectory saved to {run_config.output_path}")
