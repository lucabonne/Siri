# Release Candidate Validation Checklist

This checklist is intended to be used when preparing a new Release Candidate for Siri / OpenJarvis on macOS.

## Automated Validation

- [ ] Run `bash packaging/scripts/validate_release.sh`
- [ ] Verify that all checks return `PASS`.
- [ ] If any check returns `FAIL`, consult the printed troubleshooting hints, fix the issue, and re-run the script.

## Manual Smoke Tests

### 1. Build the App
- [ ] Run `python3 packaging/scripts/package_app.py` or `jarvis package build` to generate the `.app` bundle.
- [ ] Verify that `build/packaging/Siri.app` is created.

### 2. Install the App
- [ ] Run `bash packaging/scripts/install_macos.sh`.
- [ ] Verify the application is copied to `~/Applications/Siri.app`.
- [ ] Verify the LaunchAgent plist is installed to `~/Library/LaunchAgents/com.openjarvis.siri.plist`.

### 3. Launch and Verify
- [ ] Start Siri from `~/Applications/Siri.app` via Finder, Spotlight, or Launchpad.
- [ ] Verify the Siri icon appears in the macOS menu bar (Tray).
- [ ] Open **Mission Control** from the menu bar.
- [ ] Check the **Release Health** panel in Mission Control. Verify the Readiness Score is acceptable (ideally 100).
- [ ] Ensure `Privacy` and `Scope` indicators show local-only, no telemetry, no wake words, and no autonomous agents are active.

### 4. Basic Functionality
- [ ] Verify the backend API is reachable.
- [ ] Open the **Settings** / **Startup** tab in Mission Control and verify that LaunchAgent status shows as `Installed`.
- [ ] Submit a single manual request via Mission Control or Push-to-Talk and verify that a response is received without errors.

### 5. Uninstall the App
- [ ] Run `bash packaging/scripts/uninstall_macos.sh`.
- [ ] Verify the application is removed from `~/Applications/Siri.app`.
- [ ] Verify the LaunchAgent plist is removed and unloaded.

## Privacy & Safety Assertions
- [ ] **No Autonomy:** Siri must not take autonomous actions. All workflows and tool calls must require explicit user invocation.
- [ ] **No Wake Word:** The microphone must not be continuously listening for a wake word by default.
- [ ] **No Cloud Analytics:** Telemetry, remote tracking, and automatic cloud crash reporting must remain disabled.
- [ ] **No External Code Mutation:** No agent is allowed to autonomously modify source code, configuration files, or external repositories without explicit confirmation.
