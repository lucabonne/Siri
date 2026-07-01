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
  --recorder macos --adapter faster-whisper`, run the default preview-only path
  with `jarvis voice mic-run --duration 1 --recorder macos --adapter
  faster-whisper`, then continue with `jarvis voice record-local`, `jarvis voice
  transcribe-file`, `jarvis voice capture-preview`, `jarvis voice run-local`,
  and `jarvis voice logs`. None of these commands
  enables always-on listening or global hotkey capture by default.
- Local microphone recording, when explicitly requested with `jarvis voice
  mic-smoke --recorder macos --duration 1`, `jarvis voice record-local
  --recorder macos --duration 1`, `jarvis voice capture-preview --recorder
  macos --duration 1`, or `jarvis voice run-local --recorder macos --duration
  1`, requires macOS **Microphone** permission.
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
- `jarvis voice mic-run --duration N` uses the same bounded real microphone,
  local transcription, and preview steps. It remains preview-only by default
  and deletes the WAV unless `--keep-file` is passed. Dispatch requires
  `--approve-dispatch` and still sends `approved=true` to the existing endpoint;
  speech additionally requires `--speak-result`. It never starts hotkeys or
  background listening.
- `jarvis voice record-local` is the intentional file-producing command: it
  retains and prints its WAV. When it resolves to `macos` or `sounddevice`, the
  explicit or configured duration is limited to 0.1-30 seconds. The four
  `mic-*` pipeline commands instead delete temporary WAVs by default and retain
  them only with `--keep-file`.
- The optional real microphone adapter can also be selected explicitly with `--recorder sounddevice` or `[voice_control].default_recorder = "sounddevice"` after installing `uv sync --extra voice-mic`; it follows the same bounded-duration policy.
- If a microphone command fails on macOS, grant **Microphone** access to the terminal app running `jarvis` in System Settings > Privacy & Security > Microphone, then restart that terminal. This is separate from future **Accessibility** permission for global hotkey capture.
- Local speech output, when explicitly requested with `jarvis voice speak "text"`, `jarvis voice run-local --approve-dispatch --speak-result`, or `jarvis voice mic-run --approve-dispatch --speak-result`, uses the macOS `say` command if available. It does not enable automatic response playback.
- `jarvis voice doctor` reports the configured recorder, `dev-silent` development-recorder availability, static recorder dependency readiness, whether `sounddevice` is importable, and whether a real microphone recorder is explicitly configured. It does not open or probe the microphone, so macOS **Microphone** permission is reported as not checked; permission is only exercised by a later explicit recording command. The command also reports macOS `say` when relevant, without downloading models, dispatching, speaking, or starting hotkeys.
- Mission Control reads the same recorder diagnostics and recording policy from `/v1/voice/ptt/status` and separately shows `dev-silent` availability, real microphone configuration, `sounddevice` dependency availability, preview-only microphone pipeline availability, approval-gated microphone dispatch availability, default temporary-WAV cleanup, and explicit `--keep-file` retention. Readiness requires a statically available real microphone backend; `dev-silent` alone is not reported as microphone-ready. Mission Control does not open or probe the microphone, determine permission status, record audio, mutate settings, or execute commands.
- `jarvis voice hotkey-bridge` prints a bounded, preview-only `jarvis voice mic-run` command or disabled Hammerspoon F18 example. `--write-hammerspoon PATH` is generated disabled bridge mode and explicitly writes that example to a new `.lua` file only; the parent directory must already exist, and the command refuses existing files and the active `~/.hammerspoon/init.lua`. `--validate-hammerspoon PATH` is validation only: it statically reads a generated/example `.lua` file, refuses the active init file, requires a disabled, bounded, real-recorder, preview-only `mic-run` command, and rejects active dispatch, speech, install-path, LaunchAgent, or execution/loading markers outside the disabled guard. `--install-preview PATH` is install preview only: it runs the same validation first, then prints the exact manual Hammerspoon steps, including the `dofile(...)` line the user would add by hand. `--activation-guide PATH` is manual guide only: it validates the bridge, prints preflight status, exact manual install steps, and exact manual rollback steps, while stating activation is user-performed outside Jarvis and preview-only behavior remains the default. `--rollback-guide PATH` is manual guide only: it inspects and statically validates the bridge file when present, prints exact manual backup steps for `~/.hammerspoon/init.lua`, shows the exact `dofile(...)` line to remove manually, and shows how to reload Hammerspoon manually. `--activation-status PATH` is manual activation readiness only: it reports whether the generated bridge exists and validates safely, whether the default remains preview-only, whether a real microphone recorder and local transcription adapter/model are configured, whether approval is required, whether dispatch and speech remain disabled unless explicit, whether the manual install and rollback guides are available, whether active init references it, whether Hammerspoon.app is detected, and that Accessibility and Microphone permissions remain user-managed. `--status PATH` is status/readiness only: it reports whether the file exists, whether validation passes, whether the default remains preview-only, whether the bridge is ready for manual review, whether activation remains deferred, whether the active `~/.hammerspoon/init.lua` appears to reference it, and whether Hammerspoon.app is detected by safe filesystem checks. Validation, install preview, activation guide, rollback guide, activation status, and status never execute Lua or shell commands from the bridge file. The active generated command omits `--approve-dispatch` and `--speak-result`; those variants are commented manual opt-in examples. It does not write `~/.hammerspoon/init.lua`, copy files, install Hammerspoon or the bridge file, start a global listener, capture Fn/F18, request **Accessibility** permission, record audio, dispatch, approve, or speak.
- `jarvis voice hotkey-runtime --contract` prints the disabled-by-default runtime contract an external Hammerspoon script must follow if the user manually installs one later. The accepted trigger is a bounded `jarvis voice mic-run --duration SECONDS --recorder macos|sounddevice --adapter faster-whisper|whisper.cpp` command using a real recorder and local transcription adapter/model. It is preview-only by default; dispatch requires explicit `--approve-dispatch`, and speech requires explicit `--speak-result` after approved dispatch. The contract documents exit codes, stdout/stderr behavior, local redacted event logging expectations, and manual rollback expectations. Printing it does not edit `~/.hammerspoon/init.lua`, install or activate Hammerspoon, start listeners, request Accessibility permission, record audio, call the API, dispatch, write a voice log event, or speak. `jarvis voice hotkey-runtime --dry-run` resolves the preview-only `mic-run` command the external trigger would call and reports missing setup guidance, with optional `--json`, without opening the microphone, loading models, submitting, dispatching, speaking, logging, starting listeners, installing Hammerspoon, editing `init.lua`, or requesting Accessibility permission.
- Full manual Hammerspoon workflow: run `jarvis voice hotkey-bridge --write-hammerspoon ./siri-ptt.lua`, `jarvis voice hotkey-bridge --validate-hammerspoon ./siri-ptt.lua`, `jarvis voice hotkey-bridge --install-preview ./siri-ptt.lua`, and `jarvis voice hotkey-bridge --activation-guide ./siri-ptt.lua`; then manually add the printed `dofile(...)` line to `~/.hammerspoon/init.lua`, manually reload Hammerspoon, inspect the final read-only checklist with `jarvis voice hotkey-bridge --activation-status ./siri-ptt.lua`, and use `jarvis voice hotkey-bridge --rollback-guide ./siri-ptt.lua` for manual rollback instructions. Every Jarvis step is preview-only or read-only by default, and activation remains manual outside Jarvis. Jarvis does not install Hammerspoon, modify `init.lua`, start global listeners, request Accessibility permission, bypass approval, dispatch by default, or speak automatically.
- `jarvis voice logs` inspects recent local structured voice events from the configured JSONL file, with optional event/status/outcome filters, approval/dispatch-only filtering, `--limit`, `--json`, explicit `--export PATH` support, and confirmation-gated cleanup via `--clear --confirm` or `--clear-before YYYY-MM-DD --confirm`. Use `--dry-run` to preview cleanup. It does not record, call the API, dispatch, approve, speak, or start hotkeys. Voice logs, exports, and cleanup do not store or delete raw audio, and transcripts are summarized by length/hash plus a redacted preview unless full transcript logging was explicitly enabled before the event was written. Export parent directories must already exist.
- Mission Control's Voice tab shows the same safe local voice stack status from `/v1/voice/ptt/status`, including configured/effective API base URL, local adapter configuration, disabled/print-only hotkey bridge state, approval requirement, and recent redacted voice events when available. It also shows a read-only readiness summary with an overall `ready`, `needs setup`, or `unsafe config` state, blocking issues, warnings, the next safe manual step, and the distinct development-recorder, real-microphone preview, approval-gated microphone dispatch, and optional speech capabilities. Mission Control does not run those steps. The diagnostics summary mirrors safe `jarvis voice doctor` fields plus logging and full transcript logging state; Mission Control does not run `jarvis voice doctor`. A separate safety/audit summary shows approval required, auto-dispatch disabled, auto-speech disabled, always-on listening disabled, disabled/print-only hotkey bridge state, default temporary-WAV cleanup and explicit retention, transcript redaction defaults, full transcript logging state, local-only event logging state, and recent approval/dispatch/speech event counts when safe event data is available. The setup checklist remains read-only for API base URL configuration, transcription adapter selection, model path configuration and existence, recorder boundary availability, speech output backend, macOS `say`, hotkey bridge state, approval requirement, and full transcript logging state. A separate read-only troubleshooting section explains missing or unsafe setup items such as no local transcription adapter, missing or non-existent model path, unavailable speech backend, unavailable macOS `say`, hotkey bridge state, disabled logging, and full transcript logging warnings; it may reference manual terminal commands but does not execute them or mutate settings. Missing checklist items show copyable suggestions labeled as manual terminal commands, such as `jarvis voice doctor`, `jarvis voice transcribe-file ./voice-sample.wav --adapter faster-whisper`, `jarvis voice record-local --duration 2`, `jarvis voice hotkey-bridge`, or `jarvis voice run-local --duration 2 --adapter faster-whisper`; Mission Control does not run them. The local pipeline command helper separately builds copyable `jarvis voice run-local --duration ...` commands, defaulting to preview-only and showing approve-dispatch or speak-result variants only as explicit manual terminal commands. Recent events can be expanded read-only to inspect sanitized event metadata, transcript length/hash/redacted preview, approval decision, dispatch/speech summaries, and error summary when available. That returned list can be filtered locally by event type, status, derived success/failure outcome, approval/dispatch-only events, and text search over safe displayed fields. It does not request **Microphone** or **Accessibility** permission, start hotkeys, dispatch, approve, speak, run CLI commands, mutate voice settings, export/clean logs, or show raw audio/full transcript text.
- For frontend-only Mission Control Voice status verification on macOS, run `npm run check:mission-control-voice` from `frontend/`. If the local Vite dev server starts without binding port `5173`, run `npm run dev:verify`; this skips only the Tailwind Vite plugin import for bind verification and does not change the normal app build.
- `[voice_control]` in `~/.openjarvis/config.toml` can provide safe defaults for explicit voice commands, such as local transcription adapter, model path, fixed record duration, recorder selection, API base URL, speech-output adapter, hotkey bridge command preview settings, and local voice log settings. CLI flags still override config values.
- Future Hammerspoon or Swift Fn/push-to-talk helpers will require macOS **Accessibility** permission for global hotkey capture. OpenJarvis does not request it programmatically. Any manually enabled helper that invokes `jarvis voice mic-run --recorder macos` will also require **Microphone** permission.
- OpenJarvis does not enable Fn capture, always-on listening, automatic dispatch, automatic speech playback, or voice-only mode in the current voice CLI.

## See also

- [Full installer reference](install.md)
