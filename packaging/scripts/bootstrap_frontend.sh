#!/bin/sh
set -eu

ROOT="${SIRI_PROJECT_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
FRONTEND_DIR="$ROOT/frontend"
LOG_DIR="${OPENJARVIS_LAUNCHER_DIR:-$HOME/.openjarvis/launcher}"
PID_FILE="$LOG_DIR/frontend.pid"
LOG_FILE="$LOG_DIR/frontend.log"

mkdir -p "$LOG_DIR"

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "frontend directory missing: $FRONTEND_DIR" >&2
  exit 1
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "frontend already running pid=$(cat "$PID_FILE")"
  exit 0
fi

cd "$FRONTEND_DIR"
nohup npm run dev -- --host 127.0.0.1 >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
echo "frontend started pid=$(cat "$PID_FILE") log=$LOG_FILE"
