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

- Current safe workflow: run `jarvis voice doctor`, test the microphone with
  `jarvis voice mic-smoke --recorder macos --duration 1`, configure a local
  transcription backend/model, test the bounded local pipeline with `jarvis
  voice mic-transcribe-smoke --duration 1 --recorder macos --adapter
  faster-whisper`, preview it with `jarvis voice mic-preview --duration 1
  --recorder macos --adapter faster-whisper`, then continue with `jarvis voice
  record-local`, `jarvis voice transcribe-file`, `jarvis voice capture-preview`,
  `jarvis voice run-local`, and `jarvis voice logs`. None of these commands
  enables always-on listening or global hotkey capture by default.
- Local microphone recording, when explicitly requested with `jarvis voice
  mic-smoke --recorder macos --duration 1`, `jarvis voice record-local
  --recorder macos`, `jarvis voice capture-preview --recorder macos`, or
  `jarvis voice run-local --recorder macos`, requires macOS **Microphone**
  permission.
- `jarvis voice mic-smoke --duration N` requires an explicitly selected or
  configured `macos`/`sounddevice` backend and an explicit 0.1-30 second
  duration. It validates non-empty WAV metadata and deletes the file by default;
  `--keep-file` retains it. It never transcribes, submits, dispatches, or speaks.
- `jarvis voice mic-transcribe-smoke --duration N` has the same bounded real
  microphone requirements and additionally requires an explicit or configured
  local transcription adapter/model. It prints local WAV/transcript metadata
  and transcript text, deletes the WAV by default even after an expected
  transcription failure, and never submits, dispatches, starts hotkeys, or
  speaks. Use `--keep-file` to retain the WAV.
- `jarvis voice mic-preview --duration N` adds only the preview submission step:
  it requires the same real recorder and local adapter/model, posts the local
  transcript to `/v1/voice/ptt/submit-transcript`, prints preview/session state,
  and deletes the WAV unless `--keep-file` is passed. It never calls `/dispatch`,
  bypasses approval, starts hotkeys, or speaks.
- The optional real microphone adapter can also be selected explicitly with `--recorder sounddevice` or `[voice_control].default_recorder = "sounddevice"` after installing `uv sync --extra voice-mic`. It still requires an explicit duration and writes to a local WAV file only unless you separately run an explicit transcription pipeline command.
- If a microphone command fails on macOS, grant **Microphone** access to the terminal app running `jarvis` in System Settings > Privacy & Security > Microphone, then restart that terminal. This is separate from future **Accessibility** permission for global hotkey capture.
- Local speech output, when explicitly requested with `jarvis voice speak "text"` or `jarvis voice run-local --speak-result`, uses the macOS `say` command if available. It does not enable automatic response playback.
- `jarvis voice doctor` reports the configured recorder, static recorder dependency readiness, whether `sounddevice` is importable, and whether real microphone recording is explicitly configured. It does not open or probe the microphone, so macOS **Microphone** permission is reported as not checked; permission is only exercised by a later explicit recording command. The command also reports macOS `say` when relevant, without downloading models, dispatching, speaking, or starting hotkeys.
- Mission Control reads the same recorder diagnostics from `/v1/voice/ptt/status` and shows configuration-only microphone readiness. It does not open or probe the microphone, determine permission status, record audio, mutate settings, or execute commands.
- `jarvis voice hotkey-bridge` only prints the preview-only `jarvis voice run-local` command or a disabled Hammerspoon example that an external helper can call later. It does not start a global listener, capture Fn, record audio, dispatch, approve, or speak.
- `jarvis voice logs` inspects recent local structured voice events from the configured JSONL file, with optional event/status/outcome filters, approval/dispatch-only filtering, `--limit`, `--json`, explicit `--export PATH` support, and confirmation-gated cleanup via `--clear --confirm` or `--clear-before YYYY-MM-DD --confirm`. Use `--dry-run` to preview cleanup. It does not record, call the API, dispatch, approve, speak, or start hotkeys. Voice logs, exports, and cleanup do not store or delete raw audio, and transcripts are summarized by length/hash plus a redacted preview unless full transcript logging was explicitly enabled before the event was written. Export parent directories must already exist.
- Mission Control's Voice tab shows the same safe local voice stack status from `/v1/voice/ptt/status`, including configured/effective API base URL, local adapter configuration, disabled/print-only hotkey bridge state, approval requirement, and recent redacted voice events when available. It also shows a read-only readiness summary with an overall `ready`, `needs setup`, or `unsafe config` state, blocking issues, warnings, the next safe manual step, and whether preview-only local pipeline, approval-gated dispatch, and optional speech output are available. Mission Control does not run those steps. The diagnostics summary mirrors safe `jarvis voice doctor` fields plus logging and full transcript logging state; Mission Control does not run `jarvis voice doctor`. A separate safety/audit summary shows approval required, auto-dispatch disabled, auto-speech disabled, always-on listening disabled, disabled/print-only hotkey bridge state, raw audio non-storage, transcript redaction defaults, full transcript logging state, local-only event logging state, and recent approval/dispatch/speech event counts when safe event data is available. The setup checklist remains read-only for API base URL configuration, transcription adapter selection, model path configuration and existence, recorder boundary availability, speech output backend, macOS `say`, hotkey bridge state, approval requirement, and full transcript logging state. A separate read-only troubleshooting section explains missing or unsafe setup items such as no local transcription adapter, missing or non-existent model path, unavailable speech backend, unavailable macOS `say`, hotkey bridge state, disabled logging, and full transcript logging warnings; it may reference manual terminal commands but does not execute them or mutate settings. Missing checklist items show copyable suggestions labeled as manual terminal commands, such as `jarvis voice doctor`, `jarvis voice transcribe-file ./voice-sample.wav --adapter faster-whisper`, `jarvis voice record-local --duration 2`, `jarvis voice hotkey-bridge`, or `jarvis voice run-local --duration 2 --adapter faster-whisper`; Mission Control does not run them. The local pipeline command helper separately builds copyable `jarvis voice run-local --duration ...` commands, defaulting to preview-only and showing approve-dispatch or speak-result variants only as explicit manual terminal commands. Recent events can be expanded read-only to inspect sanitized event metadata, transcript length/hash/redacted preview, approval decision, dispatch/speech summaries, and error summary when available. That returned list can be filtered locally by event type, status, derived success/failure outcome, approval/dispatch-only events, and text search over safe displayed fields. It does not request **Microphone** or **Accessibility** permission, start hotkeys, dispatch, approve, speak, run CLI commands, mutate voice settings, export/clean logs, or show raw audio/full transcript text.
- For frontend-only Mission Control Voice status verification on macOS, run `npm run check:mission-control-voice` from `frontend/`. If the local Vite dev server starts without binding port `5173`, run `npm run dev:verify`; this skips only the Tailwind Vite plugin import for bind verification and does not change the normal app build.
- `[voice_control]` in `~/.openjarvis/config.toml` can provide safe defaults for explicit voice commands, such as local transcription adapter, model path, fixed record duration, recorder selection, API base URL, speech-output adapter, hotkey bridge command preview settings, and local voice log settings. CLI flags still override config values.
- Future Hammerspoon or Swift Fn/push-to-talk helpers will require macOS **Accessibility** permission for global hotkey capture. Any helper that invokes `jarvis voice run-local --recorder macos` will also require **Microphone** permission.
- OpenJarvis does not enable Fn capture, always-on listening, automatic dispatch, automatic speech playback, or voice-only mode in the current voice CLI.

## See also

- [Full installer reference](install.md)
