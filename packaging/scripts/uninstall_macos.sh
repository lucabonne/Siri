#!/bin/sh
set -eu

ROOT="${SIRI_PROJECT_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
DESTINATION="all"
REMOVE_LAUNCH_AGENT=1
PYTHON_BIN="${PYTHON:-python3}"
PLIST="$HOME/Library/LaunchAgents/com.openjarvis.siri.plist"

run_cli() {
  if command -v uv >/dev/null 2>&1; then
    PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" uv run python "$ROOT/packaging/scripts/package_app.py" "$@"
  else
    PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" "$ROOT/packaging/scripts/package_app.py" "$@"
  fi
}

usage() {
  echo "usage: $0 [--user|--system|--all] [--keep-launch-agent]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --user)
      DESTINATION="user"
      ;;
    --system)
      DESTINATION="system"
      ;;
    --all)
      DESTINATION="all"
      ;;
    --keep-launch-agent)
      REMOVE_LAUNCH_AGENT=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
  shift
done

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Siri.app uninstaller is macOS-only." >&2
  exit 1
fi

if [ "$REMOVE_LAUNCH_AGENT" -eq 1 ] && command -v launchctl >/dev/null 2>&1 && [ -f "$PLIST" ]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
fi

cd "$ROOT"

if [ "$REMOVE_LAUNCH_AGENT" -eq 1 ]; then
  run_cli uninstall --destination "$DESTINATION"
else
  run_cli uninstall --destination "$DESTINATION" --keep-launch-agent
fi
