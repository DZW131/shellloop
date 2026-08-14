# Shellloop Project Contract

Shellloop is an independently implemented teaching project inspired by the
minimal architecture of mini-SWE-agent.

## Scope

- Python 3.10+
- One Shell action per model response
- Local workspace execution
- JSON trajectories
- YAML configuration and a CLI
- Real API-backed models and a local Studio web workbench
- Docker-isolated Agent command execution and approved Harness configuration evolution

## Non-goals

- Do not copy upstream source code verbatim.
- Keep Studio local-only by default and bind only to 127.0.0.1.
- Run model-generated commands only in the disposable Docker workspace; never
  silently fall back to a host shell.
- Keep Harness evolution constrained, tested, visible, and user-approved.
- Do not add dependencies without approval.
- Do not print or save secrets.
- Do not run destructive commands or commands outside the configured workspace.

## Workflow

1. Read the assigned issue and relevant files.
2. State a concise implementation plan before editing.
3. Make the smallest change that satisfies the issue.
4. Add or update tests.
5. Run the planned checks.
6. Report changed files, test results, and remaining risks.

Ask before changing a public interface, adding a dependency, copying upstream
code, or expanding scope.
