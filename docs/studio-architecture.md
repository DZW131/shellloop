# Shellloop Studio architecture

Shellloop Studio separates three responsibilities that are often blurred in a
beginner Agent project:

```text
Browser UI and model API  →  local Studio process
Generated shell commands →  disposable Docker session
Approved Harness update  →  active project configuration
```

The separation keeps the Agent useful without granting it hidden host access.

## Runtime Observatory

`DefaultAgent` is the single source of lifecycle facts. It emits safe events
before and after observable control-flow boundaries:

```text
run_started → model_request → model_response → action_selected
→ command_finished → run_finished
```

The event payload contains a step, a short summary, a bounded command preview,
and selected execution metadata such as return code and completion status. It
does not contain task text, API keys, environment variables, model transcripts,
or command output bodies.

The Studio server augments events with sequence number and timestamp, streams
them with Server-Sent Events, and saves them with the trajectory. The Runtime
Observatory page uses that stream for its timeline and state cards.

## Sandbox boundary

Before a run, `create_session_workspace()` copies the source workspace into an
artifact-owned session. `DockerEnvironment` mounts only that copy at
`/workspace` and runs one command with:

- no command network;
- a read-only container base layer and writable `/workspace` session mount;
- a small writable `/tmp`;
- dropped Linux capabilities and `no-new-privileges`;
- CPU, memory, process-count, and command-time limits.

No Docker executable means no command execution. Studio can still show its
configuration and generate a proposal preview, but it cannot start or verify a
candidate run.

## Evolution Workbench

The natural-language improvement request is sent to the selected real model
API with a JSON-only contract. The only accepted update keys are:

```text
system_prompt
max_steps
timeout
```

`HarnessProposal` retains a current spec and a candidate spec in memory. It
does not retain the request text or API key. Verification writes the candidate
configuration only into a fresh Docker session and runs the project's test
command there. A non-zero result disables application.

When a user explicitly presses **批准并应用**, Studio saves the old
`harness.yaml` into `artifacts/studio/harness-history/` and writes the verified
candidate to the active project. The Agent never calls this operation itself.

## Extension rule

Future capabilities—tool policies, additional images, browser tools, memory,
multi-Agent orchestration, or code-level evolution—should extend this model in
three steps:

1. define a small, versioned configuration or capability contract;
2. expose its proposal, runtime evidence, and verification in Studio;
3. require explicit user approval before it reaches the active Harness.

Do not treat a new feature as a reason to add an unrestricted host-shell
fallback.
