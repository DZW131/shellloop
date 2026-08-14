"""Command-line interface for Shellloop."""

import json
from pathlib import Path

import typer

from shellloop.agents import DefaultAgent
from shellloop.config import build_run_config, load_config, serialize_config
from shellloop.environments import LocalEnvironment
from shellloop.inspect import summarize_trajectory
from shellloop.models import demo_model
from shellloop.serialize import save_trajectory

app = typer.Typer(invoke_without_command=True, add_completion=False, no_args_is_help=True)


@app.callback()
def main(
    ctx: typer.Context,
    task: str | None = typer.Option(None, "--task", "-t", help="Task given to the agent."),
    config: Path | None = typer.Option(None, "--config", "-c", help="YAML configuration file."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Trajectory output path."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="Maximum model calls."),
    yolo: bool = typer.Option(False, "--yolo", help="Skip the teaching-mode confirmation notice."),
) -> None:
    """Run the agent loop with an offline scripted model."""
    if ctx.invoked_subcommand is not None:
        return
    if task is None:
        raise typer.BadParameter("--task is required to run the agent loop.")

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


@app.command()
def inspect(
    file: Path = typer.Argument(..., help="Path to a trajectory JSON file to inspect."),
) -> None:
    """Print a compact summary of a trajectory file without exposing raw content."""
    try:
        summary = summarize_trajectory(file)
    except FileNotFoundError:
        typer.echo(f"Error: file not found: {file}", err=True)
        raise typer.Exit(1)
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: invalid JSON in {file}: {exc.msg}", err=True)
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"exit_status: {summary['exit_status']}")
    typer.echo(f"steps: {summary['steps']}")
    typer.echo(f"message_count: {summary['message_count']}")
    typer.echo(f"command_count: {summary['command_count']}")
