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

On Windows, WSL is recommended for isolation. Native PowerShell users can use
the student launcher below.

## Student quick start on Windows

After cloning or downloading this repository, double-click `start.bat`. On its
first run it creates `.venv` and installs the project automatically. Then
choose one of the two menu options:

1. **Offline demo** — no account or API key required.
2. **Ollama Cloud** — enter a model name and API key when prompted; the key is
   hidden while typing and is not saved to disk.

The launcher asks for a task, requires a safety confirmation, saves a trajectory
under `artifacts/`, and prints its safe summary. For scripted use, teachers can
also run `powershell -ExecutionPolicy Bypass -File .\start.ps1 -Mode offline -Task "Demonstrate the loop" -Yes`.

## Offline demo

~~~bash
shellloop --task "Demonstrate the agent loop" --output artifacts/demo.traj.json
~~~

The default scripted model runs a harmless demonstration command and writes the
full conversation and command observations to the output file.

## Ollama Cloud

Shellloop can call Ollama Cloud directly without a local Ollama service. Create
an API key in Ollama, then set it only in your shell environment:

~~~powershell
$env:OLLAMA_API_KEY = "your_api_key"
shellloop --provider ollama-cloud --model "gpt-oss:120b-cloud" --task "List the files" --output artifacts/cloud.traj.json
~~~

On WSL or Linux, use `export OLLAMA_API_KEY='your_api_key'` instead. The key is
sent only as an authorization header; never put it in YAML, source code, a
trajectory, or a Git commit. See `examples/ollama-cloud.yaml` for non-secret
settings. Ollama Cloud model names and API keys are managed in Ollama.

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
model_provider: scripted
model_name: null
ollama_base: https://ollama.com/api
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
  models/          Scripted, OpenAI-compatible, and Ollama Cloud model implementations
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
- v0.2: OpenAI-compatible and Ollama Cloud model adapters, command-format parsing,
  and trajectory inspection.
- Next: optional sandbox backends and command-permission policies.

## License and credits

Shellloop is released under the MIT License. See [CREDITS.md](CREDITS.md) for
the project inspiration and attribution boundary.
