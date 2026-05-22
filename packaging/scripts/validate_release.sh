#!/usr/bin/env bash
set -euo pipefail

# Release Candidate Local Validation Script
# Usage: bash packaging/scripts/validate_release.sh

cd "$(dirname "$0")/../.."
PROJECT_ROOT="$(pwd)"
FAILED=0

print_header() {
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

print_pass() {
    echo -e "[\033[32mPASS\033[0m] $1"
}

print_fail() {
    echo -e "[\033[31mFAIL\033[0m] $1"
    if [ -n "${2:-}" ]; then
        echo -e "       \033[33mHint:\033[0m $2"
    fi
    FAILED=1
}

print_header "Running Release Validation Checks"

# 1. Frontend build
if [ -f "src/openjarvis/server/static/index.html" ]; then
    print_pass "Frontend build (static assets exist)"
else
    print_fail "Frontend build missing" "Run 'npm run build' in the frontend directory."
fi

# 2. Backend import
if uv run python3 -c "import openjarvis" 2>/dev/null; then
    print_pass "Backend import (openjarvis module loads)"
else
    print_fail "Backend import failed" "Ensure dependencies are installed with 'uv sync' or that the venv is valid."
fi

# 3. Packaging diagnostics
echo "Running packaging diagnostics..."
if uv run python3 -m openjarvis.cli package release-diagnostics > /dev/null 2>&1; then
    print_pass "Packaging diagnostics (command succeeds)"
else
    print_fail "Packaging diagnostics failed" "Run 'uv run python3 -m openjarvis.cli package release-diagnostics' to view detailed errors."
fi

# 4. App bundle exists or can build
# Checking if the bundle is already built, or if the package_app.py script exists to build it.
if [ -d "build/packaging/Siri.app" ]; then
    print_pass "App bundle (Siri.app exists)"
elif [ -f "packaging/scripts/package_app.py" ]; then
    print_pass "App bundle (build script exists; app not yet built)"
else
    print_fail "App bundle or build script missing" "Ensure packaging/scripts/package_app.py exists and is executable."
fi

# 5. Installer script exists
if [ -f "packaging/scripts/install_macos.sh" ]; then
    print_pass "Installer script exists"
else
    print_fail "Installer script missing" "Ensure packaging/scripts/install_macos.sh is present."
fi

# 6. Uninstaller script exists
if [ -f "packaging/scripts/uninstall_macos.sh" ]; then
    print_pass "Uninstaller script exists"
else
    print_fail "Uninstaller script missing" "Ensure packaging/scripts/uninstall_macos.sh is present."
fi

# 7. LaunchAgent plist generation
if uv run python3 -c "from openjarvis.startup.launchagent import LaunchAgentManager; LaunchAgentManager().status()" > /dev/null 2>&1; then
    print_pass "LaunchAgent plist generation (LaunchAgentManager available)"
else
    print_fail "LaunchAgent plist generation failed" "Run 'uv run python3 -c \"from openjarvis.startup.launchagent import LaunchAgentManager; print(LaunchAgentManager().status())\"' to debug."
fi

# 8. ffmpeg availability
if command -v ffmpeg >/dev/null 2>&1; then
    print_pass "ffmpeg availability"
else
    print_fail "ffmpeg missing" "Install ffmpeg via Homebrew: 'brew install ffmpeg'"
fi

# 9. Ollama availability
if command -v ollama >/dev/null 2>&1; then
    print_pass "Ollama availability"
else
    print_fail "Ollama missing" "Install Ollama from https://ollama.com/download"
fi

# 10. Mission Control static frontend available
if [ -f "src/openjarvis/server/static/index.html" ]; then
    print_pass "Mission Control static frontend available"
else
    print_fail "Mission Control static frontend missing" "Run 'npm run build' in the frontend directory."
fi

print_header "Validation Summary"
if [ $FAILED -eq 0 ]; then
    echo -e "[\033[32mSUCCESS\033[0m] All release validation checks passed."
    exit 0
else
    echo -e "[\033[31mFAILURE\033[0m] One or more release validation checks failed. See hints above."
    exit 1
fi
