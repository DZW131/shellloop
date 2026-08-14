"""Command-line interface for Shellloop."""

import json
import os
from dataclasses import replace
from pathlib import Path

import typer

from shellloop.agents import DefaultAgent
from shellloop.config import RunConfig, build_run_config, load_config, serialize_config
from shellloop.core import Model
from shellloop.environments import DockerEnvironment
from shellloop.harness import effective_system_prompt, load_harness
from shellloop.inspect import summarize_trajectory
from shellloop.models import OllamaCloudModel, OpenAICompatibleModel
from shellloop.models.ollama_cloud import OllamaCloudError
from shellloop.models.openai_compatible import OpenAIModelError
from shellloop.models.text_actions import TextActionFormatError
from shellloop.serialize import save_trajectory
from shellloop.sessions import create_session_workspace
from shellloop.studio import serve
from shellloop.tracing import CallbackTraceSink, format_trace_event

app = typer.Typer(invoke_without_command=True, add_completion=False, no_args_is_help=True)


@app.callback()
def main(
    ctx: typer.Context,
    task: str | None = typer.Option(None, "--task", "-t", help="Task given to the agent."),
    config: Path | None = typer.Option(None, "--config", "-c", help="YAML configuration file."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Trajectory output path."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="Maximum model calls."),
    yolo: bool = typer.Option(False, "--yolo", help="Skip the teaching-mode confirmation notice."),
    provider: str | None = typer.Option(None, "--provider", help="Model provider: ollama-cloud or openai-compatible."),
    model: str | None = typer.Option(None, "--model", help="Model name for the selected provider."),
    api_base: str | None = typer.Option(None, "--api-base", help="Chat API base URL."),
    sandbox_image: str | None = typer.Option(None, "--sandbox-image", help="Docker image used for Agent commands."),
    trace: bool = typer.Option(True, "--trace/--no-trace", help="Show the live teaching trace."),
) -> None:
    """Run the agent loop with a configured real model API."""
    if ctx.invoked_subcommand is not None:
        return
    if task is None:
        raise typer.BadParameter("--task is required to run the agent loop.")

    config_values = load_config(config)
    run_config = build_run_config(
        config_values,
        output_path=output,
        max_steps=max_steps,
        confirm=False if yolo else None,
        model_provider=provider,
        model_name=model,
        api_base=api_base,
        sandbox_image=sandbox_image,
    )
    harness = load_harness(run_config.workspace / "harness.yaml")
    run_config = replace(
        run_config,
        max_steps=harness.max_steps if max_steps is None and "max_steps" not in config_values else run_config.max_steps,
        timeout=harness.timeout if "timeout" not in config_values else run_config.timeout,
    )
    try:
        selected_model = _build_model(run_config, _api_key(run_config))
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2)
    if not DockerEnvironment.available():
        typer.echo("Error: Docker is required. Shellloop never falls back to host command execution.", err=True)
        raise typer.Exit(2)
    if run_config.confirm:
        typer.confirm("Run the agent command loop in the configured workspace?", abort=True)

    session = create_session_workspace(run_config.workspace, run_config.output_path)
    agent = DefaultAgent(
        selected_model,
        DockerEnvironment(session, run_config.timeout, run_config.sandbox_image),
        run_config.max_steps,
        CallbackTraceSink(lambda event: typer.echo(format_trace_event(event))) if trace else None,
        system_prompt=effective_system_prompt(harness),
        verification_command=harness.verification_command if harness.verification_enabled else None,
        verification_retries=harness.verification_retries,
    )
    try:
        result = agent.run(task)
    except (OllamaCloudError, OpenAIModelError, TextActionFormatError) as exc:
        save_trajectory(
            run_config.output_path,
            messages=agent.messages,
            result={"exit_status": "ModelError", "submission": "", "steps": len(agent.events)},
            config=serialize_config(run_config),
            events=agent.events,
        )
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    save_trajectory(
        run_config.output_path,
        messages=agent.messages,
        result=result,
        config=serialize_config(run_config),
        events=agent.events,
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


@app.command()
def studio(
    port: int = typer.Option(8765, min=1, max=65535, help="Local-only Studio port."),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open the local Studio in a browser."),
) -> None:
    """Start the local Shellloop Studio web workbench."""
    serve(Path.cwd(), port, open_browser)


def _api_key(config: RunConfig) -> str | None:
    return os.getenv("OLLAMA_API_KEY" if config.model_provider == "ollama-cloud" else "OPENAI_API_KEY")


def _build_model(config: RunConfig, api_key: str | None) -> Model:
    if config.model_provider not in {"ollama-cloud", "openai-compatible"}:
        raise ValueError(f"unsupported model provider: {config.model_provider}")
    if not config.model_name:
        raise ValueError("--model is required when using a model API")
    if not api_key:
        raise ValueError("an API key environment variable is required for the selected provider")
    if config.model_provider == "ollama-cloud":
        return OllamaCloudModel(config.api_base, config.model_name, api_key)
    return OpenAICompatibleModel(config.api_base, config.model_name, api_key)
