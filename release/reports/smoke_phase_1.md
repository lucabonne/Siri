# Release Smoke Phase 1

Date: 2026-05-22
Branch: `siri-release-smoke-phase-1`
Scope: Validate Siri as an installable local macOS application.

## Current Result

PASS after Release Smoke Fix Phase 1.

Siri now builds, installs, launches from `~/Applications/Siri.app`, starts a
healthy local backend, serves the local frontend, exposes Mission Control, and
loads the release status surfaces needed for Phase 1 validation.

No new features, wake word behavior, or autonomous behavior were added.

## Fix Summary

- Backend launch no longer assumes `python`; it prefers the project venv,
  then `uv run`, then `python3`.
- The installed app now runs bundled launcher/bootstrap scripts from
  `Siri.app/Contents/Resources/packaging` instead of executing shell scripts
  directly from the source checkout.
- The LaunchAgent plist now invokes `/bin/bash` with the installed app
  executable and validates ownership, permissions, and executable paths.
- Backend launch now logs stdout/stderr separately, waits for health, and
  prints log tails on timeout.
- The installed release backend exposes local-only status endpoints without
  model execution, wake words, or autonomous behavior.
- The frontend bootstrap now serves built static assets with SPA fallback
  instead of relying on Vite dev-server dependency scanning.
- `ffmpeg` is detected at `/opt/homebrew/bin/ffmpeg`.

## Smoke Matrix

| Check | Result | Evidence |
| --- | --- | --- |
| Build `Siri.app` using packaging flow | PASS | `uv run python packaging/scripts/build_app_bundle.py` completed in 0.22s. |
| Install locally with `install_macos.sh` | PASS | Installed `~/Applications/Siri.app`; LaunchAgent valid. |
| Launch from installed location | PASS | `open ~/Applications/Siri.app` started backend and frontend processes. |
| Backend starts | PASS | `/health` returned HTTP 200; backend ready in 3s on final smoke. |
| Frontend opens | PASS | `http://127.0.0.1:5173/` returned built HTML. |
| Mission Control loads | PASS | `http://127.0.0.1:5173/mission-control` returned built HTML through SPA fallback. |
| Memory loads | PASS | `/v1/memory/stats` returned HTTP 200. |
| Packaging status works | PASS | `/v1/packaging/status` returned HTTP 200. |
| Release diagnostics work | PASS | `/v1/release/diagnostics` returned HTTP 200. |
| Voice subsystem initializes | PASS | `/v1/voice/ptt/status` and `/v1/speech/health` returned HTTP 200; wake word disabled. |
| Hotkey subsystem initializes | PASS | `/v1/hotkeys/status` returned HTTP 200; wake word/background transcription disabled. |
| Tray state loads | PASS | `/v1/desktop/tray` returned HTTP 200. |
| Startup scheduler state loads | PASS | `/v1/startup/status` returned HTTP 200 with valid LaunchAgent args. |
| ffmpeg diagnostics | PASS | Diagnostics returned `/opt/homebrew/bin/ffmpeg`. |
| Uninstall flow | PASS | `uninstall_macos.sh --all` completed in 0.32s. |
| Clean reinstall | PASS | Reinstall completed in 0.14s and restored app plus LaunchAgent. |

## Timings

| Step | Time |
| --- | ---: |
| Build app bundle | 0.22s |
| Backend ready after installed app launch | 3s |
| Endpoint probes after backend ready | < 0.02s each for backend status endpoints |
| Uninstall | 0.32s |
| Clean reinstall | 0.14s |

## Dependencies

| Dependency | Status | Notes |
| --- | --- | --- |
| Project venv Python | OK | Used by installed backend and frontend launchers. |
| `python` command | Not required | Launcher no longer assumes it exists. |
| `uv` | OK | `/opt/homebrew/bin/uv`. |
| Node/npm | Not required for installed frontend | Built static assets are served by the local frontend server. |
| Ollama | OK | `/opt/homebrew/bin/ollama`; not started by smoke backend. |
| ffmpeg | OK | `/opt/homebrew/bin/ffmpeg`. |
| macOS permissions | Guidance | Microphone, Accessibility, Screen Recording, and Notifications still require user approval when enabling related features. |

## Final Install State

After the uninstall/reinstall cycle:

- `~/Applications/Siri.app` exists.
- `~/Applications/Siri.app/Contents/MacOS/Siri` exists and is executable.
- `~/Applications/Siri.app/Contents/Resources/packaging` contains bundled
  launch scripts.
- `~/Applications/Siri.app/Contents/Resources/Siri.icns` is present.
- `~/Library/LaunchAgents/com.openjarvis.siri.plist` exists and points to
  `/bin/bash` plus the installed app executable.
- No smoke backend/frontend processes were left running.

## Residual Notes

- The Phase 1 installed backend is a local release/status backend. It is
  intentionally not a model-serving or autonomous assistant runtime.
- Voice and hotkey checks validate initialization/status only. They do not
  enable wake words, background transcription, or microphone recording.
