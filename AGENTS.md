# Shellloop Project Contract

Shellloop is an independently implemented teaching project inspired by the
minimal architecture of mini-SWE-agent.

## Scope

- Python 3.10+
- One Shell action per model response
- Local workspace execution
- JSON trajectories
- YAML configuration and a CLI
- An offline scripted model

## Non-goals

- Do not copy upstream source code verbatim.
- Do not add model providers, container backends, benchmarks, or a UI unless an
  issue explicitly asks for them.
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
