#!/bin/sh
set -eu

ROOT="${SIRI_PROJECT_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
LOG_DIR="${OPENJARVIS_LAUNCHER_DIR:-$HOME/.openjarvis/launcher}"
BACKEND_PID="$LOG_DIR/backend.pid"
FRONTEND_PID="$LOG_DIR/frontend.pid"
BACKEND_HEALTH="${OPENJARVIS_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
FRONTEND_HEALTH="${OPENJARVIS_FRONTEND_URL:-http://127.0.0.1:5173}"

mkdir -p "$LOG_DIR"

running() {
  pid_file="$1"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

health() {
  label="$1"
  url="$2"
  if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "$url" >/dev/null 2>&1; then
    echo "$label=healthy $url"
  else
    echo "$label=unavailable $url"
  fi
}

start_backend() {
  "$ROOT/packaging/scripts/bootstrap_backend.sh"
}

start_frontend() {
  "$ROOT/packaging/scripts/bootstrap_frontend.sh"
}

stop_pid() {
  pid_file="$1"
  label="$2"
  if running "$pid_file"; then
    kill "$(cat "$pid_file")" 2>/dev/null || true
    echo "$label stopped pid=$(cat "$pid_file")"
  else
    echo "$label not running"
  fi
}

status() {
  if running "$BACKEND_PID"; then
    echo "backend=running pid=$(cat "$BACKEND_PID")"
  else
    echo "backend=stopped"
  fi
  if running "$FRONTEND_PID"; then
    echo "frontend=running pid=$(cat "$FRONTEND_PID")"
  else
    echo "frontend=stopped"
  fi
  echo "local_only=true telemetry_enabled=false"
}

diagnostics() {
  status
  health backend "$BACKEND_HEALTH"
  health frontend "$FRONTEND_HEALTH"
  [ -f "$ROOT/packaging/config/app_metadata.json" ] && echo "metadata=ok" || echo "metadata=missing"
  [ -d "$ROOT/frontend" ] && echo "frontend_directory=ok" || echo "frontend_directory=missing"
}

open_frontend() {
  if [ "$(uname -s)" = "Darwin" ] && command -v open >/dev/null 2>&1; then
    open "$FRONTEND_HEALTH" >/dev/null 2>&1 || true
  fi
}

case "${1:-launch}" in
  launch|start)
    start_backend
    start_frontend
    open_frontend
    status
    ;;
  backend)
    start_backend
    ;;
  frontend)
    start_frontend
    ;;
  restart)
    stop_pid "$BACKEND_PID" backend
    stop_pid "$FRONTEND_PID" frontend
    start_backend
    start_frontend
    open_frontend
    status
    ;;
  stop)
    stop_pid "$BACKEND_PID" backend
    stop_pid "$FRONTEND_PID" frontend
    ;;
  status)
    status
    ;;
  diagnostics)
    diagnostics
    ;;
  *)
    echo "usage: $0 {launch|start|backend|frontend|restart|stop|status|diagnostics}" >&2
    exit 2
    ;;
esac
