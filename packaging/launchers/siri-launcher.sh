#!/bin/sh
set -eu

ROOT="${SIRI_PROJECT_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
PACKAGING_ROOT="${SIRI_PACKAGING_ROOT:-$ROOT/packaging}"
LOG_DIR="${OPENJARVIS_LAUNCHER_DIR:-$HOME/.openjarvis/launcher}"
BACKEND_PID="$LOG_DIR/backend.pid"
FRONTEND_PID="$LOG_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
BACKEND_ERR="$LOG_DIR/backend.err.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_HEALTH="${OPENJARVIS_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
FRONTEND_HEALTH="${OPENJARVIS_FRONTEND_URL:-http://127.0.0.1:5173}"
BACKEND_HEALTH_TIMEOUT="${OPENJARVIS_BACKEND_HEALTH_TIMEOUT:-120}"
FRONTEND_HEALTH_TIMEOUT="${OPENJARVIS_FRONTEND_HEALTH_TIMEOUT:-180}"

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

wait_for_health() {
  label="$1"
  url="$2"
  timeout="$3"
  started="$(date +%s)"
  while :; do
    if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "$url" >/dev/null 2>&1; then
      elapsed="$(($(date +%s) - started))"
      echo "$label=healthy url=$url elapsed=${elapsed}s"
      return 0
    fi
    elapsed="$(($(date +%s) - started))"
    if [ "$elapsed" -ge "$timeout" ]; then
      echo "$label=unhealthy url=$url timeout=${timeout}s"
      return 1
    fi
    sleep 1
  done
}

tail_file() {
  file="$1"
  label="$2"
  if [ -f "$file" ]; then
    echo "$label tail:"
    tail -40 "$file" || true
  else
    echo "$label missing: $file"
  fi
}

backend_diagnostics() {
  if running "$BACKEND_PID"; then
    echo "backend_process=running pid=$(cat "$BACKEND_PID")"
  else
    echo "backend_process=stopped"
  fi
  tail_file "$BACKEND_LOG" backend_log
  tail_file "$BACKEND_ERR" backend_error_log
}

start_backend() {
  /bin/bash "$PACKAGING_ROOT/scripts/bootstrap_backend.sh"
}

start_frontend() {
  /bin/bash "$PACKAGING_ROOT/scripts/bootstrap_frontend.sh"
}

stop_pid() {
  pid_file="$1"
  label="$2"
  if running "$pid_file"; then
    kill "$(cat "$pid_file")" 2>/dev/null || true
    sleep 1
    if running "$pid_file"; then
      kill -9 "$(cat "$pid_file")" 2>/dev/null || true
    fi
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
  backend_diagnostics
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
    backend_ready=0
    wait_for_health backend "$BACKEND_HEALTH" "$BACKEND_HEALTH_TIMEOUT" || backend_ready=1
    if [ "${OPENJARVIS_SKIP_FRONTEND:-0}" != "1" ]; then
      start_frontend
      wait_for_health frontend "$FRONTEND_HEALTH" "$FRONTEND_HEALTH_TIMEOUT" || true
    fi
    open_frontend
    status
    if [ "$backend_ready" -ne 0 ]; then
      backend_diagnostics
      exit 1
    fi
    ;;
  backend)
    start_backend
    wait_for_health backend "$BACKEND_HEALTH" "$BACKEND_HEALTH_TIMEOUT" || {
      backend_diagnostics
      exit 1
    }
    ;;
  frontend)
    start_frontend
    ;;
  restart)
    stop_pid "$BACKEND_PID" backend
    stop_pid "$FRONTEND_PID" frontend
    start_backend
    backend_ready=0
    wait_for_health backend "$BACKEND_HEALTH" "$BACKEND_HEALTH_TIMEOUT" || backend_ready=1
    start_frontend
    wait_for_health frontend "$FRONTEND_HEALTH" "$FRONTEND_HEALTH_TIMEOUT" || true
    open_frontend
    status
    if [ "$backend_ready" -ne 0 ]; then
      backend_diagnostics
      exit 1
    fi
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
