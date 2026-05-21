#!/bin/sh
set -eu

ROOT="${SIRI_PROJECT_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
LOG_DIR="${OPENJARVIS_LAUNCHER_DIR:-$HOME/.openjarvis/launcher}"
PID_FILE="$LOG_DIR/backend.pid"
LOG_FILE="$LOG_DIR/backend.log"

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "backend already running pid=$(cat "$PID_FILE")"
  exit 0
fi

if command -v jarvis >/dev/null 2>&1; then
  BACKEND_CMD="jarvis serve"
else
  BACKEND_CMD="PYTHONPATH=\"$ROOT/src${PYTHONPATH:+:$PYTHONPATH}\" python -m openjarvis.cli serve"
fi

cd "$ROOT"
nohup sh -c "$BACKEND_CMD" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
echo "backend started pid=$(cat "$PID_FILE") log=$LOG_FILE"
