# Shellloop Studio v0.5 delivery

## Delivered outcome

Harness evolution now has a repeatable, reversible evidence loop:

```text
Natural-language change
→ constrained candidate
→ Docker project tests
→ checked multi-case A/B evaluation with live events
→ explicit user approval
→ fingerprinted version
→ guarded restore candidate when needed
```

The default `evaluations.yaml` contains three deterministic teaching cases:
exact file creation, project-fact inspection, and a small Python change. Agent
completion and task-check success are separate facts. Current and candidate
runs use independent temporary workspaces that are removed after every case.

## Version governance

- Each active Harness has an id, UTC timestamp, source, parent id, content
  fingerprint, and credential-free spec.
- Direct edits to `harness.yaml` are detected and recorded as external versions.
- Applying a stale proposal is refused instead of overwriting a newer Harness.
- Restore never writes immediately; it creates a candidate that must pass the
  Docker test gate and receive a new user approval.
- Version metadata remains local under `artifacts/studio/harness-versions/`.
- Launchers open preview-only Studio when Docker, its engine, or the sandbox
  image is unavailable; execution never falls back to the host shell.

## Validation completed

```text
python -m pytest -q                 101 passed
python -m ruff check src tests      passed
python -m ruff format --check ...   passed
node --check runtime.js             passed
node --check evolution.js           passed
Edge headless render, evolution UI  passed at 1440 px
start.ps1 without Docker            preview-only API passed
git diff --check                    passed
```

## Environment-dependent check remaining

Docker is unavailable on the development machine, so the three real evaluation
cases and a paid-model comparison were not executed end to end here. Automated
tests cover suite validation, deterministic-check scoring, aggregation,
request-scoped task privacy, background comparison state, version activation,
external-edit detection, stale-proposal rejection, guarded restore, Studio API
routes, and rendered page structure. A release operator should still run the
default suite with Docker and their own API key before tagging v0.5. The Unix
launcher was reviewed but could not be executed here because this Windows host
does not have a WSL distribution.
