#!/bin/sh
set -eu

ROOT="${SIRI_PROJECT_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
LOG_DIR="${OPENJARVIS_LAUNCHER_DIR:-$HOME/.openjarvis/launcher}"
PID_FILE="$LOG_DIR/backend.pid"
LOG_FILE="$LOG_DIR/backend.log"
ERR_FILE="$LOG_DIR/backend.err.log"

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "backend already running pid=$(cat "$PID_FILE")"
  exit 0
fi

if [ -n "${OPENJARVIS_BACKEND_COMMAND:-}" ]; then
  BACKEND_CMD="$OPENJARVIS_BACKEND_COMMAND"
elif [ -n "${OPENJARVIS_PYTHON:-}" ] && [ -x "$OPENJARVIS_PYTHON" ]; then
  BACKEND_CMD="\"$OPENJARVIS_PYTHON\" -m openjarvis.packaging.local_backend --host 127.0.0.1"
elif [ -x "$ROOT/.venv/bin/python" ]; then
  BACKEND_CMD="\"$ROOT/.venv/bin/python\" -m openjarvis.packaging.local_backend --host 127.0.0.1"
elif [ -x "$ROOT/.venv/bin/python3" ]; then
  BACKEND_CMD="\"$ROOT/.venv/bin/python3\" -m openjarvis.packaging.local_backend --host 127.0.0.1"
elif command -v uv >/dev/null 2>&1; then
  BACKEND_CMD="uv run python -m openjarvis.packaging.local_backend --host 127.0.0.1"
elif command -v python3 >/dev/null 2>&1; then
  BACKEND_CMD="python3 -m openjarvis.packaging.local_backend --host 127.0.0.1"
else
  echo "backend launcher could not find a Python executable. Tried OPENJARVIS_PYTHON, $ROOT/.venv/bin/python, $ROOT/.venv/bin/python3, uv run, and python3." >&2
  exit 127
fi

cd "$ROOT"
{
  echo "backend command: $BACKEND_CMD"
  echo "project root: $ROOT"
  echo "started at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} >>"$LOG_FILE"
nohup sh -c "PYTHONPATH=\"$ROOT/src${PYTHONPATH:+:$PYTHONPATH}\" $BACKEND_CMD" >>"$LOG_FILE" 2>>"$ERR_FILE" &
echo $! >"$PID_FILE"
echo "backend started pid=$(cat "$PID_FILE") log=$LOG_FILE err=$ERR_FILE"
