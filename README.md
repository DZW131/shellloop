# Shellloop

Shellloop is a small, traceable coding agent for teaching how an
LLM-to-shell loop works:

~~~text
task -> model -> shell action -> observation -> model -> trajectory
~~~

Version 0.1 uses an offline scripted model by default. This keeps the core
agent deterministic, free to run, and easy to test before a real model API is
introduced.

## Safety

Shellloop executes shell commands. Run it only in an isolated WSL, Linux, or
container workspace that contains no secrets. The local environment is not a
security sandbox. Keep confirmation enabled and use a small step limit.

## Setup

~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
~~~

On Windows, run these commands inside WSL rather than native PowerShell.

## Offline demo

~~~bash
shellloop --task "Demonstrate the agent loop" --output artifacts/demo.traj.json
~~~

The default scripted model runs a harmless demonstration command and writes the
full conversation and command observations to the output file.

## Inspecting trajectories

After a run, inspect the trajectory summary without exposing raw messages,
shell commands, or sensitive content:

~~~bash
shellloop inspect artifacts/demo.traj.json
~~~

Output:

~~~text
exit_status: Submitted
steps: 2
message_count: 6
command_count: 2
~~~

The inspect command only reads the file—it does not execute any commands
contained in the trajectory. If the file is missing, contains invalid JSON, or
lacks required fields, a clear error is printed and the exit code is non-zero.

## Tests

~~~bash
pytest -q
ruff check src tests
ruff format --check src tests
~~~

## Configuration

~~~yaml
workspace: .
max_steps: 8
timeout: 30
confirm: true
output_path: artifacts/run.traj.json
~~~

Pass a configuration file with:

~~~bash
shellloop --task "Demonstrate the agent loop" --config examples/basic.yaml
~~~

Command-line options override the configuration file.

## Repository structure

~~~text
src/shellloop/
  agents/          Agent control flow
  environments/    Shell execution
  models/          Offline model implementations
  cli.py           Command-line interface
  config.py        YAML loading and runtime configuration
  inspect.py       Offline trajectory summary tool
  serialize.py     Trajectory persistence
tests/             Offline unit and CLI tests
examples/          Runnable configuration examples
~~~

## Development roadmap

- v0.1: offline scripted model, one-action agent loop, local execution, CLI,
  JSON trajectories, and tests.
- v0.2: one real OpenAI-compatible model adapter and command-format parsing.
- v0.3: optional sandbox backends and trajectory inspection.

## License and credits

Shellloop is released under the MIT License. See [CREDITS.md](CREDITS.md) for
the project inspiration and attribution boundary.
