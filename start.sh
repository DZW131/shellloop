#!/usr/bin/env sh

set -eu

task_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_python="$task_root/.venv/bin/python"

cd "$task_root"

if [ ! -x "$task_python" ]; then
  python3 -m venv .venv
fi

"$task_python" -c "import shellloop, typer, yaml" >/dev/null 2>&1 || "$task_python" -m pip install -e '.[dev]'
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker build -t shellloop-sandbox:0.5 -f Dockerfile.sandbox . || echo "Sandbox build failed; Studio will start in preview-only mode." >&2
else
  echo "Docker Engine is unavailable; Studio will start in preview-only mode." >&2
fi
exec "$task_python" -m shellloop studio
