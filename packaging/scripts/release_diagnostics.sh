#!/bin/sh
set -eu

ROOT="${SIRI_PROJECT_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
PYTHON_BIN="${PYTHON:-python3}"

cd "$ROOT"
if command -v uv >/dev/null 2>&1; then
  PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" uv run python "$ROOT/packaging/scripts/package_app.py" release-diagnostics
else
  PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" "$ROOT/packaging/scripts/package_app.py" release-diagnostics
fi
