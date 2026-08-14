# Shellloop Studio v0.4 delivery

## Delivered outcome

Shellloop now teaches both how an Agent run proceeds and how a constrained
Harness change affects that process. The active workflow is executable rather
than decorative:

```text
Understand → optional visible Plan → Act → Observe
           → optional Verify → bounded Retry → Finish
```

The Runtime Observatory groups factual events into Agent, model, sandbox, and
verification phases. The Evolution Workbench shows field diffs, before/after
workflow graphs, deterministic test-gate evidence, and optional real same-task
A/B evidence before the user decides whether to apply a proposal.

## Safety and portability evidence

- Agent commands run only in `shellloop-sandbox:0.4` with no network, a
  read-only base filesystem, dropped capabilities, process/memory/CPU limits,
  and a writable disposable project copy.
- Missing Docker means preview-only Studio behavior and refused CLI execution;
  there is no host-shell fallback.
- API keys remain request-scoped and are not written to Harness configuration,
  browser storage, trajectory configuration, proposal history, or Git.
- Proposal verification runs in an isolated candidate copy. Same-task A/B
  workspaces are deleted immediately after evaluation.
- A candidate can reach `harness.yaml` only after the test gate passes and the
  user explicitly approves it. The previous version is archived first.

## Validation completed

```text
python -m pytest -q                 89 passed
python -m ruff check src tests      passed
python -m ruff format --check ...   passed
node --check runtime.js             passed
node --check evolution.js           passed
Edge headless render, both pages    passed at 1440 px
git diff --check                    passed
```

## Environment-dependent check remaining

This development machine does not have Docker available, so a live container
run and a live paid-model API run could not be executed here. The Docker command
construction, refusal path, Studio endpoints, event stream data, workflow
comparison, redaction, temporary evaluation cleanup, and approval gate are
covered by automated tests. A release operator should still run one end-to-end
task on a machine with Docker and their own API key before tagging a release.
