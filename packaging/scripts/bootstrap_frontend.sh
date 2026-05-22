#!/bin/sh
set -eu

ROOT="${SIRI_PROJECT_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
FRONTEND_DIR="$ROOT/frontend"
STATIC_DIR="${OPENJARVIS_FRONTEND_STATIC_DIR:-$ROOT/src/openjarvis/server/static}"
LOG_DIR="${OPENJARVIS_LAUNCHER_DIR:-$HOME/.openjarvis/launcher}"
PID_FILE="$LOG_DIR/frontend.pid"
LOG_FILE="$LOG_DIR/frontend.log"
ERR_FILE="$LOG_DIR/frontend.err.log"
FRONTEND_HOST="${OPENJARVIS_FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${OPENJARVIS_FRONTEND_PORT:-5173}"

mkdir -p "$LOG_DIR"

if [ ! -d "$FRONTEND_DIR" ] && [ ! -f "$STATIC_DIR/index.html" ]; then
  echo "frontend directory missing: $FRONTEND_DIR" >&2
  exit 1
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "frontend already running pid=$(cat "$PID_FILE")"
  exit 0
fi

if [ -n "${OPENJARVIS_PYTHON:-}" ] && [ -x "$OPENJARVIS_PYTHON" ]; then
  PYTHON_BIN="$OPENJARVIS_PYTHON"
elif [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/.venv/bin/python3" ]; then
  PYTHON_BIN="$ROOT/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "frontend launcher could not find a Python executable. Tried OPENJARVIS_PYTHON, $ROOT/.venv/bin/python, $ROOT/.venv/bin/python3, and python3." >&2
  exit 127
fi

if [ -f "$STATIC_DIR/index.html" ]; then
  cd "$ROOT"
  {
    echo "frontend command: $PYTHON_BIN -m openjarvis.packaging.static_frontend --host $FRONTEND_HOST --port $FRONTEND_PORT --directory $STATIC_DIR"
    echo "started at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } >>"$LOG_FILE"
  nohup sh -c "PYTHONPATH=\"$ROOT/src${PYTHONPATH:+:$PYTHONPATH}\" \"$PYTHON_BIN\" -m openjarvis.packaging.static_frontend --host \"$FRONTEND_HOST\" --port \"$FRONTEND_PORT\" --directory \"$STATIC_DIR\"" >>"$LOG_FILE" 2>>"$ERR_FILE" &
else
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required when built static frontend assets are missing." >&2
    exit 127
  fi
  cd "$FRONTEND_DIR"
  nohup npm run dev -- --host "$FRONTEND_HOST" >>"$LOG_FILE" 2>>"$ERR_FILE" &
fi
echo $! >"$PID_FILE"
echo "frontend started pid=$(cat "$PID_FILE") log=$LOG_FILE err=$ERR_FILE"
