# Shellloop Studio

Shellloop Studio is a local-first, observable and evolvable Agent Harness for
beginners. A learner can describe a task or an improvement in natural language,
watch the Agent's factual runtime events, and approve a tested Harness update
without handing an AI unrestricted control of their computer.

```text
natural-language task → Plan → Act → Observe → Verify → live evidence
natural-language improvement → candidate workflow → tests + A/B evidence → user approval
```

## What makes it different

- **Low entry barrier** — double-click `start.bat` on Windows or run
  `./start.sh` on macOS/Linux. The local browser UI asks for a model, API base,
  API key, and task.
- **Two complementary views** — Runtime Observatory follows one Agent run in
  detail; Evolution Workbench explains what a Harness revision changes and why.
- **Real APIs only** — Shellloop no longer exposes an offline scripted model.
  It supports Ollama Cloud and OpenAI-compatible chat APIs.
- **Host protection by default** — generated commands run only in a disposable
  Docker session copy. The container has no network, a read-only base layer,
  dropped Linux capabilities, CPU/memory/process limits, and only the session
  directory mounted writable.
- **Constrained self-improvement** — proposals can change the instruction,
  step/time bounds, visible planning, verification, and retry behavior. A model
  can reshape the explicit workflow but cannot write the active Harness
  directly.
- **Evidence before change** — the candidate is verified in Docker. Only after
  a passing test gate can it be approved. An optional same-task A/B run compares
  the current and candidate Harness using success, steps, failed commands,
  verification count, and duration. The previous config is preserved under
  `artifacts/studio/harness-history/`.

Shellloop reports observable execution facts, not hidden model reasoning. It
does not display API keys, environment variables, full model transcripts, or
tool-output bodies in its teaching trace.

## Quick start

### Prerequisites

1. Python 3.10 or newer.
2. Docker Desktop (Windows/macOS) or Docker Engine (Linux), running locally.
3. An Ollama Cloud API key or an OpenAI-compatible API key.

Docker is a deliberate requirement: if it is unavailable, Studio stays in
preview-only mode and the CLI refuses to execute a model command on the host.

### Windows

Clone or download the repository, then double-click `start.bat`. On first run
it creates `.venv`, installs Python dependencies, builds
`shellloop-sandbox:0.4`, and opens:

```text
http://127.0.0.1:8765
```

### macOS and Linux

```bash
chmod +x start.sh
./start.sh
```

The start scripts bind the Studio to `127.0.0.1`, not to a public network
interface. Stop the Studio with `Ctrl+C` in its terminal.

## Studio workflow

### 1. Runtime Observatory

Open **运行观测台** and enter a provider, API base, model, API key, and task.
The key is submitted only for that request; Shellloop never writes it to YAML,
the trajectory, browser storage, or Git.

The live timeline shows these state changes:

```text
sandbox_prepared
run_started
model_request
model_response
action_selected
command_finished
verification_started
verification_finished
run_finished
```

This answers classroom questions such as:

- Has the model actually been called?
- Did its response contain exactly one executable action?
- Which command was selected by the Harness?
- Did the sandbox finish it, fail it, or time out?
- Did verification pass, and was a bounded repair attempt needed?
- Why did the Agent stop?

The page separates Agent control, model interaction, sandbox execution, and
verification into phase lanes. It also shows the active Harness workflow and
safe metrics without claiming to expose a model's hidden chain of thought.

### 2. Evolution Workbench

Open **演化工作台** and ask for a specific improvement, for example:

> Make the system prompt explain its visible plan to beginners and reduce the
> step limit to avoid endless loops.

The model must return a constrained JSON proposal. Studio displays both field
changes and the resulting workflow graph. It cannot return arbitrary file
edits, credentials, or new capabilities.

Click **在 Docker 中验证** to run the existing Python tests in a disposable
candidate workspace. After a green result, **批准并应用** becomes available.
That confirmation is the only route that writes the new `harness.yaml` to the
active project; the old configuration is saved in history first.

Before approval, enter a private evaluation task and click **运行当前版与候选版**
to gather same-task A/B evidence. Those evaluation workspaces are deleted when
the comparison finishes, and the task is not written to the proposal history.
One stochastic comparison is evidence rather than proof, so important changes
should be repeated on several representative tasks.

## Harness configuration

[`harness.yaml`](harness.yaml) is deliberately small and versionable:

```yaml
system_prompt: A visible, beginner-friendly Agent instruction
max_steps: 8
timeout: 30
visible_planning: true
verification_enabled: true
verification_command: python -m pytest -q
verification_retries: 1
```

There are no provider credentials in this file. The narrow configuration
surface is intentional: beginners can understand a proposed change, observe
its consequence, and roll it back. Later versions can add capabilities through
new explicit, tested fields rather than granting a model unconstrained host
access.

## Command line

The Studio is the recommended interface:

```bash
shellloop studio
```

For scripted API-backed runs, build the sandbox image first and configure a
key in the environment:

```powershell
docker build -t shellloop-sandbox:0.4 -f Dockerfile.sandbox .
$env:OLLAMA_API_KEY = "your_api_key"
shellloop --provider ollama-cloud --api-base https://ollama.com/api --model gpt-oss:120b-cloud --task "List project files and finish correctly" --output artifacts/run.traj.json
```

For an OpenAI-compatible endpoint, use `--provider openai-compatible`, set
`OPENAI_API_KEY`, and provide its `/v1` base with `--api-base`.

After a run, inspect safe aggregate data without executing anything from the
trajectory:

```bash
shellloop inspect artifacts/run.traj.json
```

## Security model and limits

Docker isolation substantially reduces host impact; it is not a substitute for
reviewing an Agent's behavior. Do not mount valuable host data into the Studio
workspace or enter secrets in a task. The first sandbox image disables command
network access, but Studio itself needs network access to call the model API.

Future capability expansion should be explicit and observable: an approved
image, a read-only data mount, package-cache access, or a reviewed tool policy.
Never implement expansion as a silent fallback to unrestricted host execution.

## Development

```bash
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
```

## Repository structure

```text
src/shellloop/
  agents/          Observable Agent control loop
  environments/    Docker-only product execution environment
  harness.py       User-approvable Harness configuration
  evaluation.py    Privacy-preserving run metrics and A/B conclusions
  proposals.py     Constrained natural-language change proposals
  studio.py        Local API and server-sent event service
  studio_static/   Runtime Observatory and Evolution Workbench pages
  tracing.py       Safe lifecycle event formatting
  models/          Real API model adapters
tests/             Offline unit, CLI, sandbox, proposal, and Studio tests
Dockerfile.sandbox Isolated command-runner image
harness.yaml       Active, versionable Harness configuration
```

## Roadmap

1. Current: local Studio, phased factual runtime trace, Docker sessions,
   constrained workflow proposals, verification/retry behavior, same-task A/B
   evidence, and user approval.
2. Next: reusable evaluation suites, repeated comparisons, replay, and
   configurable safe tool policies.
3. Later: explicit capability packs for planning, memory, browser tools,
   multiple agents, and broader code evolution — each introduced as a visible,
   tested, reversible Harness capability.

## License and credits

Shellloop is released under the MIT License. See [CREDITS.md](CREDITS.md) for
the project inspiration and attribution boundary.
