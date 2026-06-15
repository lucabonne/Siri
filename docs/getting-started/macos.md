# macOS Install

```bash
curl -fsSL https://openjarvis.ai/install.sh | bash
```

Works on Intel and Apple Silicon. The installer auto-detects your CPU/GPU.

## Prerequisites

If you've never run `git` or `curl` on this Mac, macOS will prompt you to install the Xcode Command Line Tools the first time you run them. Accept the prompt; that gives you both.

If you'd rather pre-install:

```bash
xcode-select --install
```

## Apple Silicon notes

- The installer picks `mlx` as the recommended engine via the standard hardware-detect path, but the foreground default is still Ollama for compatibility. Switch later with `jarvis init --force` and pick `mlx` if you've installed `mlx-lm`.
- Unified memory is reported as "VRAM" by the installer — that's intentional; on Apple Silicon, system RAM is what GPU-accelerated models can use.

## Voice permissions

- Local microphone recording, when explicitly requested with `jarvis voice record-local --recorder macos`, `jarvis voice capture-preview --recorder macos`, or `jarvis voice run-local --recorder macos`, requires macOS **Microphone** permission.
- Local speech output, when explicitly requested with `jarvis voice speak "text"` or `jarvis voice run-local --speak-result`, uses the macOS `say` command if available. It does not enable automatic response playback.
- `jarvis voice doctor` reports local voice configuration and dependency availability, including macOS `say` when relevant, without requesting **Microphone** permission, downloading models, dispatching, speaking, or starting hotkeys.
- `jarvis voice hotkey-bridge` only prints the preview-only `jarvis voice run-local` command or a disabled Hammerspoon example that an external helper can call later. It does not start a global listener, capture Fn, record audio, dispatch, approve, or speak.
- `jarvis voice logs` inspects recent local structured voice events from the configured JSONL file, with optional event/status/outcome filters, approval/dispatch-only filtering, `--limit`, `--json`, explicit `--export PATH` support, and confirmation-gated cleanup via `--clear --confirm` or `--clear-before YYYY-MM-DD --confirm`. Use `--dry-run` to preview cleanup. It does not record, call the API, dispatch, approve, speak, or start hotkeys. Voice logs, exports, and cleanup do not store or delete raw audio, and transcripts are summarized by length/hash plus a redacted preview unless full transcript logging was explicitly enabled before the event was written. Export parent directories must already exist.
- Mission Control's Voice tab shows the same safe local voice stack status from `/v1/voice/ptt/status`, including configured/effective API base URL, local adapter configuration, disabled/print-only hotkey bridge state, approval requirement, and recent redacted voice events when available. It also shows a read-only diagnostics summary mirroring safe `jarvis voice doctor` fields plus logging and full transcript logging state; Mission Control does not run `jarvis voice doctor`. The setup checklist remains read-only for API base URL configuration, transcription adapter selection, model path configuration and existence, recorder boundary availability, speech output backend, macOS `say`, hotkey bridge state, approval requirement, and full transcript logging state. Missing checklist items show copyable suggestions labeled as manual terminal commands, such as `jarvis voice doctor`, `jarvis voice transcribe-file ./voice-sample.wav --adapter faster-whisper`, `jarvis voice record-local --duration 2`, `jarvis voice hotkey-bridge`, or `jarvis voice run-local --duration 2 --adapter faster-whisper`; Mission Control does not run them. Recent events can be expanded read-only to inspect sanitized event metadata, transcript length/hash/redacted preview, approval decision, dispatch/speech summaries, and error summary when available. That returned list can be filtered locally by event type, status, derived success/failure outcome, approval/dispatch-only events, and text search over safe displayed fields. It does not request **Microphone** or **Accessibility** permission, start hotkeys, dispatch, approve, speak, run CLI commands, mutate voice settings, export/clean logs, or show raw audio/full transcript text.
- For frontend-only Mission Control Voice status verification on macOS, run `npm run check:mission-control-voice` from `frontend/`. If the local Vite dev server starts without binding port `5173`, run `npm run dev:verify`; this skips only the Tailwind Vite plugin import for bind verification and does not change the normal app build.
- `[voice_control]` in `~/.openjarvis/config.toml` can provide safe defaults for explicit voice commands, such as local transcription adapter, model path, fixed record duration, API base URL, speech-output adapter, hotkey bridge command preview settings, and local voice log settings. CLI flags still override config values.
- Future Hammerspoon or Swift Fn/push-to-talk helpers will require macOS **Accessibility** permission for global hotkey capture. Any helper that invokes `jarvis voice run-local --recorder macos` will also require **Microphone** permission.
- OpenJarvis does not enable Fn capture, always-on listening, automatic dispatch, automatic speech playback, or voice-only mode in the current voice CLI.

## See also

- [Full installer reference](install.md)
