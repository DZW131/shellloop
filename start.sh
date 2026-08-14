#!/usr/bin/env sh

set -eu

task_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_python="$task_root/.venv/bin/python"

cd "$task_root"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Shellloop never runs Agent commands on the host shell." >&2
  exit 1
fi

if [ ! -x "$task_python" ]; then
  python3 -m venv .venv
fi

"$task_python" -c "import shellloop, typer, yaml" >/dev/null 2>&1 || "$task_python" -m pip install -e '.[dev]'
docker build -t shellloop-sandbox:0.4 -f Dockerfile.sandbox .
exec "$task_python" -m shellloop studio
