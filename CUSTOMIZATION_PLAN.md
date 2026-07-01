# Customization Plan

## Voice Control Hotkey Activation Phase 3

Activation Phase 3 adds a final manual Hammerspoon bridge activation readiness
summary without activating anything from Jarvis.

- `jarvis voice hotkey-bridge --activation-status PATH` inspects a generated
  Hammerspoon bridge file with the existing static validator and summarizes
  whether it exists, validates safely, remains preview-only by default, has
  manual install and rollback guide paths available, is referenced by the
  active `~/.hammerspoon/init.lua`, and whether Hammerspoon.app is detected by
  safe filesystem checks.
- The summary states that Accessibility and Microphone permissions remain
  user-managed, no global listener was started by Jarvis, and activation remains
  deferred/manual.
- The command does not execute Lua, run shell commands from the bridge file,
  mutate files, touch active Hammerspoon config, install Hammerspoon, request
  permissions, bypass approval, dispatch by default, or speak automatically.
- Existing `jarvis voice` commands, Voice Control Phase 1-30, Mic Phase 1-8,
  Hotkey Phase 1-6, Hotkey Activation Phase 1-2, and read-only Mission Control
  behavior remain intact. Voice-only mode remains deferred.

Deferred work remains intentionally untouched:

- no always-on listening
- no enabled Fn/global hotkey capture
- no Python-started global hotkey listener
- no automatic Hammerspoon installation or init mutation
- no programmatic Accessibility permission request
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no voice-only mode; text input remains available

## Voice Control Hotkey Activation Phase 2

Activation Phase 2 adds a manual Hammerspoon bridge backup/rollback instruction
generator without activating anything from Jarvis.

- `jarvis voice hotkey-bridge --rollback-guide PATH` inspects a generated
  Hammerspoon bridge file when it exists, using the existing static validator,
  and still prints rollback guidance when the bridge path is missing.
- The guide prints exact manual backup steps for `~/.hammerspoon/init.lua`,
  the exact `dofile(...)` line to remove manually, manual rollback steps, and
  manual Hammerspoon reload guidance.
- The guide clearly states that no files were changed, no listener was started,
  Lua was not executed, bridge shell commands were not run, Hammerspoon was not
  installed, Accessibility permission was not requested, approval was not
  bypassed, automatic dispatch remains disabled by default, and automatic speech
  remains disabled by default.
- Existing `jarvis voice` commands, Voice Control Phase 1-30, Mic Phase 1-8,
  Hotkey Phase 1-6, Hotkey Activation Phase 1, and read-only Mission Control
  behavior remain intact. Voice-only mode remains deferred.

Deferred work remains intentionally untouched:

- no always-on listening
- no enabled Fn/global hotkey capture
- no Python-started global hotkey listener
- no automatic Hammerspoon installation or init mutation
- no programmatic Accessibility permission request
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no voice-only mode; text input remains available

## Voice Control Hotkey Activation Phase 1

Activation Phase 1 adds a manual Hammerspoon push-to-talk activation guide
without activating anything from Jarvis.

- `jarvis voice hotkey-bridge --activation-guide PATH` validates a generated
  Hammerspoon bridge file with the existing static validator, then prints a
  preflight checklist, exact manual install steps, and exact manual rollback
  steps.
- The guide clearly states that activation is user-performed outside Jarvis and
  that preview-only `jarvis voice mic-run` remains the default behavior.
- The guide does not execute Lua, run shell commands from the bridge file,
  mutate files, modify `~/.hammerspoon/init.lua`, install Hammerspoon, start
  listeners, request Accessibility permission, bypass approval, dispatch by
  default, or speak automatically.
- Existing `jarvis voice` commands, Voice Control Phase 1-30, Mic Phase 1-8,
  Hotkey Phase 1-6, and read-only Mission Control behavior remain intact.
  Voice-only mode remains deferred.

Deferred work remains intentionally untouched:

- no always-on listening
- no enabled Fn/global hotkey capture
- no Python-started global hotkey listener
- no automatic Hammerspoon installation or init mutation
- no programmatic Accessibility permission request
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no voice-only mode; text input remains available

## Voice Control Hotkey Phase 6

Hotkey Phase 6 is a final disabled-by-default bridge hardening pass before any
activation work.

- The hotkey bridge command family is documented as four separate safe modes:
  generated disabled bridge output/write, validation only, install preview only,
  and status/readiness only.
- `jarvis voice hotkey-bridge --validate-hammerspoon PATH` remains a static text
  validator. It now rejects active execution/loading markers outside the
  disabled hotkey guard in addition to active dispatch, speech, init-path, and
  LaunchAgent markers. It still never evaluates Lua or runs shell commands from
  the bridge file.
- `jarvis voice hotkey-bridge --status PATH` remains read-only and now reports
  whether the bridge is ready for manual review, that activation remains
  deferred, and that global hotkey capture is not enabled. It does not mutate
  `~/.hammerspoon/init.lua`, install anything, execute Lua, run bridge shell
  commands, request permissions, dispatch, or speak.
- `--validate-hammerspoon` no longer accepts irrelevant `--format` output
  selection, matching the existing separation for status and install preview.
- Generated Hammerspoon examples remain preview-only by default. Approved
  dispatch and result speech variants remain commented manual opt-in examples.
- Existing `jarvis voice` commands, Voice Control Phase 1-30, Mic Phase 1-8,
  Hotkey Phase 1-5, and read-only Mission Control behavior remain intact.
  Voice-only mode remains deferred.

Deferred work remains intentionally untouched:

- no always-on listening
- no enabled Fn/global hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Hotkey Phase 5

Hotkey Phase 5 adds a read-only Hammerspoon bridge status check without
activating or installing the bridge.

- `jarvis voice hotkey-bridge --status PATH` reports whether the target bridge
  file exists, whether it passes the Phase 3 static validator, whether the
  generated bridge remains preview-only by default, and whether the active
  `~/.hammerspoon/init.lua` appears to reference it.
- The status check also reports safe filesystem-only Hammerspoon app detection
  when running on macOS, plus explicit safety facts: no listener was started,
  no files were modified, Lua was not executed, bridge shell commands were not
  run, Hammerspoon was not installed, Accessibility permission was not
  requested, dispatch was not started, and speech was not started.
- Missing and invalid files are reported as status results rather than
  triggering install or execution flows.
- The command does not write `~/.hammerspoon/init.lua`, copy files, install
  Hammerspoon or the bridge file, start listeners, enable Fn/global hotkey
  capture, request Accessibility permission, record, dispatch, approve, or
  speak.
- Existing `jarvis voice` commands, Voice Control Phase 1-30, Mic Phase 1-8,
  Hotkey Phase 1-4, and read-only Mission Control behavior remain intact.
  Voice-only mode remains deferred.

## Voice Control Hotkey Phase 4

Hotkey Phase 4 adds a safe Hammerspoon bridge install preview without
activating or installing the bridge.

- `jarvis voice hotkey-bridge --install-preview PATH` validates the supplied
  generated/example `.lua` file with the Phase 3 validator before printing any
  install guidance.
- The preview prints the exact manual Hammerspoon steps, including the
  `dofile(...)` line the user would add by hand, and states that no changes
  were made.
- The command does not write `~/.hammerspoon/init.lua`, copy files, install
  Hammerspoon or the bridge file, start listeners, enable Fn/global hotkey
  capture, request Accessibility permission, record, dispatch, approve, or
  speak.
- The generated bridge remains disabled/preview-only by default. Approved
  dispatch and result speech variants remain commented manual opt-in choices.
- Existing `jarvis voice` commands, Voice Control Phase 1-30, Mic Phase 1-8,
  Hotkey Phase 1-3, and read-only Mission Control behavior remain intact.
  Voice-only mode remains deferred.

## Voice Control Hotkey Phase 3

Hotkey Phase 3 adds static validation for generated Hammerspoon bridge files
without activating or installing them.

- `jarvis voice hotkey-bridge --validate-hammerspoon PATH` reads a `.lua` file
  as text only and refuses the active `~/.hammerspoon/init.lua`.
- Validation requires `enable_openjarvis_voice_hotkey = false` and an active
  preview-only `jarvis voice mic-run` command with a 0.1-30 second duration and
  a real `macos` or `sounddevice` recorder.
- Active `--approve-dispatch`, `--speak-result`, Hammerspoon init-path mutation,
  and LaunchAgent markers are rejected. Commented manual opt-in examples remain
  valid.
- Validation does not evaluate Lua, run commands found in the file, install or
  modify files, start listeners, request Accessibility permission, record,
  dispatch, approve, or speak.
- Existing Voice Control Phase 1-30, Mic Phase 1-8, Hotkey Phase 1-2, and
  read-only Mission Control behavior remain intact. Voice-only mode remains
  deferred.

## Voice Control Hotkey Phase 2

Hotkey Phase 2 adds an explicit file-generation boundary without activating or
installing a macOS hotkey helper.

- `jarvis voice hotkey-bridge --write-hammerspoon PATH` writes a disabled
  Hammerspoon Lua example only when an output path is explicitly supplied.
- The target must be a new `.lua` file in an existing parent directory. The
  command refuses overwrites and the active `~/.hammerspoon/init.lua`.
- The active generated command calls bounded `jarvis voice mic-run` in preview
  mode. Approved dispatch and result speech variants are commented manual
  opt-in examples only.
- Generation does not install Hammerspoon or the file, start a listener, bind
  Fn/F18, request Accessibility permission, record, dispatch, or speak.
- Existing print and JSON formats, Voice Control Phase 1-30, Mic Phase 1-8,
  Hotkey Phase 1, and read-only Mission Control behavior remain intact.

Deferred work remains unchanged: always-on listening, enabled Fn/global hotkey
capture, approval bypass, automatic dispatch, automatic speech, helper
installation, permission prompts, and voice-only mode.

## Voice Control Hotkey Phase 1

Hotkey Phase 1 refines the existing disabled macOS bridge around the hardened
real-microphone stack without activating global key capture.

- `jarvis voice hotkey-bridge` remains print-only and now generates the bounded
  `jarvis voice mic-run` path with a real `macos` or `sounddevice` recorder.
- The default command and disabled Hammerspoon F18 example stop at preview.
  They omit `--approve-dispatch` and `--speak-result`; approved dispatch and
  result speech remain separate, explicit manual `mic-run` terminal variants.
- The helper keeps `enable_openjarvis_voice_hotkey = false`, does not install or
  execute the example, does not start a listener, and does not capture Fn/F18.
- Duration and recorder validation reuse the 0.1-30 second real-microphone
  boundary. Tests inspect generated text only and require no microphone,
  Accessibility permission, or global key capture.
- Mission Control remains read-only and can report only disabled/print-only
  hotkey readiness/status. It does not run bridge or microphone commands.
- Existing Voice Control Phase 1-30 and Mic Phase 1-8 commands and safety gates
  remain intact.

Deferred work remains intentionally untouched:

- no always-on listening or enabled Fn/global hotkey capture
- no LaunchAgent or Hammerspoon/Swift helper installation
- no programmatic Accessibility permission request
- no approval bypass or automatic dispatch
- no automatic speech playback
- no voice-only mode; text input remains available

## Voice Control Mic Phase 8

Mic Phase 8 is the final microphone-stack hardening pass before any Fn/global
hotkey activation work.

- The existing command family remains intact: `record-local` records and
  intentionally retains its output; `mic-smoke`, `mic-transcribe-smoke`,
  `mic-preview`, and `mic-run` use only an explicitly selected or configured
  `macos`/`sounddevice` backend and reject `dev-silent`.
- Every real-microphone capture is bounded to 0.1-30 seconds. This now also
  applies when `record-local` resolves to a real microphone backend, including
  a configured default duration.
- Temporary WAVs from the four `mic-*` pipeline commands are deleted by
  default, including expected failures, and are retained only with the explicit
  `--keep-file` flag. `record-local` is the intentional output-producing
  command and therefore keeps the WAV it prints.
- `mic-preview` never dispatches or speaks. `mic-run` dispatches only with
  `--approve-dispatch` and sends `approved=true`; speech additionally requires
  `--speak-result` and an approved dispatch.
- `jarvis voice doctor`, `/v1/voice/ptt/status`, and Mission Control use the
  same recording policy and real-microphone readiness fields. These surfaces
  remain configuration-only and do not open hardware, request permission, run
  commands, dispatch, or speak.
- Event logs continue to record safe command results and retention/dispatch/
  speech decisions while status removes recording paths and full transcript
  text. No raw audio is embedded in event logs.
- Fn/global hotkey capture, always-on listening, voice-only mode, approval
  bypass, automatic dispatch, and automatic speech remain deferred.

## Voice Control Mic Phase 7

Mic Phase 7 consolidates the explicit microphone command family and makes
readiness describe the real-microphone pipeline rather than treating the
`dev-silent` development recorder as microphone readiness.

- The command stages are explicit and unchanged: `record-local` and
  `mic-smoke` record only; `mic-transcribe-smoke` records and transcribes;
  `mic-preview` records, transcribes, and previews; `mic-run` records,
  transcribes, previews, and dispatches only with `--approve-dispatch`.
  `run-local` remains the compatible general pipeline, including its safe
  `dev-silent` default and explicit dispatch/speech flags.
- `jarvis voice doctor` and `/v1/voice/ptt/status` separately expose
  `dev-silent` availability, real microphone configuration, and the optional
  `sounddevice` dependency. These checks remain configuration-only and never
  open microphone hardware or request permission.
- Status readiness reports real-microphone preview and approval-gated dispatch
  availability only when a real recorder backend and its static dependency,
  local transcription, model requirements, and safety gates are ready.
- Mission Control displays those distinctions read-only. It adds no recording
  controls, command execution, settings mutation, permission requests, or
  automatic behavior.
- Tests mock recorder/dependency boundaries and require no microphone hardware
  or model downloads. All Mic Phase 1-6 commands and behavior remain intact.
- Fn/global hotkey listening, always-on listening, voice-only mode, approval
  bypass, automatic dispatch, and automatic speech remain deferred.

## Voice Control Mic Phase 6

Mic Phase 6 adds an explicit bounded microphone-to-preview-and-optional-approved-
dispatch command while keeping preview as the default and speech separately
opt-in.

- `jarvis voice mic-run --duration 1 --recorder sounddevice --adapter
  faster-whisper` records one bounded local WAV, transcribes locally, submits
  the transcript to `/v1/voice/ptt/submit-transcript`, prints preview/session
  state, and deletes the WAV by default. `--keep-file` explicitly retains it.
- Only the real `macos` and `sounddevice` recorder backends are accepted. The
  duration remains required and limited to 0.1-30 seconds.
- Dispatch occurs only with `--approve-dispatch`, through the existing
  `/v1/voice/ptt/dispatch` endpoint with `approved=true`. The server approval
  gate is unchanged.
- Speech occurs only with `--speak-result`, which is rejected unless
  `--approve-dispatch` is also present. Nothing speaks by default.
- WAV cleanup also runs after expected transcription, API, dispatch, or speech
  failures. Existing recorder, permission, dependency, device, model, API, and
  speech adapter errors provide local setup guidance.
- Tests mock recorder, transcription, API, and speech boundaries and require no
  microphone hardware, model download, or audible output.
- Existing `jarvis voice` commands and Mic Phase 1-5 behavior remain unchanged.
  Mission Control remains read-only. Always-on listening, wake words, enabled
  Fn/global hotkeys, live Hammerspoon/Swift helpers, approval bypass, automatic
  dispatch, automatic speech, and voice-only mode remain deferred.

## Voice Control Mic Phase 5

Mic Phase 5 adds an explicit bounded microphone-to-preview command without
dispatch, hotkeys, always-on listening, approval bypass, or speech.

- `jarvis voice mic-preview --duration 1 --recorder sounddevice --adapter
  faster-whisper` records one local WAV, transcribes it with an explicitly
  selected or configured local adapter/model, and submits only the transcript
  to `/v1/voice/ptt/submit-transcript`.
- The duration is required and limited to 0.1-30 seconds. The recorder must be
  the real `macos` or `sounddevice` backend selected by CLI or configuration;
  `dev-silent` is rejected.
- The preview and session state are printed. The WAV is deleted by default
  after success or an expected failure and retained only with `--keep-file`.
- Microphone permission, dependency/device, model/transcription, and API
  connection failures return local setup guidance. Tests mock recorder,
  transcription, and API boundaries and require no microphone or model download.
- The command has no dispatch or speech flags and never calls `/dispatch` or a
  speech adapter. The existing approval gate remains unchanged. Mission Control
  stays read-only; Fn/global hotkeys, always-on listening, and voice-only mode
  remain deferred.

## Voice Control Mic Phase 4

Mic Phase 4 adds an explicit bounded microphone-to-transcript smoke command
without submission, dispatch, hotkeys, always-on listening, or speech.

- `jarvis voice mic-transcribe-smoke --duration 1 --recorder sounddevice
  --adapter faster-whisper` records one local WAV and transcribes it with an
  explicitly selected or configured local adapter/model.
- The duration is required and limited to 0.1-30 seconds. The recorder must be
  the real `macos` or `sounddevice` backend selected by CLI or configuration;
  `dev-silent` is rejected.
- Recorder and WAV metadata, transcription metadata, and transcript text are
  printed locally. The WAV is deleted by default after success or failure and
  retained only with `--keep-file`.
- Missing microphone permission, recorder/device dependencies, transcription
  dependencies, and invalid model paths return the existing local setup
  guidance. Tests use mocked recorder and transcription boundaries and require
  no microphone hardware or model download.
- The command never calls `/v1/voice/ptt/submit-transcript` or `/dispatch` and
  never speaks. Mission Control remains read-only. Fn/global hotkey capture,
  always-on listening, voice-only mode, approval bypass, automatic dispatch,
  and automatic speech remain deferred.

## Voice Control Mic Phase 3

Mic Phase 3 adds an explicit bounded microphone recording smoke test without
transcription, submission, dispatch, hotkeys, or speech.

- `jarvis voice mic-smoke --duration N` records only for the supplied duration,
  which is required and limited to 0.1-30 seconds.
- The command requires `--recorder macos`, `--recorder sounddevice`, or one of
  those real microphone backends in `[voice_control].default_recorder`; the
  `dev-silent` backend is rejected so the smoke test cannot report a false
  microphone success.
- The resulting local WAV is checked for readable, non-empty channel, sample,
  rate, frame, size, and duration metadata. It is deleted by default and kept
  only with `--keep-file`.
- Recorder dependency, permission, device, and invalid-WAV failures return
  actionable local guidance. Tests use mocked recorders and require no
  microphone hardware.
- Mission Control remains read-only. Fn/global hotkey capture, always-on
  listening, voice-only mode, approval bypass, automatic dispatch, and
  automatic speech remain deferred.

## Voice Control Mic Phase 2

Mic Phase 2 adds configuration-only microphone diagnostics to the existing
safe CLI and Mission Control status surfaces. Diagnostics never open an input
stream, request permission, record audio, start hotkeys, dispatch, or speak.

- `jarvis voice doctor` reports the configured recorder backend, backend
  dependency availability, whether `sounddevice` is importable, whether a real
  microphone recorder is explicitly configured, and whether that configuration
  is ready based only on static dependencies.
- macOS output includes guidance for System Settings > Privacy & Security >
  Microphone and explicitly reports that permission was not checked.
- `/v1/voice/ptt/status` exposes the same read-only recorder diagnostics and
  configuration readiness for Mission Control.
- Mission Control shows recorder and microphone configuration readiness but
  cannot record, probe hardware, mutate settings, or execute commands.
- Tests inject dependency and executable lookup results and do not require
  microphone hardware or macOS permissions.

Deferred work remains intentionally untouched:

- no always-on listening
- no wake word
- no enabled Fn/global hotkey capture
- no live Hammerspoon or Swift helper installation
- no approval bypass
- no automatic dispatch
- no automatic speech playback
- no voice-only mode; text input remains available

## Voice Control Mic Phase 1

Mic Phase 1 adds the first optional real local microphone recorder adapter
behind explicit CLI/config selection only. It does not enable always-on
listening, Fn/global hotkey capture, approval bypass, automatic dispatch, or
automatic speech playback.

- `SoundDeviceRecorder` uses the optional `sounddevice` package to capture
  local microphone audio only between explicit `start()` and `stop()` calls.
- `jarvis voice record-local --recorder sounddevice --duration N` writes a
  local WAV file and prints its path. It does not transcribe, submit, dispatch,
  approve, or speak.
- `jarvis voice capture-preview --recorder sounddevice --duration N` and
  `jarvis voice run-local --recorder sounddevice --duration N` may use the same
  recorder, but still follow the existing explicit transcription, preview,
  approval, dispatch, and speech gates.
- `[voice_control].default_recorder = "sounddevice"` can opt explicit voice
  CLI commands into the real mic adapter. The default remains `dev-silent`.
- The optional dependency is installed with `uv sync --extra voice-mic` or
  `pip install sounddevice`.
- Missing `sounddevice` and microphone startup failures return clear CLI
  errors. On macOS, microphone failures point users to System Settings >
  Privacy & Security > Microphone.
- Tests use mocked recorder and `sounddevice` modules, so test runs do not
  require microphone hardware or macOS permissions.

Deferred work remains intentionally untouched:

- no always-on listening
- no wake word
- no enabled Fn/global hotkey capture
- no live Hammerspoon or Swift helper installation
- no approval bypass
- no automatic dispatch
- no automatic speech playback
- no voice-only mode; text input remains available

## Voice Control Phase 30

Phase 30 is a consolidation and release-readiness pass for the safe Voice
Control stack before Fn/global hotkey activation and always-on listening.

### Voice Control Phase 1-30 summary

- Phases 1-3 established the voice architecture, explicit session FSM, preview
  endpoint, approval-gated dispatch endpoint, cancel/status endpoints, and a
  Mission Control manual transcript panel without real microphone capture.
- Phases 4-7 added the `jarvis voice` CLI bridge, local recorder boundary,
  local transcription boundary, fixed-duration `record-local`, existing-file
  `transcribe-file`, and preview-only `capture-preview` pipeline.
- Phases 8-10 added optional local `faster-whisper` and `whisper.cpp`
  transcription adapters, explicit local speech output, and the manual
  end-to-end `run-local` command. Dispatch and speech stayed behind
  `--approve-dispatch` and `--speak-result`.
- Phases 11-13 added the disabled/print-only macOS hotkey bridge boundary,
  `[voice_control]` safe defaults for explicit commands, and side-effect-free
  `jarvis voice doctor` diagnostics.
- Phases 14-17 added local structured voice event logging, redacted history
  inspection, explicit export, and confirmation-gated cleanup through
  `jarvis voice logs`.
- Phases 18-29 expanded Mission Control's read-only voice status surface:
  stack metadata, recent redacted events, event detail/filtering, setup
  checklist, manual command suggestions, diagnostics, safety/audit summary,
  copy-only local pipeline helper, troubleshooting, and readiness summary from
  `/v1/voice/ptt/status`.
- Phase 30 cleaned release-facing docs and labels so the implemented
  safe/manual workflow, optional configured behavior, and deferred activation
  scope are clearly separated.
- Mic Phase 1 adds an optional `sounddevice` real microphone recorder behind
  explicit CLI/config selection while keeping hotkeys, always-on listening,
  auto-dispatch, and auto-speech deferred.
- Mic Phase 3 adds a bounded real-microphone smoke command that validates WAV
  metadata and deletes its local recording by default.
- Mic Phase 4 adds a bounded real-microphone transcription smoke command that
  prints local transcript metadata/text, deletes audio by default, and never
  submits, dispatches, or speaks.
- Mic Phase 5 adds a bounded real-microphone preview command that submits only
  to `/v1/voice/ptt/submit-transcript`, preserves approval, deletes audio by
  default, and never dispatches or speaks.
- Mic Phase 6 adds a bounded real-microphone run command that remains
  preview-only by default, deletes audio by default, and exposes dispatch and
  speech only through the existing explicit approval and speech flags.

### Current safe workflow

1. `jarvis voice doctor`
2. `jarvis voice mic-smoke --recorder sounddevice --duration 1`
3. Configure a local transcription backend/model.
4. `jarvis voice mic-transcribe-smoke --duration 1 --recorder sounddevice
   --adapter faster-whisper`
5. `jarvis voice mic-preview --duration 1 --recorder sounddevice --adapter
   faster-whisper`
6. `jarvis voice mic-run --duration 1 --recorder sounddevice --adapter
   faster-whisper`
7. `jarvis voice record-local --duration 2`
8. `jarvis voice transcribe-file ./voice-sample.wav --adapter faster-whisper`
9. `jarvis voice capture-preview --duration 2 --adapter faster-whisper`
10. `jarvis voice run-local --duration 2 --adapter faster-whisper`
11. `jarvis voice logs`

### Implemented safe local/manual behavior

- `jarvis voice submit`, `status`, and `cancel` keep the existing preview,
  approval, dispatch, and FSM lifecycle gates.
- `record-local`, `mic-transcribe-smoke`, `mic-preview`, `mic-run`,
  `transcribe-file`, `capture-preview`, and `run-local` require explicit terminal
  invocation and never enable background listening.
- `/v1/voice/ptt/submit-transcript` previews only; `/dispatch` still requires
  `approved=true`.
- Local transcription adapters are opt-in and local-only for the voice CLI.
- Speech output is explicit through `jarvis voice speak` or
  `run-local --approve-dispatch --speak-result`.
- The hotkey bridge is disabled/print-only by default.
- Voice logs are local structured JSONL events with redacted transcript
  summaries by default; export and cleanup remain CLI-only and explicit.
- Mission Control is read-only for voice setup, readiness, diagnostics,
  checklist, filters, and recent redacted event inspection.

### Optional configured behavior

- `[voice_control]` may provide defaults for local transcription adapter/model,
  record duration, recorder selection, API base URL, explicit speech output,
  printed hotkey bridge command formatting, and local event logging.
- `--recorder macos` may be used manually and may require macOS **Microphone**
  permission.
- `--recorder sounddevice` may be used manually after installing the optional
  `voice-mic` dependency and may require OS microphone permission.
- `--approve-dispatch` may be supplied manually to dispatch after preview.
- `--speak-result` may be supplied only with `--approve-dispatch` to speak the
  explicit dispatch result.
- Full transcript logging is available only through explicit local config and
  affects future events only.

### Deferred scope

- no always-on listening
- no wake word
- no enabled Fn/global hotkey capture by default
- no live Hammerspoon or Swift helper installation
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no Mission Control settings mutation controls
- no Mission Control microphone/accessibility permission prompts
- no Mission Control log export or cleanup controls
- no voice-only mode; text input remains available

## Voice Control Phase 29

Phase 29 adds a read-only Mission Control voice readiness summary that combines
the existing diagnostics, safety audit, setup checklist, troubleshooting, and
recent redacted event status into one ready/not-ready view without enabling new
behavior.

- `/v1/voice/ptt/status` now includes a read-only `voice_stack.readiness`
  summary with an overall `ready`, `needs_setup`, or `unsafe_config` state,
  blocking issues, warnings, the next safe manual step, and availability flags
  for the preview-only local pipeline, approval-gated dispatch, and optional
  speech output.
- Mission Control renders that readiness summary above the existing diagnostics,
  safety/audit, local pipeline command helper, setup checklist, troubleshooting,
  and recent redacted event sections.
- The summary is display-only. Mission Control does not run CLI commands, mutate
  settings, request microphone or accessibility permissions, approve, dispatch,
  speak, export/clean logs, show raw audio, or reveal full transcript text from
  status-loaded events.
- The Phase 28 troubleshooting section and Phase 27 local pipeline command
  helper remain intact. Preview-only remains the default; approve-dispatch and
  speak-result variants stay explicit manual terminal commands.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn/global hotkey capture by default
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no settings mutation controls in Mission Control
- no destructive voice log cleanup/export controls in Mission Control
- no voice-only mode; text input remains available

## Voice Control Phase 28

Phase 28 adds read-only Mission Control setup troubleshooting hints for local
voice configuration without enabling new behavior.

- Mission Control now shows a separate setup troubleshooting section derived
  from the existing `/v1/voice/ptt/status` payload. It explains missing or
  unsafe setup items such as no local transcription adapter, missing model path,
  non-existent model path, unavailable speech backend, unavailable macOS `say`,
  non-standard hotkey bridge state, disabled local logging, and full transcript
  logging warnings.
- Hints are short and read-only. They may show manual terminal command
  references, but Mission Control does not execute those commands or mutate
  voice settings.
- The hotkey bridge hint preserves the disabled/print-only boundary and
  reiterates that Mission Control does not enable Fn/global hotkey capture or
  start a listener.
- The Phase 27 local pipeline command helper remains copy-only and intact.
  Preview-only remains the default; approve-dispatch and speak-result variants
  stay explicit manual terminal commands.
- Recent voice event privacy remains unchanged: raw audio is not shown, and
  status-loaded event details still show sanitized summaries instead of full
  transcript text.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn/global hotkey capture by default
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no settings mutation controls in Mission Control
- no destructive voice log cleanup/export controls in Mission Control
- no voice-only mode; text input remains available

## Voice Control Phase 27

Phase 27 adds a guarded, opt-in Mission Control helper for copying the safe
local voice pipeline command without executing anything from the UI.

- Mission Control now shows a separate local pipeline command helper that builds
  copyable manual terminal commands for `jarvis voice run-local --duration ...`.
  The default command is preview-only and keeps dispatch and speech disabled.
- When the safe status payload already identifies a supported local
  transcription adapter, the helper includes the matching `--adapter` flag. It
  otherwise leaves adapter selection to the existing CLI/config boundary.
- Optional approve-dispatch and approve-dispatch-plus-speak variants are shown
  separately and labeled as manual explicit terminal commands. Mission Control
  still only copies command text; it does not run commands or mutate settings.
- The Phase 26 diagnostics and safety/audit summaries remain intact. Raw audio
  is not shown, destructive log cleanup/export controls are not added, and full
  transcript text remains hidden from status-loaded events unless it was
  explicitly logged before the event was written.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn/global hotkey capture by default
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no settings mutation controls in Mission Control
- no destructive voice log cleanup/export controls in Mission Control
- no voice-only mode; text input remains available

## Voice Control Phase 26

Phase 26 adds a read-only Mission Control voice safety/audit summary that makes
the voice safeguards visible without enabling new behavior.

- Mission Control now shows a separate safety/audit summary for explicit
  approval, disabled auto-dispatch, disabled auto-speech, disabled always-on
  listening, disabled/print-only hotkey bridge state, raw audio non-storage,
  transcript redaction defaults, full transcript logging state, local-only event
  logging state, and recent approval/dispatch/speech event counts when safe
  event data is available.
- `/v1/voice/ptt/status` now includes read-only audit fields for disabled
  auto-dispatch/auto-speech, raw audio non-storage, transcript redaction
  default, local-only event logging, and recent safe event counts. These fields
  are derived from existing config/status data and sanitized recent event
  summaries.
- The Phase 25 diagnostics summary remains intact. The setup checklist and
  recent redacted event filters remain read-only and continue to avoid raw audio
  and full transcript text from status-loaded events.
- Mission Control still does not run CLI commands, mutate settings, start
  hotkeys, approve, dispatch, speak, export/clean logs, show raw audio, or render
  full transcript text unless it was explicitly logged before the event was
  written, and even then status-loaded full text remains hidden in the UI.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn/global hotkey capture by default
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no settings mutation controls in Mission Control
- no destructive voice log cleanup/export controls in Mission Control
- no voice-only mode; text input remains available

## Voice Control Phase 25

Phase 25 adds a read-only Mission Control voice diagnostics summary that mirrors
the safe setup fields from `jarvis voice doctor` without running the command from
the UI or changing voice command behavior.

- Mission Control now shows a diagnostics summary for API base URL,
  transcription adapter, configured model path, model path existence, default
  record duration, speech output backend, macOS `say` availability, disabled
  print-only hotkey bridge state, approval requirement, logging state, and full
  transcript logging state.
- The summary reads the existing `/v1/voice/ptt/status` voice stack payload; the
  status payload now also includes the read-only macOS `say` path alongside the
  existing availability flag.
- Phase 24 event filters remain intact. Recent event details still show only
  sanitized metadata, transcript length/hash/redacted preview, approval,
  dispatch/speech summaries, and error summary when available.
- Mission Control does not run `jarvis voice doctor`, mutate settings, start
  hotkeys, approve, dispatch, speak, export/clean logs, show raw audio, or render
  full transcript text from status-loaded events.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn/global hotkey capture by default
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no settings mutation controls in Mission Control
- no destructive voice log cleanup/export controls in Mission Control
- no voice-only mode; text input remains available

## Voice Control Phase 24

Phase 24 adds read-only Mission Control filters for recent redacted voice events
already returned by the status payload, without changing `jarvis voice` command
behavior.

- Mission Control now filters the existing recent voice event list locally by
  event type, status, derived success/failure outcome, approval/dispatch-only
  events, and text search over the safe displayed event fields.
- Filtering is client-side only and uses the same sanitized fields already shown
  in the Phase 21 detail view: event metadata, transcript length/hash/redacted
  preview, approval decision, dispatch/speech summaries, and error summary.
- Phase 23 setup command guidance remains intact: Mission Control only displays
  and copies manual terminal command text. It does not run CLI commands or
  mutate settings.
- Raw audio is never shown, and full transcript text is not rendered unless it
  was explicitly logged before the event was written.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn/global hotkey capture by default
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no settings mutation controls in Mission Control
- no destructive voice log cleanup/export controls in Mission Control
- no voice-only mode; text input remains available

## Voice Control Phase 23

Phase 23 adds read-only manual command guidance to the Mission Control voice
setup checklist, without changing `jarvis voice` command behavior.

- Missing checklist items now show copyable snippets labeled as manual terminal
  commands.
- Suggested commands stay on the safe CLI surface: `jarvis voice doctor`,
  `jarvis voice transcribe-file ./voice-sample.wav --adapter faster-whisper`,
  `jarvis voice record-local --duration 2`, `jarvis voice hotkey-bridge`, and
  `jarvis voice run-local --duration 2 --adapter faster-whisper` when relevant.
- Mission Control only copies command text to the clipboard. It does not run
  commands, mutate settings, request microphone or accessibility permissions,
  start hotkeys, dispatch, approve, speak, export logs, or clean up logs.
- Phase 22 setup checklist behavior remains intact, and Phase 21 event detail
  privacy remains intact: raw audio is never shown, and full transcript text is
  not rendered unless it was explicitly logged before the event was written.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn/global hotkey capture by default
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no settings mutation controls in Mission Control
- no destructive voice log cleanup/export controls in Mission Control
- no voice-only mode; text input remains available

## Voice Control Phase 22

Phase 22 adds a read-only Mission Control voice setup checklist before real
push-to-talk is enabled, without changing `jarvis voice` command behavior.

- Mission Control's Voice status panel now derives a setup checklist from the
  existing `/v1/voice/ptt/status` safe status fields.
- The checklist shows API base URL configuration, transcription adapter
  selection, model path configuration and existence, recorder boundary
  availability, speech output backend, macOS `say` availability,
  disabled/print-only hotkey bridge state, approval requirement, and full
  transcript logging state.
- The checklist is display-only and does not add settings mutation controls,
  destructive log cleanup/export controls, hotkey capture, dispatch, approval,
  speech, or recording behavior.
- Phase 21 event detail behavior remains intact: recent voice events still show
  only sanitized metadata, transcript length/hash/redacted preview, approval,
  dispatch/speech summaries, and error summary when available.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no settings mutation controls in Mission Control
- no destructive voice log cleanup/export controls in Mission Control
- no voice-only mode; text input remains available

## Voice Control Phase 21

Phase 21 adds a read-only Mission Control detail view for recent redacted voice
events without changing voice command execution behavior.

- Mission Control's Voice status panel keeps the Phase 20 stack/status tiles and
  now lets one recent redacted voice event expand in place for inspection.
- The detail view only shows sanitized event metadata: event type, status,
  timestamp, transcript length/hash/redacted preview when available, approval
  decision, dispatch and speech attempt/result summaries, and error summary.
- Raw audio is not exposed, and full transcript text is not shown from
  status-loaded event history. If an event was written with full transcript
  logging enabled, Mission Control still indicates that fact without rendering
  the transcript body.
- Destructive log cleanup and export controls remain CLI-only through
  `jarvis voice logs`; Mission Control does not add cleanup or export actions.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 20

Phase 20 expands the read-only Mission Control voice settings/status surface
using the stabilized Phase 19 verification path, without changing voice command
execution behavior.

- `/v1/voice/ptt/status` now includes the effective `jarvis voice` API base URL
  source, matching `jarvis voice doctor` precedence:
  `[voice_control].default_api_base_url` first, then server host/port.
- Mission Control's Voice status panel now shows the configured/effective API
  base URL, configured transcription adapter, model path status, default record
  duration, speech output backend, macOS `say` availability, disabled/print-only
  hotkey bridge state, explicit approval requirement, and recent redacted voice
  events.
- Recent voice events remain sanitized for the UI: raw audio is not exposed, and
  full transcript text is not shown from status-loaded event history.
- The existing manual Voice Push-to-Talk panel remains available and
  approval-gated; this phase does not add automation or a voice-only mode.
- `npm run check:mission-control-voice` remains the focused frontend
  verification path for the Mission Control Voice surface.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 19

Phase 19 stabilizes frontend verification for the Mission Control voice status
panel without adding new voice features or changing the Phase 18 safety
boundary.

- The Mission Control Voice status panel remains read-only and continues to use
  `/v1/voice/ptt/status` for FSM state, local voice stack metadata, approval
  status, disabled/print-only hotkey bridge state, and recent redacted voice
  events.
- Frontend investigation found that full project TypeScript checks and
  file-scoped checks for the existing Base UI wrappers hang silently in this
  environment, even though a focused Mission Control Voice status check
  completes.
- Vite port-binding investigation found that the dev server binds with a
  minimal/React-only config, but stalls before listening when the existing
  Tailwind Vite plugin is imported in this environment.
- `npm run check:mission-control-voice` provides a lightweight TypeScript smoke
  check for `MissionControlPage.tsx` plus `src/vite-env.d.ts`.
- `npm run dev:verify` starts Vite with `OPENJARVIS_VITE_SKIP_TAILWIND=1` so
  the local server bind path can be verified on `127.0.0.1:5173` while leaving
  the normal `npm run dev` and build plugin set unchanged.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 18

Phase 18 adds a safe read-only Mission Control status panel for the local voice
stack without changing the voice execution safety boundary.

- `/v1/voice/ptt/status` now includes a `voice_stack` block with FSM-adjacent
  local configuration metadata for Mission Control.
- Mission Control's Voice tab shows the FSM state, configured transcription
  adapter, model path status, default record duration, speech-output backend,
  disabled/print-only hotkey bridge state, and explicit approval requirement.
- The panel shows recent sanitized structured voice events when local voice
  logging is enabled, using redacted transcript previews and omitting local
  audio/path details.
- The existing manual voice preview flow remains available, but status-loaded
  latest transcripts are not displayed as full text in the panel.
- Tests cover safe status flags, read-only voice stack fields, and redacted
  recent event summaries.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 17

Phase 17 adds explicit local voice log cleanup and retention controls without
changing the voice execution safety boundary.

- `jarvis voice logs --clear --dry-run` previews clearing all local voice log
  events from the configured JSONL file.
- `jarvis voice logs --clear --confirm` clears local voice log events only after
  explicit confirmation.
- `jarvis voice logs --clear-before YYYY-MM-DD --dry-run` previews date-based
  retention, and `--confirm` removes dated events before that UTC date while
  retaining newer, undated, or unparseable lines.
- Cleanup supports `--json` summaries for tooling and reports matched,
  retained, and changed counts.
- Cleanup remains local-only and operates only on the configured structured
  voice log file. It does not delete audio files; voice logs do not store raw
  audio.
- Transcript redaction defaults are preserved because cleanup does not rewrite
  event payloads except to remove whole local log lines.
- Tests cover dry-run, confirmed clear, date-based retention, refusal without
  confirmation, empty log behavior, and JSON cleanup output.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 16

Phase 16 adds explicit local voice event export support without changing the
voice execution safety boundary.

- `jarvis voice logs --export PATH` writes the same filtered local events shown
  by `jarvis voice logs`.
- Exports preserve existing filters for exact event type, exact status,
  success, failure, approval/dispatch-only metadata, and `--limit`.
- Export output supports JSONL by default and JSON via `.json` paths or
  `--export-format json`.
- Export remains local-only. Paths must be local filesystem paths, and parent
  directories must already exist.
- Exports do not include raw audio. Transcript redaction remains the default,
  and full transcript text is exposed only when it was explicitly logged before
  the event was written.
- Tests cover filtered export, JSON/JSONL output, redaction preservation, empty
  log export, and invalid export path behavior.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 15

Phase 15 adds a safe voice history/inspection layer on top of the existing
local structured voice event logs.

- `jarvis voice logs` remains read-only and can now filter local JSONL events
  by exact event type, exact status, success, failure, or approval/dispatch
  metadata.
- `jarvis voice logs --approval-dispatch-only` shows approval and dispatch
  related events without calling the API or changing session state.
- `jarvis voice logs --limit N` returns the last N matching events after
  filters are applied.
- `jarvis voice logs --json` returns local event data plus the active filter
  metadata for tooling.
- Transcript inspection preserves the existing privacy boundary: redacted
  transcript summaries remain the default, and full transcript text appears
  only if full transcript logging was explicitly enabled before the event was
  written.
- Tests cover filtering, JSON output, redaction preservation, and empty log
  behavior.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 14

Phase 14 adds local structured logs for explicit voice CLI activity while
preserving the existing preview-first voice pipeline.

- `[voice_control]` now includes local voice log settings:
  `voice_logs_enabled`, `voice_logs_path`,
  `voice_logs_include_full_transcripts`, and `voice_logs_preview_chars`.
- `jarvis voice` actions write JSONL events for submit, status, cancel,
  transcribe-file, record-local, capture-preview, run-local, speak, doctor, and
  hotkey-bridge when logging is enabled.
- Log events never store raw audio. Transcript text is summarized by length,
  SHA-256, and a redacted preview by default; full transcript logging requires
  explicit config opt-in.
- Approval decisions, skipped dispatches, approved dispatch results, and speech
  attempts/results are recorded as structured metadata.
- `jarvis voice logs` shows recent local voice events without dispatching,
  speaking, recording, or starting hotkeys.
- Tests cover redaction, local JSONL writing, disabled logging, and CLI log
  output.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 13

Phase 13 adds a safe read-only diagnostics command for local voice setup.

- `jarvis voice doctor` reports the effective API base URL, configured local
  transcription adapter, required model path existence, default record duration,
  configured speech-output adapter, macOS `say` availability when relevant,
  print-only/disabled hotkey bridge state, and explicit approval requirement.
- The diagnostics path only inspects config, environment, paths, and executable
  availability. It does not request microphone access, download models, call
  dispatch, speak, or start hotkeys.
- Tests cover available and missing local dependency cases with mocks so the
  command remains side-effect free.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 12

Phase 12 adds an explicit local configuration layer for safe voice-control
defaults without enabling any risky runtime behavior by default.

- `VoiceControlConfig` adds `[voice_control]` support for local transcription
  adapter selection, model path/name override, fixed record duration, default
  API base URL, optional speech-output adapter defaults, and hotkey bridge
  command preview settings.
- `jarvis voice` commands now resolve safe defaults from config only when the
  command is explicitly invoked. CLI flags and `OPENJARVIS_BASE_URL` take
  precedence over config values.
- Configured transcription adapters remain limited to local adapters
  (`faster-whisper` and `whisper.cpp`). Missing configured model paths fail with
  clear CLI errors before transcription.
- `jarvis voice hotkey-bridge` may use config to format its printed command or
  JSON/Hammerspoon preview, but it still reports disabled listener state and
  does not start global key capture.
- Config can choose defaults for explicit speech commands, but it does not make
  the CLI speak automatically; `voice speak` or `run-local --speak-result` are
  still required.
- Dispatch remains approval-gated. Config does not cause automatic dispatch;
  `--approve-dispatch` is still required and the dispatch request still sends
  `approved=true`.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback by default
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 11

Phase 11 adds the first disabled macOS hotkey/Fn bridge boundary without adding
real global key capture.

- `openjarvis.hotkeys.macos_bridge.MacOSHotkeyBridgeCommand` formats the safe
  external helper command around the existing `jarvis voice run-local` path.
- `openjarvis.hotkeys.macos_bridge.DisabledMacOSHotkeyBridge` documents the
  adapter boundary and refuses to start capture, keeping hotkey listening
  disabled by default.
- `jarvis voice hotkey-bridge` prints the bridge command only. It can also print
  a disabled Hammerspoon example with `enable_openjarvis_voice_hotkey = false`.
- The printed bridge command uses `jarvis voice run-local` and intentionally
  omits `--approve-dispatch` and `--speak-result`, so dispatch approval and
  speech output remain explicit opt-ins.
- The command does not install Hammerspoon, start a Swift helper, capture Fn,
  listen globally, record audio, call the API, dispatch, approve, or speak.
- Documentation covers required macOS **Accessibility** permission for future
  global hotkey helpers and **Microphone** permission for explicit local
  recording with `--recorder macos`.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no enabled Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback without `--speak-result`
- no live Hammerspoon or Swift helper installation
- no voice-only mode; text input remains available

## Voice Control Phase 10

Phase 10 adds an explicit manual local end-to-end voice pipeline command while
keeping every execution and playback step opt-in.

- `jarvis voice run-local --duration N` records a local WAV with an explicit
  duration stop condition, transcribes it with an explicitly selected or
  configured local adapter, submits the transcript to
  `/v1/voice/ptt/submit-transcript`, and prints the preview/session state.
- By default `run-local` stops after preview. It does not call
  `/v1/voice/ptt/dispatch`, does not approve anything, and does not speak a
  response.
- `--approve-dispatch` is required before `run-local` calls the existing
  dispatch endpoint, and the request still sends `approved=true` through the
  server-side approval gate.
- `--speak-result` is required before `run-local` speaks any dispatch result,
  and the CLI rejects `--speak-result` unless `--approve-dispatch` is also
  present.
- Missing recorder, transcription, and speech-output dependencies surface clear
  CLI errors from the existing local adapter boundaries.
- Tests mock recording, transcription, API calls, and speech output, so they do
  not require a microphone, model download, or audible playback.
- Documentation now covers the manual pipeline, local adapter requirement,
  macOS microphone permission for `run-local --recorder macos`, and explicit
  speech output through `--speak-result`.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no Fn hotkey capture
- no approval bypass
- no automatic dispatch by default
- no automatic speech playback without `--speak-result`
- no Piper, Coqui, or other local TTS adapters yet
- no voice-only mode; text input remains available

## Voice Control Phase 9

Phase 9 adds the first optional local speech-output boundary while keeping voice
input, dispatch, and approval behavior unchanged.

- `openjarvis.voice.speech_output.LocalSpeechOutput` defines the explicit local
  speech-output contract for future voice adapters.
- `MacOSSaySpeechOutput` provides an opt-in macOS adapter backed by the local
  `say` command when available.
- `jarvis voice speak "text"` speaks only the literal text supplied on the
  command line and does not call the OpenJarvis API, submit transcripts, dispatch
  actions, or speak any dispatch result automatically.
- The macOS `say` adapter sends spoken text through subprocess stdin so user
  text is not interpreted as command-line flags.
- Tests mock the speech-output adapter and subprocess boundary, so test runs do
  not require audio output.
- Documentation now covers explicit local speech output, macOS `say` behavior,
  privacy boundaries, and deferred Piper/Coqui/other local TTS adapters.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no Fn hotkey capture
- no approval bypass
- no automatic dispatch
- no automatic speech playback of dispatch results
- no Piper, Coqui, or other local TTS adapters yet
- no voice-only mode; text input remains available

## Voice Control Phase 8

Phase 8 adds the first real optional local transcription adapter choices while
keeping voice input explicit, local, and non-dispatching by default.

- `jarvis voice transcribe-file <audio> --adapter faster-whisper` can
  transcribe an existing local audio file through the optional faster-whisper
  adapter and prints the transcript only.
- `jarvis voice transcribe-file <audio> --adapter whisper.cpp` can use a local
  whisper.cpp binary and model when explicitly configured.
- `jarvis voice capture-preview --duration N --adapter <adapter>` records for
  the explicit duration, transcribes through the selected local adapter, submits
  the transcript to `/v1/voice/ptt/submit-transcript`, and prints the preview
  only.
- Local transcription is disabled unless an adapter is selected with
  `--adapter` or `[speech].backend` is explicitly set to a supported local
  adapter.
- Missing optional dependencies, binaries, or model files return clear
  configuration errors instead of silently falling back.
- The server-side push-to-talk service no longer inherits an auto-discovered
  speech backend for voice transcription unless a local backend was explicitly
  configured.
- Dispatch remains separate: transcripts must still go through
  `jarvis voice submit --approve-dispatch` or the explicit `/dispatch` approval
  path with `approved=true`.
- Documentation now covers faster-whisper setup, whisper.cpp binary/model
  expectations, local-only privacy behavior, and the unchanged approval gate.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no Fn hotkey capture
- no approval bypass
- no automatic dispatch from transcription or preview
- no TTS response playback
- no voice-only mode; text input remains available

## Voice Control Phase 7

Phase 7 adds a safe manual local pipeline command that chains the existing
recording, transcription, and preview boundaries without adding any automatic
dispatch path.

- `jarvis voice capture-preview --duration N` records a local WAV using the
  existing recorder boundary, with the same explicit duration stop condition as
  `record-local`.
- The command transcribes the recorded WAV through the existing local
  transcription adapter boundary.
- It submits the resulting transcript to
  `/v1/voice/ptt/submit-transcript` and prints the returned intent/session
  preview.
- It does not call `/v1/voice/ptt/dispatch`. Dispatch remains available only
  through the separate explicit approval path on `jarvis voice submit
  --approve-dispatch`, which sends `approved=true`.
- CLI output names each stage: recording, transcribing, and submitting the
  preview.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no Fn hotkey capture
- no approval bypass
- no new Whisper/faster-whisper adapter implementation beyond the existing
  local transcription boundary
- no TTS response playback
- no voice-only mode; text input remains available

## Voice Control Phase 6

Phase 6 adds the first safe local recorder boundary for future push-to-talk
microphone recording while keeping the user-facing flow explicit, local, and
non-dispatching by default.

- `openjarvis.voice.recorder.Recorder` defines the explicit local recorder
  contract used by the voice service and CLI.
- Recorder implementations only capture between a direct `start()` call and a
  direct `stop()` call. Always-on listening, wake-word activation, and Fn/hotkey
  capture are intentionally outside this boundary.
- `SilentWavRecorder` provides a safe development recorder that writes a local
  silent WAV only after an explicit stop condition.
- `jarvis voice record-local --duration N` records to a local WAV file and
  prints the path. The required `--duration` option is the stop condition.
- `record-local` does not transcribe the recording, submit a transcript, call
  `/v1/voice/ptt/dispatch`, or dispatch to an agent.
- The existing `jarvis voice submit`, `transcribe-file`, `status`, and `cancel`
  commands remain available, with dispatch still gated behind
  `--approve-dispatch` and `approved=true`.

Required future macOS permissions:

- **Microphone** permission for explicitly requested local microphone recording.
- **Accessibility** permission for a later Fn/hotkey listener.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no Fn hotkey capture
- no automatic transcription from recording
- no automatic dispatch or approval bypass
- no new Whisper/faster-whisper integration beyond the existing deferred
  adapter boundary
- no TTS response playback
- no voice-only mode; text input remains available

## Voice Control Phase 5

Phase 5 adds the first local transcription adapter boundary while keeping the
user-facing voice flow explicit and non-recording by default.

- `openjarvis.voice.transcription.LocalTranscriptionAdapter` defines the local
  audio transcription contract for future adapters.
- `SpeechBackendLocalTranscriptionAdapter` wraps local speech backends without
  introducing cloud speech APIs.
- `jarvis voice transcribe-file <audio>` can transcribe an existing local audio
  file through a selected local adapter and prints the transcript only.
- File transcription does not dispatch. Users must still review text and pass it
  through `jarvis voice submit`, with `/dispatch` remaining gated behind
  `--approve-dispatch` and `approved=true`.

Expected future adapters:

- `whisper.cpp` local subprocess adapter
- `faster-whisper` local CTranslate2 adapter
- macOS dictation fallback only if explicitly enabled in a later phase

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no Fn hotkey capture
- no live microphone recording
- no cloud speech APIs
- no automatic dispatch from transcription
- no TTS response playback
- no voice-only mode; text input remains available

## Voice Control Phase 4

Phase 4 adds a local CLI/dev bridge for the manual voice flow before any
real microphone recording is introduced.

- `jarvis voice submit "..."` posts the transcript to
  `/v1/voice/ptt/submit-transcript` and prints the returned intent preview plus
  `fsm_state`.
- Dispatch remains opt-in: the CLI calls `/v1/voice/ptt/dispatch` only when
  `--approve-dispatch` is present, and it sends `approved=true` through the
  existing approval-gated endpoint.
- `jarvis voice cancel` calls `/v1/voice/ptt/cancel` so a local dev session can
  be reset without touching the UI.
- `jarvis voice status` reports the current push-to-talk/session state from
  `/v1/voice/ptt/status`.
- This command is the future bridge for a Hammerspoon/Fn push-to-talk script:
  external capture/transcription can hand a transcript to the CLI while the
  backend keeps the same preview, approval, dispatch, and cancel gates.

Deferred work remains intentionally untouched in this phase:

- no always-on listening
- no real microphone recording
- no macOS Fn listener implementation
- no Whisper/faster-whisper integration
- no cloud speech APIs
- no TTS response playback
- no voice-only mode; text input remains available

## Voice Control Phase 3

Phase 3 wires the explicit voice-session state machine through the backend and
Mission Control while keeping the user flow manual-transcript only.

- `VoiceSessionFSM` is created privately per FastAPI app instance and stored on
  `app.state`; there is no module-level/global FSM.
- `/v1/voice/ptt/status` reports the current `fsm_state` alongside the existing
  push-to-talk status payload.
- `/v1/voice/ptt/submit-transcript` accepts a typed transcript, requires
  non-empty text, produces an intent preview, and advances the FSM through
  `idle -> listening -> transcribing -> awaiting_approval` without touching a
  real microphone or transcription backend.
- `/v1/voice/ptt/dispatch` remains gated by `approved=true`, dispatches only
  from the explicit approval path in the UI, returns completion/failure details,
  and keeps no-agent behavior compatible with the existing API contract.
- `/v1/voice/ptt/cancel` is safe and idempotent; cancelling from `idle` returns
  `{fsm_state: "idle"}`.
- Mission Control adds a manual transcript textarea, preview action, approval
  dispatch action, cancel action, and clear manual-only labeling while
  keeping the existing PTT placeholder button visible.

Deferred work remains intentionally untouched in this phase:

- no Fn key listener
- no local microphone recorder wiring in the UI
- no Whisper/faster-whisper transcription flow
- no TTS response playback
- no macOS microphone permission workflow
- no voice-only mode

## Morning Briefing + World Map Phase 1

Phase 1 adds a proactive-but-quiet daily briefing layer for Siri without
autonomous interruptions, background notifications, cloud persistence, or
LaunchAgent installation.

- `src/openjarvis/morning_briefing/` owns RSS/Atom fetching, deterministic
  summarization, event categorization, world-map event shaping, typed models,
  a scheduler abstraction, and the coordinating service.
- SQLite storage now covers cached `daily_briefings` plus categorized
  `morning_events` with title, category, latitude/longitude, source URL,
  source name, short summary, published timestamp, and metadata.
- Briefings are timestamped, source-linked, categorized, and location-aware
  where lightweight local inference can identify a place.
- `/v1/morning-briefing/latest`, list, `/world-events`, `/events`,
  `/regenerate`, and `/status` expose the local cache and explicit regeneration
  flow for Mission Control.
- Privacy Mode disables external news fetching. Existing cached briefings and
  events remain readable, and regeneration returns cached content only when it
  exists.
- Memory integration records generated briefing summaries as local structured
  memories outside Privacy Mode.
- Mission Control now includes Today, World Map, Daily Briefing, and Important
  Events surfaces backed by the briefing APIs with local fallbacks.
- The scheduler is intentionally only an abstraction that can report due
  status; it does not install or run a macOS LaunchAgent.

Deferred work for that original briefing phase was intentionally untouched
until Startup / Boot Scheduler Phase 1:

- no autonomous interruptions
- no background notifications
- no cloud persistence
- LaunchAgent installation moved to Startup / Boot Scheduler Phase 1

## Startup / Boot Scheduler Phase 1

Phase 1 adds local login-startup support and a passive once-per-day Morning
Briefing trigger without introducing a scheduler daemon, autonomous
notifications, or continuous background monitoring.

- `src/openjarvis/startup/` owns LaunchAgent plist generation, install/remove
  helpers, validation, local JSON state, passive scheduled task descriptors,
  and the coordinating startup service.
- Startup state is stored locally under `~/.openjarvis/state/` in
  `last_morning_briefing.json` and `scheduler_state.json`.
- The passive scheduler detects first launch of the day, evaluates a
  Morning Briefing task at a configured local time, and prevents duplicate
  briefings by comparing the stored last briefing date.
- macOS LaunchAgent support writes a user LaunchAgent for `jarvis serve` on
  login with `RunAtLoad=true` and `KeepAlive=false`; validation reports plist
  path, label, expected arguments, installed arguments, and validity.
- `/v1/startup/status`, `/scheduler/status`, `/install`, `/remove`, and
  `/morning-briefing` expose startup status, scheduler status, launch-at-login
  control, and manual briefing triggering.
- The FastAPI app evaluates startup tasks once on process startup, but only
  auto-triggers Morning Briefing when the LaunchAgent is installed and valid.
- Mission Control Settings now shows launch-at-login controls, startup status,
  passive scheduler status, last briefing timestamp, and manual briefing
  trigger controls.
- Privacy Mode remains local-only: no startup telemetry is emitted, scheduler
  state stays on disk, and external briefing fetches stay blocked.

Deferred work remains intentionally untouched in this phase:

- no autonomous notifications
- no continuous background monitoring
- no scheduler daemon process
- no external startup telemetry

## WorldMonitor Integration Phase 1

Phase 1 adds `koala73/worldmonitor` as an optional local-first intelligence
source for Siri while keeping Siri as the orchestrator and operating layer.

- `src/openjarvis/worldmonitor/` owns local API detection, payload adapters,
  event normalization, map filtering, SQLite caching, typed models, and the
  passive integration service.
- The integration detects localhost WorldMonitor APIs and nearby local repos
  but does not clone, fork, vendor, or modify the WorldMonitor repository.
- Imported WorldMonitor data is cached locally as source-aware events with
  categories, summaries/signals, latitude/longitude, source URLs, import
  timestamps, and raw-domain metadata.
- `/v1/worldmonitor/status`, `/events`, `/briefing-data`, `/sync`, and
  `/sync-status` expose passive sync and cached reads. There is no background
  polling daemon.
- Morning Briefing can enrich generated briefings with cached/local
  WorldMonitor events. In Privacy Mode it may ingest from a detected local
  WorldMonitor instance only; RSS/news fetching remains disabled.
- The Context Layer exposes passive WorldMonitor status through
  `/v1/context/worldmonitor`.
- Memory integration records local sync summaries outside Privacy Mode only.
- Mission Control shows WorldMonitor connection state, cache counts, source
  indicators, source links, and sync timestamps in the World Map and Daily
  Briefing surfaces.

Deferred work remains intentionally untouched in this phase:

- no autonomous monitoring
- no background polling daemon
- no remote telemetry
- no external uploads
- no changes to the WorldMonitor repo itself

## Memory Architecture Phase 1

Phase 1 adds the local-first memory foundation for Siri without enabling
autonomous memory writing or advanced summarization.

- `src/openjarvis/memory/service.py` owns the structured SQLite schema for
  memories, projects, tasks, sources, research reports, command history,
  agent runs, and daily briefings.
- The memory service supports creating, listing, filtering, searching,
  deleting, pinning, and unpinning memories. Filters cover project id, memory
  type, creation window, and pinned state.
- Source metadata is first-class for memories: title, URL, timestamp,
  relevance, and tags are stored in the `sources` table and returned through
  the API.
- `src/openjarvis/memory/semantic.py` adds optional local ChromaDB indexing
  with a tiny deterministic embedding function. If ChromaDB or embedding
  setup fails, the service falls back to SQLite FTS/LIKE search.
- `/v1/memory` now exposes list/create/delete/search routes for structured
  memory while preserving the older `/store`, `/search`, `/stats`, and
  `/index` compatibility paths.
- Mission Control's Memory tab now reads, searches, creates, pins, and deletes
  through the backend API, falling back to mock data when the backend is not
  reachable.

Deferred work remains intentionally untouched in this phase:

- no autonomous memory writing
- no advanced summarization
- no redesign of the existing agent or retrieval architecture

## Agent Workspace Phase 1

Phase 1 adds a configuration-driven multi-agent workspace for Siri without
introducing autonomous planning or a full orchestrator redesign.

- `src/openjarvis/agent_workspace/` owns the central workspace registry,
  typed agent configuration models, default Siri agent definitions, active
  agent state, and lightweight routing metadata.
- The default registry defines `coding`, `research`, `engineering`,
  `privacy`, `scheduler`, `CAD`, `terminal`, and `vision` agents. Each agent
  declares id, display name, description, allowed tools, memory scopes,
  permission ceiling, preferred model, personality mode, output style, and
  orchestrator routing hints.
- `PermissionMiddleware` now accepts an optional per-request permission
  ceiling and denies tool calls whose classified level exceeds the active
  workspace agent's ceiling.
- Server-side tool gating can consult the workspace registry for an active
  agent's allowed tools, memory scopes, and permission ceiling before
  executing server-streamed tool calls.
- `/v1/agent-workspace` exposes list/get/switch/current active-agent routes.
- Mission Control's Agents tab reads the live registry and switches the active
  agent through the backend, while keeping its mock fallback when the local API
  is unavailable.

Deferred work remains intentionally untouched in this phase:

- no autonomous planning
- no complex multi-agent execution graph
- no orchestrator rewrite

## Mode System Phase 1

Phase 1 adds a global Siri operating mode layer without changing the core
agent orchestration model.

- `src/openjarvis/modes/` owns the central mode registry, typed mode models,
  default mode definitions, and local active-mode persistence at
  `~/.openjarvis/state/current_mode.json`.
- The default registry defines `focus`, `research`, `creative`, `quiet`,
  `coding`, `engineering`, and `privacy`. Each mode declares verbosity,
  proactive level, interruption policy, preferred agents, memory behavior,
  privacy/network policy, default model overrides, UI theme metadata, and
  notification behavior.
- `/v1/modes` exposes list, active-mode, and switch-mode APIs. Switching a
  mode updates the persisted state file.
- Agent Workspace responses now include the active mode id and preferred-agent
  hints so Mission Control and future routing layers can read the mode without
  redesigning the orchestrator.
- `PermissionMiddleware` can consult the active mode. Privacy Mode blocks
  remote MCP tool execution and denies non-localhost HTTP/browser/web-search
  networking where the current permission layer can see the target.
- Server chat and cloud reload routes reject cloud API usage while Privacy
  Mode is active. Remote MCP discovery is skipped in Privacy Mode while local
  stdio tools remain available.
- Mission Control now includes a live mode switcher backed by `/v1/modes`,
  with a small local fallback when the backend is unavailable.

Deferred work remains intentionally untouched in this phase:

- no autonomous behavior
- no orchestrator rewrite
- no proactive scheduling or background mode actions

## Context Layer Phase 1

Phase 1 adds passive desktop and project awareness for Siri without enabling
autonomous desktop control or project execution.

- `src/openjarvis/context/` owns the local context models and the
  `ContextLayer` collector for desktop, project, and repository snapshots.
- Desktop awareness uses macOS-local mechanisms where available:
  AppleScript for the frontmost application/window title, `pbpaste` for a
  redacted clipboard preview, process cwd for the current working directory,
  and bounded filesystem scanning for recent files.
- Project awareness detects the git repository root, current branch,
  language mix, framework/build-system hints, package managers, and a coarse
  project type from local manifests and file extensions.
- Lightweight repo indexing returns a bounded file inventory, top-level module
  summaries, dependency hints from local manifests, and architecture metadata
  such as frontend/backend/Rust/tests presence.
- `/v1/context/desktop`, `/v1/context/project`, and `/v1/context/repo` expose
  read-only local APIs for Mission Control and future prompt-context assembly.
- Mission Control now surfaces Current App, Current Project, Current Repo,
  Current Branch, Tech Stack, and Clipboard Preview from the context APIs.
- Privacy Mode is respected by redacting clipboard preview content. Sensitive
  clipboard-looking values are redacted in all modes where practical.

Deferred work remains intentionally untouched in this phase:

- no autonomous execution
- no desktop control
- no outbound context transmission

## Repo Semantic Indexing Phase 1

Phase 1 gives Siri deeper local repository understanding while keeping the
indexer passive, local-only, and privacy-aware.

- `src/openjarvis/repo_index/` owns scanner, models, semantic index,
  architecture, dependency graph, language detection, build detection, and
  service APIs.
- The scanner detects git repositories and branches, respects git ignored
  paths, skips common build/cache/vendor directories, and avoids sensitive
  path names such as `.env`, credentials, tokens, keys, and local databases.
- Stack detection covers languages, frameworks, package managers, build
  systems, and project type, with specialized handling for Java, Gradle,
  Fabric, Minecraft mods, Loom, Rust, Python, and Node/Vite projects.
- Architecture maps summarize packages/modules, build files, entry points,
  major directories, configuration files, dependency hints, and repo metadata.
- Semantic indexing creates compact file summaries and deterministic local
  hash embeddings for repo-wide search. It performs no outbound uploads and
  does not download embedding models.
- Dependency graph extraction reads manifests and import statements to expose
  direct dependency hints and lightweight internal edges.
- `/v1/repo/summary`, `/v1/repo/architecture`, `/v1/repo/search`,
  `/v1/repo/dependency-graph`, and `/v1/repo/stack` expose read-only local
  APIs for Mission Control and future context assembly.
- The Context Layer now delegates project/repo understanding to the repo index
  service, Terminal Co-Pilot records repo architecture hints with command
  context, Agent Workspace declares `repo_index` memory scope for coding,
  engineering, and terminal agents, and the memory service can store explicit
  repo-index metadata snapshots.
- Mission Control now includes a Repo tab for detected stack, architecture
  summary, semantic repo search, and dependency overview.

Deferred work remains intentionally untouched in this phase:

- no autonomous repo modification
- no automatic refactors
- no background watchers
- no cloud embeddings or outbound repository uploads

## Coding Assistant Specialization Phase 1

Phase 1 adds passive developer intelligence on top of the repo index, terminal
co-pilot, context layer, agent workspace, memory, and permission systems.

- `src/openjarvis/coding_assistant/` owns specialized advisory modules for
  Gradle, Fabric, Minecraft mods, Java, debugging, architecture guidance,
  refactor guidance, build analysis, typed models, and the coordinating
  service.
- Stack specialization detects Gradle, Fabric, Minecraft mods, Loom, Java 21,
  Node/Vite, Rust, and Python by reading local manifests and indexed files.
- Build analysis classifies Gradle task failures, Java/toolchain mismatches,
  Fabric metadata and mixin issues, Minecraft mapping/remap failures,
  Node/Vite/TypeScript errors, Rust compiler diagnostics, and Python
  tracebacks.
- Repo-aware guidance identifies entry points, major modules, dependency
  hints, risky refactors, and debugging entry points from the semantic repo
  index and architecture map.
- Terminal Co-Pilot output can feed the coding panel, but the coding assistant
  only summarizes and suggests next diagnostic steps. It does not execute
  commands or modify code.
- Suggested diagnostic commands are passed through `PermissionMiddleware` in
  dry-run mode so Mission Control can show approval metadata without running
  anything.
- Memory integration reuses explicit repo-index snapshots when requested and
  skips memory persistence in Privacy Mode.
- `/v1/coding/analyze-build`, `/architecture`, `/debugging-summary`,
  `/safe-fixes`, `/health`, and `/panel` expose local-only passive APIs.
- Mission Control now includes a Coding tab for build health, repo health,
  current stack, recent errors, suggested fixes, architecture overview, and
  risky refactor notes.
- Privacy Mode keeps analysis local, suppresses memory persistence, and
  reports no cloud uploads.

Deferred work remains intentionally untouched in this phase:

- no autonomous refactors
- no automatic code modification
- no autonomous terminal execution
- no cloud build/debug analysis

## Vision Layer Phase 1

Phase 1 adds passive screenshot context for Siri without enabling autonomous
screen watching or cloud image processing.

- `src/openjarvis/context/vision.py` owns explicit macOS screenshot capture
  through the local `screencapture` utility plus JSONL metadata storage under
  the local OpenJarvis vision directory.
- Screenshot metadata records capture time, local file path, image dimensions,
  byte size, SHA-256, active application/window hints, and passive/local-only
  flags. Image bytes stay on disk and are never sent to cloud APIs.
- `/v1/context/vision/screenshots` supports explicit capture and recent
  metadata listing. `/v1/context/vision/latest` returns the latest visual
  context metadata without image bytes.
- Privacy Mode blocks screenshot capture and queues an approval request for the
  vision capture tool. Recent/latest metadata is redacted in Privacy Mode by
  hiding local paths, hashes, and window titles.
- `PermissionMiddleware` classifies `vision_screenshot_capture` as an explicit
  local action and applies the Privacy Mode screenshot approval guard.
- Mission Control now includes a Vision tab with explicit capture, recent
  screenshot metadata, local-only status, and Privacy Mode redaction signals.

Deferred work remains intentionally untouched in this phase:

- no autonomous screen watching
- no background polling
- no OCR or cloud vision analysis
- no screen control or click automation

## Voice Push-to-Talk Phase 1

Phase 1 adds explicit voice input for Siri without wake-word detection,
always-on listening, background recording, or autonomous responses.

- `src/openjarvis/voice/` owns a dedicated modular voice subsystem:
  `recorder.py` handles local audio capture, `transcription.py` handles
  faster-whisper local transcription, `models.py` defines `VoiceSession` and
  intent preview payloads, `permissions.py` handles PermissionMiddleware and
  Approval Queue integration, `state.py` owns active/latest session state, and
  `service.py` coordinates the passive push-to-talk workflow. `ptt.py` remains
  a compatibility import surface.
- Local macOS microphone capture is supported through local recording tools
  (`ffmpeg` avfoundation first, then `sox`/`rec`) and stores raw audio only in
  a temporary local file unless `persist_raw_audio` is explicitly enabled.
- Local-first push-to-talk transcription prefers `faster-whisper`. If no local
  faster-whisper backend is available, the latest-recording path returns a
  clear backend-unavailable response and does not call cloud transcription APIs.
- `/v1/voice/ptt/start`, `/stop`, `/status`, and `/transcribe-latest` expose
  the Phase 1 recording APIs. `/v1/speech/transcribe` remains the existing
  uploaded-audio compatibility endpoint.
- `SpeechConfig` now defaults voice capture off, requires explicit voice
  approval, disables raw audio persistence, and caps local recording duration
  metadata for future enforcement.
- `PermissionMiddleware` classifies microphone capture as confirmed execution.
  Privacy Mode blocks voice capture unless the request includes explicit
  push-to-talk approval.
- The mode registry now carries `voice_capture_behavior` metadata for Privacy
  Mode: push-to-talk only, wake word disabled, background recording disabled,
  explicit approval required, local-only transcription, and raw audio storage
  off by default.
- The voice service records active mode, active workspace agent, agent memory
  scopes, and passive Context Layer desktop/project snapshots as minimal
  metadata while avoiding persistent raw audio by default.
- After transcription, the service returns a passive intent preview with the
  transcript, interpreted intent, planned actions, risk level, and approval
  requirement. It does not route or execute anything automatically.
- The Memory system receives only minimal voice metadata when available and
  Privacy Mode is off; raw audio and full transcript persistence remain off by
  default.
- Mission Control now includes a Voice tab with a hold-to-talk control,
  recording indicator, local privacy/agent status, transcript preview, intent
  preview, and approval-required signal.

Deferred work remains intentionally untouched in this phase:

- no wake word
- no passive listening
- no autonomous transcript submission
- no background microphone capture
- no persistent raw audio unless explicitly enabled

## Terminal Co-Pilot Phase 1

Phase 1 adds passive terminal awareness and local-only terminal debugging
assistance without enabling autonomous command execution.

- `src/openjarvis/context/terminal.py` owns terminal command snapshots,
  recent history, local error analysis, possible fixes, and dry-run annotated
  suggested commands.
- Captured snapshots include last command, bounded command output, exit code,
  cwd, repository/project context, shell type, timestamp, and passive/local
  metadata.
- `/v1/context/terminal/current`, `/history`, `/error-summary`, and
  `/suggested-fixes` expose read-only terminal context APIs. A local shell
  integration can passively record completed commands through
  `/v1/context/terminal/commands`.
- Error analysis is lightweight and local: it detects missing dependencies,
  command-not-found errors, permission failures, occupied ports, git
  conflicts, Python tracebacks, TypeScript diagnostics, Rust compiler errors,
  and generic non-zero exits.
- Suggested commands are not executed. They are classified through
  `PermissionMiddleware`, include dry-run previews, and clearly mark dangerous
  commands with matched permission patterns.
- Suggested command approval requests can be queued through the existing
  approval queue, preserving a passive "request approval only" workflow for
  future execution phases.
- Structured memory now records terminal command summaries in the existing
  `commands_history` table when Privacy Mode is off.
- Mission Control's Terminal tab now shows Recent Commands, Last Error,
  Suggested Fixes, and Suggested Commands from the live terminal context APIs.
- Privacy Mode redacts command/output payloads in terminal APIs and skips
  structured memory writes for captured terminal commands.

Deferred work remains intentionally untouched in this phase:

- no autonomous terminal execution
- no shell hook installer
- no cloud-based terminal analysis
- no automatic fix application

## Phase 1 Permission System

Phase 1 adds a minimal Python-side permission layer before existing tool
boundary and capability checks. The new middleware lives in
`src/openjarvis/security/permissions.py` and introduces:

- `PermissionLevel` for coarse request levels: read-only, safe action,
  confirmed execution, and dangerous.
- `PermissionRequest` and `PermissionDecision` dataclasses for a stable
  decision contract.
- `PermissionMiddleware`, which classifies tools by name, inspects
  `shell_exec` commands for dangerous patterns, supports dry-run decision
  checks, and appends JSONL audit records to
  `~/.openjarvis/logs/permissions.log`.

`ToolExecutor.execute()` now calls the middleware immediately after JSON
argument parsing and before boundary guard checks, RBAC capability checks,
taint checks, legacy confirmation, and `tool.execute()`. Dangerous requests
are denied before execution. Confirmed requests reuse the existing interactive
confirmation callback so tools that already set `requires_confirmation=True`
do not prompt twice.

Deferred work remains intentionally untouched in this phase:

- no Rust executor changes
- no MCP streaming bypass changes
- no broader tool-system refactor

## Phase 2 Server Streaming And MCP Gate

Phase 2 closes the Python server streaming bypass where tool calls emitted by
`engine.stream_full()` could execute directly in
`src/openjarvis/server/agent_manager_routes.py` without going through
`ToolExecutor.execute()`.

The server now performs a minimal permission check before both direct MCP
adapter execution and server-created tool execution. The request includes the
tool name, parsed arguments, agent id, and `source="server_streaming"` metadata.
Dangerous requests are denied, and requests that require confirmation are
blocked unless a future route supplies an explicit user approval path.

The server no longer uses unconditional
`confirm_callback=lambda _prompt: True` approvals in this module. The MCP
adapter path remains otherwise unchanged; Phase 2 intentionally does not
redesign streaming, MCP discovery, or the broader tool system.

## Phase 3 Tool-Specific Hardening

Phase 3 adds defense-in-depth inside high-risk Python tools so direct tool
execution remains guarded even if a caller bypasses `ToolExecutor` or the
server streaming permission gate.

The hardened tools now perform local checks before touching the filesystem,
spawning processes, or launching containers:

- `shell_exec` reuses `PermissionMiddleware.classify_shell_command()` and
  blocks dangerous shell command patterns before either Rust or Python
  execution.
- `file_write` blocks sensitive files, protected system paths, path traversal,
  and symlink targets that resolve to sensitive files.
- `apply_patch` blocks sensitive files, protected system paths, and path
  traversal from both explicit `path` input and patch headers.
- `file_read` continues to honor allowed roots and now also blocks sensitive
  symlink targets.
- `code_interpreter` runs from an isolated temporary workdir and blocks obvious
  absolute or parent-path literals before execution.
- `ContainerRunner` rejects dangerous host mounts such as `/` before invoking
  Docker or Podman and logs sandbox start/completion/timeout events.

Deferred work remains intentionally untouched in this phase:

- no Rust executor changes
- no frontend approval UI changes

## Phase 4 Rust Executor Hardening

Phase 4 adds a minimal Rust-side permission layer so native Rust tool
execution cannot bypass the Python middleware by calling
`rust/crates/openjarvis-tools/src/executor.rs` or high-risk builtins directly.

The new policy lives in `rust/crates/openjarvis-security/src/permissions.rs`
and mirrors the Python permission model without a runtime Python dependency:

- `PermissionLevel`, `PermissionAction`, `PermissionRequest`, and
  `PermissionDecision` provide the same coarse read-only, safe action,
  confirmed execution, and dangerous concepts.
- Shell command classification uses the same dangerous-pattern labels as the
  Python middleware and writes JSONL audit records to the shared
  `~/.openjarvis/logs/permissions.log` path.
- `ToolExecutor.execute()` checks permissions before RBAC, taint checks,
  events, and builtin dispatch. Dangerous calls are blocked immediately, and
  confirmed-execution calls require an explicit internal
  `_permission_confirmed=true` marker.
- Rust `shell_exec`, `file_read`, and `file_write` also perform local
  defense-in-depth checks so direct rig/PyO3 builtin calls do not skip the
  dangerous-command, sensitive-file, protected-path, or traversal rules.
- Rust file policy helpers now include protected write roots and protected
  path parts aligned with Python's file policy.

This phase intentionally keeps the Rust policy self-contained and conservative
instead of introducing cross-language approval plumbing or redesigning the
native agent/tool subsystem.

## Phase 5 Approval Queue And Permissions UI

Phase 5 adds a small review surface for permission-gated work without changing
the conservative execution default from earlier phases.

- `src/openjarvis/security/approval_queue.py` stores confirmation-required
  tool calls as owner-only JSON records under `~/.openjarvis/approvals`.
  Records keep sanitized review metadata such as tool name, source, reason,
  argument keys, and a short command preview.
- Server streaming permission blocks now enqueue pending approvals and include
  the approval id in tool-call metadata.
- New API routes expose pending/all approvals, approve/deny mutations, and a
  recent permission audit feed under `/v1/security/...`.
- The Mission Control Permissions tab now renders a live approval queue with
  approve/deny controls and a permission audit lane, falling back to mock data
  when the local API is unavailable.

Approving a queued item records the user's decision for review and follow-up;
it does not silently resume or replay the blocked tool call.

## Learning Layer Phase 1

Phase 1 adds explicit, local-only feedback tracking to personalize ranking and
suggestions across Siri without introducing autonomous adaptation or cloud sync.

- `src/openjarvis/learning_layer/` owns the core feedback, preference, ranking,
  memory, models, and service logic. Learning state is persisted locally to
  `~/.openjarvis/state/learning/learning_state.json`.
- Users explicitly provide thumbs up/down feedback which adjust preference weights
  and component scores. No self-modifying prompts, no hidden adaptation.
- Feedback affects:
  - Memory multipliers (important topics get a relevance boost in searches)
  - Workflow ranking (preferred workflows move up the list)
  - Personalization defaults (learning layer aggregates preference weights)
- `LearningPanel.tsx` in Mission Control offers a dedicated section to view
  learning metrics, current preference weights, and manually reset, export, or
  import learning state.
- Data remains local and is explicitly triggered by user-driven ratings, ensuring
  maximum predictability and control over adaptation.

## Second Brain / Knowledge Vault Phase 1

Phase 1 turns Siri's memory layer into an Obsidian-compatible local knowledge
vault while keeping the existing SQLite `memories` table as the source of
truth — the vault never writes to it.

### Architecture

- `src/openjarvis/knowledge_vault/` is a self-contained Python package backed by
  a dedicated SQLite database (`~/.openjarvis/knowledge_vault.db`), completely
  separate from `siri_memory.db`.
- **`models.py`** — Pydantic contracts: `KnowledgeNote`, `NoteType`, `SourceLink`,
  `BacklinkRecord`, `VaultTag`, and all request/response models.
- **`notes.py`** — Low-level CRUD against the `vault_notes` table.  Supports FTS5
  full-text search with a `LIKE` fallback.
- **`daily_notes.py`** — Idempotent daily note helpers. `get_or_create_daily_note`
  is the canonical entry point; exactly one daily note per calendar date exists.
- **`backlinks.py`** — Parses `[[Note Title]]` wiki-link syntax from note content.
  Backlinks are stored in a `vault_backlinks` table with `ON DELETE CASCADE` to
  keep them consistent with note deletions.
- **`tags.py`** — Extracts `#hashtag` inline tags from note content and aggregates
  tag counts across the vault.
- **`markdown_export.py`** — Converts notes to Obsidian-compatible markdown with
  YAML frontmatter (`title`, `tags`, `type`, `created`, `updated`, `pinned`,
  `sources`).  Wiki-links are preserved as-is.
- **`service.py`** — `KnowledgeVaultService` coordinates all helpers.  Integration
  hooks: `from_memory(memory_id, memory_service)` imports a memory record as a
  note without touching the memory DB, `link_to_research(note_id, summary)`
  appends a research block.

### API

`knowledge_vault_routes.py` exposes 12 endpoints at `/v1/knowledge-vault/`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/notes` | List with filters (type, tag, pinned, project) |
| `POST` | `/notes` | Create note |
| `GET` | `/notes/{id}` | Get note (includes backlinks) |
| `PATCH` | `/notes/{id}` | Partial update |
| `DELETE` | `/notes/{id}` | Delete note |
| `POST` | `/notes/{id}/pin` | Pin / unpin |
| `GET` | `/notes/{id}/backlinks` | Backlinks to this note |
| `GET` | `/notes/{id}/export` | Markdown export (single note) |
| `GET` | `/daily` | Today's daily note (created if absent) |
| `POST` | `/daily` | Daily note for a specific date |
| `GET` | `/export` | Export full vault to disk |
| `GET` | `/search` | FTS5 full-text search |
| `GET` | `/tags` | Tag list with counts |
| `GET` | `/status` | Health + note count |

### Mission Control

A new **Knowledge Vault** tab (`knowledge-vault` section) in Mission Control
provides:
- Note list with type badge, inline tag chips, pin indicator, and date
- Inline create-note form (title + type picker)
- Full-text search bar
- Tag cloud for tag-based filtering
- Daily Note sidebar panel with content preview
- "By Type" breakdown sidebar
- "Export Vault" button with local path feedback

### Privacy

- All data stays on disk under `~/.openjarvis/`.
- No cloud sync path exists anywhere in the codebase.
- Export writes `.md` files locally; no upload endpoint is exposed.

### Deferred

The following were intentionally excluded from Phase 1:

- Cloud sync or remote backup
- Obsidian plugin or direct Obsidian integration (export is compatible, not coupled)
- Automatic note creation from conversations (user-explicit creation only)
- Graph view UI (deferred to Phase 2)
- Note version history / undo
- Filesystem watcher for vault directory

## Knowledge Graph Phase 1

Phase 1 turns the Knowledge Vault into a connected local second brain while
preserving the existing memory systems as independent sources of truth.

- `src/openjarvis/knowledge_graph/` owns local graph nodes, edges,
  relationship helpers, graph traversal, neighborhood search, project decision
  tracking, timeline events, typed models, and the coordinating service.
- The graph uses a dedicated SQLite database at
  `~/.openjarvis/knowledge_graph.db`. There is no cloud graph, no external DB,
  and no upload path.
- Graph nodes can represent notes, memories, research reports, sources,
  projects, decisions, timeline events, repo snapshots, code context, learning
  signals, and concepts. Nodes keep optional references back to their original
  local tables instead of replacing those systems.
- Graph edges support note-to-note links, memory-to-note links,
  research-to-source links, project decisions, implementation/dependency links,
  and general related/reference relationships.
- Project decisions are recorded as graph decision nodes, persisted decision
  records, project relationships, and timeline events.
- Timeline events are first-class local records and can be attached to nodes or
  projects for Mission Control chronology.
- Semantic neighborhood search is local-only: it combines SQLite FTS/LIKE
  matching, deterministic token overlap, pinned-root boosts, and graph
  proximity. It does not download embedding models.
- Graph traversal performs bounded breadth-first walks over local edges and
  returns connected nodes, edges, timeline records, and pinned graph roots.
- Pinned graph roots mark durable entry points for the second brain without
  changing Knowledge Vault pinned notes or structured memory pinned records.
- Integration hooks read from Knowledge Vault, Memory, Research, Repo Index,
  Coding Assistant, and Learning Layer services when supplied, but the graph
  augments those records rather than writing back to them.
- `/v1/knowledge-graph` exposes local APIs for status, nodes, edges, roots,
  traversal, neighborhood search, note-note links, memory-note links,
  research-source links, project decisions, and timeline events.
- Mission Control's Knowledge Vault tab now includes a Graph panel with root
  nodes, relationship viewer, timeline view, connected nodes, and a
  neighborhood explorer.

Deferred work remains intentionally untouched in this phase:

- no cloud graph or hosted sync
- no external graph database
- no autonomous graph mutation from conversations
- no replacement of existing memory, vault, research, or repo-index systems

## Brain UI Phase 1

Phase 1 begins turning Mission Control's Knowledge Vault graph experience into
a Siri brain interface while preserving the Knowledge Graph backend and the
existing Knowledge Vault workflows.

- The Knowledge Vault tab keeps note creation, note search, tag filtering,
  pinning, deletion, daily notes, type breakdowns, and local markdown export.
- The graph panel is now a visual Brain Graph surface backed by the existing
  `/v1/knowledge-graph` status, roots, timeline, neighborhood, and traversal
  endpoints. It does not introduce mock graph data or new backend contracts.
- Pinned graph roots are shown as durable entry nodes, the selected focus node
  expands into connected memories/notes, and relationship edges render between
  visible graph nodes with relationship labels when available.
- Timeline events are included as secondary nodes along the brain surface and
  connect back to visible graph nodes when the event payload includes a
  `node_id`.
- Search remains available but is visually secondary to the brain map; search
  results become selectable graph nodes rather than replacing Knowledge Vault
  note search.
- Text-heavy relationship, focus, and timeline details remain in compact side
  panels so the first read of the experience is the connected graph itself.
- Voice-first direction is preserved for future phases, but text inputs remain
  intact for note creation, vault search, and graph neighborhood search.

Deferred work remains intentionally untouched in this phase:

- no backend Knowledge Graph API changes
- no removal of Knowledge Vault features
- no voice-only graph interaction
- no autonomous graph mutation
- no replacement of text inputs

## Brain UI Phase 2

Phase 2 moves Mission Control further toward an AI-brain-first Knowledge Vault
experience while keeping all current Knowledge Graph APIs and existing vault
tools intact.

- The Brain Graph is now ordered as the primary visual surface in the Knowledge
  Vault tab, ahead of note creation and note-list tooling.
- The graph canvas is larger and remains backed by the existing graph status,
  root, timeline, neighborhood search, and traversal responses.
- Hovering, focusing, or clicking graph nodes reveals memory/thought details in
  the graph surface, including node type, source, text preview, updated time,
  visible link count, and matching timeline context when available.
- Clicking graph nodes still traverses the existing backend graph endpoint and
  updates the selected focus node without introducing fake local graph
  behavior.
- Relationship details now show relationship type, source node, target node,
  edge weight, and timeline context where the visible graph data provides it.
- Text-heavy Focus, Relationships, Timeline, and Timeline Nodes panels are
  secondary collapsible sections beside the graph.
- Text inputs for note creation, note search, and graph neighborhood search
  remain available for this phase.

Deferred work remains intentionally untouched in this phase:

- no Knowledge Graph backend or API contract changes
- no removal of current Knowledge Vault panels or workflows
- no voice-only controls
- no autonomous graph updates
- no fake graph data or mock backend behavior

## Brain UI Phase 3

Phase 3 prepares Mission Control for a future AI-brain-only main interface by
adding an explicit brain-first view state while preserving the current
Knowledge Vault and Mission Control affordances.

- The Knowledge Vault header now includes a Brain First toggle. The default
  layout remains available, and no Mission Control tabs are removed.
- In Brain First mode, the Brain Graph becomes the dominant surface with a
  larger full-width canvas and the same existing Knowledge Graph status,
  roots, timeline, neighborhood search, and traversal APIs.
- Graph hover, focus, keyboard, and click inspection continue to reveal
  memory/thought details without creating local fake graph behavior.
- Graph controls, root chips, note creation, note lists, and vault context
  panels move into secondary collapsible sections when Brain First mode is
  active.
- Relationship and timeline detail panels remain available as collapsible
  secondary context instead of competing with the graph as the primary read.
- Keyboard and text inputs remain available through the collapsible controls
  for note creation, vault search, and graph neighborhood search.

Deferred work remains intentionally untouched in this phase:

- no Knowledge Graph backend or API contract changes
- no deletion of existing Mission Control tabs
- no removal of Knowledge Vault note workflows
- no voice-only control layer
- no autonomous graph mutation
- no fake backend behavior or mock graph responses

### Verification Notes

TypeScript check (`npx tsc --noEmit --pretty false --extendedDiagnostics`) consistently hangs
and does not complete within 55 seconds when run from the project root. This appears to be a
pre-existing issue unrelated to Phase 3 changes (the two modified files contain no new type
errors visible in the diff). Phase 3 was committed without a passing tsc run; the hang should
be investigated separately.

## Voice Control Phase 1

Phase 1 establishes the integration architecture for future macOS push-to-talk voice control
without removing any existing keyboard or text input.

### Architecture

```
Fn key (held)
    └── FnKeyPushToTalkListener.on_press()          [hotkeys/ — deferred]
            └── POST /v1/voice/ptt/start

Fn key (released)
    └── FnKeyPushToTalkListener.on_release()        [hotkeys/ — deferred]
            └── POST /v1/voice/ptt/stop
            └── POST /v1/voice/ptt/transcribe-latest
                    └── LocalVoiceTranscriber        [local whisper_cpp / faster-whisper]
                    └── VoicePermissionGate.check_start()
                    └── VoiceIntentPreview           [classify: dictation / question / action]
            └── (user reviews preview)
            └── POST /v1/voice/ptt/dispatch          [Phase 1 — new endpoint]
                    └── AgentSendTool.execute(agent_id, message=transcript)
                            └── existing orchestrator / agent message flow
```

### What Phase 1 adds

- `src/openjarvis/hotkeys/__init__.py` — `HotkeyListener` abstract base and
  `FnKeyPushToTalkListener` stub. Raises `NotImplementedError` on `start()`; exists
  so the rest of the codebase can import and type-hint against the interface.

- `POST /v1/voice/ptt/dispatch` — bridges an approved transcript to the existing
  `AgentSendTool` orchestrator entry point (`/v1/agents/{agent_id}/message`).
  Returns `dispatched: false` with a reason when no agent is addressable, rather
  than raising an error, so callers can surface the state gracefully.

### Invariants preserved

- No always-on or background listening; push-to-talk only.
- No cloud speech APIs; transcription is local (whisper_cpp / faster-whisper).
- No removal of keyboard or text inputs.
- No microphone access without explicit user PTT action.
- Permission gate already in place via `VoicePermissionGate`.

### Deferred work

The following is explicitly out of scope for Phase 1:

- CGEventTap / pynput macOS Fn key listener (requires Accessibility permission prompt)
- Configurable hotkey (user-settable key combo)
- Actual microphone recording integration wiring to the hotkey
- Transcription backend installation UX
- TTS / speech output for responses
- macOS microphone permission prompting on first use
- Frontend voice-only mode or UI controls
- Cross-platform hotkey support

## Voice Control Phase 2

Phase 2 adds the explicit session state machine and approval gate, tightening
the API contract without wiring real audio capture yet.

### Explicit session states

```
idle → listening → transcribing → awaiting_approval → dispatching → completed
                ↘ failed                            ↘ idle (cancel)
```

All states are defined in `VoiceSessionState` (str enum).  `VoiceSessionFSM`
validates transitions and raises `VoiceSessionFSMError` on illegal moves.

### New API surface

| Endpoint | Purpose |
|---|---|
| `POST /v1/voice/ptt/submit-transcript` | Accept a manually-supplied transcript; return intent preview at `awaiting_approval` state without requiring a local transcription backend |
| `POST /v1/voice/ptt/dispatch` | Unchanged path, now requires `approved: true`; returns 403 with `approval_required` status if omitted |

### Approval gate

`/dispatch` now returns HTTP 403 when `approved` is absent or false, ensuring
no transcript reaches the orchestrator without an explicit caller confirmation.
The error body includes `status: "approval_required"` and a human-readable
message pointing to the intent preview.

### What Phase 2 adds

- `src/openjarvis/voice/session_fsm.py` — `VoiceSessionState`, `VoiceSessionFSM`,
  `VoiceSessionFSMError`
- `src/openjarvis/voice/__init__.py` — exports for the three new types
- `src/openjarvis/server/api_routes.py` — `submit-transcript` stub,
  `VoiceSubmitTranscriptRequest`, approval gate on `/dispatch`
- `tests/voice/test_session_fsm.py` — 12 FSM transition tests
- `tests/server/test_voice_routes.py` — approval gate, mocked-agent dispatch,
  submit-transcript, empty-transcript cases

### Invariants preserved

- No always-on or background listening.
- No cloud speech APIs.
- No removal of keyboard or text inputs.
- No microphone access without explicit PTT action.

### Deferred work (unchanged from Phase 1)

- Fn key / CGEventTap listener
- Actual microphone recording wired to hotkey
- whisper.cpp / faster-whisper transcription backend UX
- Local TTS output
- macOS Accessibility and Microphone permission prompting
- Frontend voice-only mode
