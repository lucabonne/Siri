# CLI Reference

OpenJarvis provides a command-line interface through the `jarvis` command. Built on [Click](https://click.palletsprojects.com/), it offers subcommands for querying models, managing memory, running benchmarks, and serving an OpenAI-compatible API.

## Global Options

```bash
jarvis --version   # Print the OpenJarvis version
jarvis --help      # Show top-level help with all subcommands
```

## `jarvis init`

Detect local hardware (CPU, GPU, RAM) and generate a configuration file at `~/.openjarvis/config.toml`.

```bash
jarvis init           # Interactive — refuses to overwrite existing config
jarvis init --force   # Overwrite existing config without prompting
```

| Option    | Description                                   |
|-----------|-----------------------------------------------|
| `--force` | Overwrite existing configuration without prompting |

The `init` command auto-detects:

- **Platform** (Linux, macOS, Windows)
- **CPU** brand and core count
- **RAM** in GB
- **GPU** vendor, model, VRAM, and count (via `nvidia-smi`, `rocm-smi`, or `system_profiler`)

Based on the detected hardware, it recommends an appropriate inference engine and writes a pre-configured TOML file.

**Example output:**

```
Detecting hardware...
  Platform : linux
  CPU      : AMD Ryzen 9 7950X (32 cores)
  RAM      : 64 GB
  GPU      : NVIDIA RTX 4090 (24.0 GB VRAM, x1)

Config written successfully.
```

---

## `jarvis ask`

Send a query to the inference engine (directly or through an agent) and print the response.

```bash
jarvis ask "What is the capital of France?"
```

### Options

| Option                        | Type    | Default    | Description                                           |
|-------------------------------|---------|------------|-------------------------------------------------------|
| `-m`, `--model MODEL`         | string  | auto       | Model to use for inference                             |
| `-e`, `--engine ENGINE`       | string  | auto       | Engine backend (ollama, vllm, llamacpp, etc.)          |
| `-t`, `--temperature TEMP`    | float   | `0.7`      | Sampling temperature                                   |
| `--max-tokens N`              | int     | `1024`     | Maximum tokens to generate                             |
| `--json`                      | flag    | off        | Output raw JSON result instead of plain text           |
| `--no-stream`                 | flag    | off        | Disable streaming (synchronous mode)                   |
| `--no-context`                | flag    | off        | Disable memory context injection                       |
| `-a`, `--agent AGENT`         | string  | none       | Agent to use (`simple`, `orchestrator`)                |
| `--tools TOOLS`               | string  | none       | Comma-separated tool names to enable                   |

### Direct Mode vs Agent Mode

**Direct mode** (default) sends the query straight to the inference engine:

```bash
jarvis ask "Explain quantum computing"
```

**Agent mode** routes the query through an agent that can use tools and manage multi-turn interactions:

```bash
jarvis ask --agent orchestrator "What is 2+2?"
jarvis ask --agent orchestrator --tools calculator,think "Calculate sqrt(144) + 3^2"
jarvis ask --agent simple "Hello"
```

### Usage Examples

```bash
# Basic query
jarvis ask "What is machine learning?"

# Specify a model
jarvis ask -m qwen3:8b "Summarize this concept"

# Use the orchestrator agent with tools
jarvis ask --agent orchestrator --tools calculator "What is 15% of 340?"

# Get JSON output
jarvis ask --json "Hello"

# Disable memory context injection
jarvis ask --no-context "Tell me about Python"

# Set maximum token generation
jarvis ask --max-tokens 2048 "Write a detailed essay about AI"
```

### JSON Output Format

When using `--json` in **direct mode**, the output includes:

```json
{
  "content": "The response text...",
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 85,
    "total_tokens": 97
  }
}
```

When using `--json` in **agent mode**, the output includes:

```json
{
  "content": "The response text...",
  "turns": 3,
  "tool_results": [
    {
      "tool_name": "calculator",
      "content": "51.0",
      "success": true
    }
  ]
}
```

---

## `jarvis model`

Manage and inspect language models available on running engines.

### `jarvis model list`

List all models available from running inference engines, displayed as a Rich table with model parameters, context length, and VRAM requirements.

```bash
jarvis model list
```

**Example output:**

```
           Available Models
┌─────────┬────────────────┬────────┬─────────┬──────┐
│ Engine  │ Model          │ Params │ Context │ VRAM │
├─────────┼────────────────┼────────┼─────────┼──────┤
│ ollama  │ qwen3:8b       │ 8B     │ 32,768  │ 6GB  │
│ ollama  │ llama3.2:3b    │ 3B     │ 8,192   │ 3GB  │
└─────────┴────────────────┴────────┴─────────┴──────┘
```

### `jarvis model info <model>`

Show detailed information about a specific model.

```bash
jarvis model info qwen3:8b
```

**Example output:**

```
┌─ Qwen 3 8B ──────────────────────────────┐
│ Model ID:     qwen3:8b                    │
│ Name:         Qwen 3 8B                   │
│ Parameters:   8B                          │
│ Context:      32,768                      │
│ Quantization: none                        │
│ Min VRAM:     6GB                         │
│ Engines:      ollama, vllm                │
│ Provider:     Alibaba                     │
│ API Key:      not required                │
└───────────────────────────────────────────┘
```

### `jarvis model pull <model>`

Download a model via Ollama. Shows a progress bar during download.

```bash
jarvis model pull qwen3:8b
```

!!! note
    The `pull` command requires a running Ollama instance. It connects to the Ollama API at the host configured in your `config.toml`.

---

## `jarvis pearl`

Access Pearl's native node, wallet, and RPC tools from the OpenJarvis CLI.

```bash
jarvis pearl doctor
jarvis pearl node -- <pearld args>
jarvis pearl wallet -- <oyster args>
jarvis pearl ctl -- <prlctl args>
jarvis pearl address
```

All Pearl wrapper commands use the `jarvis pearl <command>` shape. The
pass-through commands map to Pearl's native binaries:

| OpenJarvis command | Pearl binary | Use |
|--------------------|--------------|-----|
| `jarvis pearl doctor` | n/a | Check whether `pearld`, `oyster`, and `prlctl` are discoverable |
| `jarvis pearl node` | `pearld` | Run the Pearl full node |
| `jarvis pearl wallet` | `oyster` | Run the Oyster wallet daemon |
| `jarvis pearl ctl` | `prlctl` | Query Pearl node or wallet RPC |
| `jarvis pearl address` | `prlctl --wallet getnewaddress` | Generate a wallet address from Oyster |

Use `PEARL_HOME=/path/to/pearl` or `--pearl-home /path/to/pearl` if Pearl's
`bin/` directory is not on `PATH`. See the [Pearl CLI guide](pearl.md) for
examples.

---

## `jarvis memory`

Manage the document memory store for retrieval-augmented generation.

### `jarvis memory index <path>`

Index documents from a file or directory into the memory store.

```bash
jarvis memory index ./docs/
jarvis memory index ./notes.md
jarvis memory index ./data/ --chunk-size 256 --chunk-overlap 32
jarvis memory index ./docs/ --backend sqlite
```

| Option                      | Type   | Default | Description                          |
|-----------------------------|--------|---------|--------------------------------------|
| `--backend`, `-b`           | string | config  | Override the default memory backend  |
| `--chunk-size`              | int    | `512`   | Chunk size in tokens                 |
| `--chunk-overlap`           | int    | `64`    | Overlap between chunks in tokens     |

The ingestion pipeline supports text, markdown, code files, and PDF (with `pdfplumber` installed). Binary files and hidden directories are automatically skipped.

### `jarvis memory search <query>`

Search the memory store for relevant document chunks.

```bash
jarvis memory search "machine learning basics"
jarvis memory search -k 10 "neural networks"
jarvis memory search --backend faiss "embeddings"
```

| Option             | Type   | Default | Description                          |
|--------------------|--------|---------|--------------------------------------|
| `--top-k`, `-k`    | int    | `5`     | Number of results to return          |
| `--backend`, `-b`  | string | config  | Override the default memory backend  |

Results are displayed in a table with rank, score, source file, and a content preview.

### `jarvis memory stats`

Show memory store statistics including document count and database size.

```bash
jarvis memory stats
jarvis memory stats --backend sqlite
```

| Option             | Type   | Default | Description                          |
|--------------------|--------|---------|--------------------------------------|
| `--backend`, `-b`  | string | config  | Override the default memory backend  |

---

## `jarvis telemetry`

Query and manage inference telemetry data stored in SQLite.

### `jarvis telemetry stats`

Show aggregated telemetry statistics including total calls, tokens, cost, and latency, broken down by model and engine.

```bash
jarvis telemetry stats
jarvis telemetry stats -n 5    # Show top 5 models
```

| Option          | Type | Default | Description                   |
|-----------------|------|---------|-------------------------------|
| `-n`, `--top`   | int  | `10`    | Number of top models to show  |

### `jarvis telemetry export`

Export raw telemetry records in JSON or CSV format.

```bash
jarvis telemetry export                          # JSON to stdout
jarvis telemetry export --format csv             # CSV to stdout
jarvis telemetry export --format json -o data.json  # JSON to file
jarvis telemetry export -f csv -o metrics.csv    # CSV to file
```

| Option                | Type   | Default  | Description                     |
|-----------------------|--------|----------|---------------------------------|
| `-f`, `--format`      | choice | `json`   | Output format: `json` or `csv`  |
| `-o`, `--output`      | path   | stdout   | Output file path                |

### `jarvis telemetry clear`

Delete all telemetry records from the database.

```bash
jarvis telemetry clear         # Interactive confirmation
jarvis telemetry clear --yes   # Skip confirmation
```

| Option         | Type | Default | Description                   |
|----------------|------|---------|-------------------------------|
| `-y`, `--yes`  | flag | off     | Skip confirmation prompt      |

!!! warning
    This permanently deletes all stored telemetry data. Use `--yes` to skip the confirmation prompt in automated scripts.

---

## `jarvis bench`

Run inference benchmarks against a running engine.

### `jarvis bench run`

Execute benchmarks and report results.

```bash
jarvis bench run                               # Run all benchmarks, 10 samples
jarvis bench run -n 20                         # 20 samples per benchmark
jarvis bench run -b latency                    # Only the latency benchmark
jarvis bench run -b throughput -n 50 --json    # Throughput, 50 samples, JSON output
jarvis bench run -o results.jsonl              # Write JSONL results to file
jarvis bench run -m qwen3:8b -e ollama         # Specific model and engine
```

| Option                     | Type   | Default | Description                              |
|----------------------------|--------|---------|------------------------------------------|
| `-m`, `--model MODEL`      | string | auto    | Model to benchmark                       |
| `-e`, `--engine ENGINE`    | string | auto    | Engine backend                           |
| `-n`, `--samples N`        | int    | `10`    | Number of samples per benchmark          |
| `-b`, `--benchmark NAME`   | string | all     | Specific benchmark to run                |
| `-o`, `--output PATH`      | path   | none    | Write JSONL results to file              |
| `--json`                   | flag   | off     | Output JSON summary to stdout            |

Available benchmarks:

- **latency** -- Measures per-call inference latency (mean, p50, p95, min, max)
- **throughput** -- Measures tokens-per-second throughput

---

## `jarvis channel`

Manage messaging channels for multi-platform communication. Channels connect directly to platform APIs (Telegram, Discord, Slack, etc.) -- no gateway required.

### `jarvis channel list`

List registered channel backends and their connection status.

```bash
jarvis channel list
```

### `jarvis channel send`

Send a message to a specific channel.

```bash
jarvis channel send slack "Hello from Jarvis!"
jarvis channel send discord "Build complete"
```

| Argument    | Type   | Description                          |
|-------------|--------|--------------------------------------|
| `TARGET`    | string | Channel name to send to              |
| `MESSAGE`   | string | Message content                      |

### `jarvis channel status`

Show connection status for configured channels.

```bash
jarvis channel status
```

!!! note "Channel Dependencies"
    Each channel requires its platform-specific credentials (bot tokens, API keys) configured in the `[channel.<platform>]` section of your config. See [Configuration](../getting-started/configuration.md) for details.

---

## `jarvis serve`

Start an OpenAI-compatible API server.

```bash
jarvis serve                                 # Default host/port from config
jarvis serve --port 8000                     # Custom port
jarvis serve --host 0.0.0.0 --port 9000      # Bind to all interfaces
jarvis serve --model qwen3:8b                # Specify default model
jarvis serve --agent orchestrator            # Route requests through an agent
```

| Option                   | Type   | Default | Description                              |
|--------------------------|--------|---------|------------------------------------------|
| `--host HOST`            | string | config  | Bind address                             |
| `--port PORT`            | int    | config  | Port number                              |
| `-e`, `--engine ENGINE`  | string | auto    | Engine backend                           |
| `-m`, `--model MODEL`    | string | config  | Default model for inference              |
| `-a`, `--agent AGENT`    | string | none    | Agent for non-streaming requests         |

!!! note "Server Dependencies"
    The `serve` command requires the server extra:

    ```bash
    uv sync --extra server
    ```

    This installs FastAPI, uvicorn, and related dependencies.

### API Endpoints

The server exposes the following OpenAI-compatible endpoints:

| Method | Path                     | Description                    |
|--------|--------------------------|--------------------------------|
| POST   | `/v1/chat/completions`   | Chat completions (streaming & non-streaming) |
| GET    | `/v1/models`             | List available models          |
| GET    | `/health`                | Health check                   |
| GET    | `/v1/channels`           | List available messaging channels    |
| POST   | `/v1/channels/send`      | Send a message to a channel          |
| GET    | `/v1/channels/status`    | Channel bridge connection status     |

**Example with curl:**

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3:8b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

When an agent is configured (e.g., `--agent orchestrator`), non-streaming requests are routed through the agent with access to all registered tools. For tool-capable agents (`orchestrator`, `react`, `openhands`), all registered tools are automatically loaded and made available.

---

## `jarvis voice`

Run the explicit local/manual voice flow against an already running OpenJarvis
API server. This is the current safe bridge before global hotkey or always-on
activation: a terminal command can record or transcribe only when you invoke
it, while OpenJarvis keeps the same preview, approval, dispatch, and cancel API
gates.

```bash
jarvis voice submit "open notes"                         # Preview only
jarvis voice submit "open notes" --approve-dispatch      # Preview, then dispatch
jarvis voice submit "run tests" --agent-id agent-123 --approve-dispatch
jarvis voice record-local --duration 2                   # Local WAV only
jarvis voice record-local --recorder sounddevice --duration 2
jarvis voice mic-smoke --recorder sounddevice --duration 1
jarvis voice mic-smoke --recorder macos --duration 1 --keep-file
jarvis voice mic-transcribe-smoke --duration 1 --recorder sounddevice --adapter faster-whisper
jarvis voice mic-preview --duration 1 --recorder sounddevice --adapter faster-whisper
jarvis voice mic-run --duration 1 --recorder sounddevice --adapter faster-whisper
jarvis voice mic-run --duration 1 --recorder sounddevice --adapter faster-whisper --approve-dispatch
jarvis voice mic-run --duration 1 --recorder sounddevice --adapter faster-whisper --approve-dispatch --speak-result
jarvis voice transcribe-file ./clip.wav --adapter faster-whisper
jarvis voice capture-preview --duration 2 --adapter faster-whisper
jarvis voice run-local --duration 2 --adapter faster-whisper
jarvis voice run-local --duration 2 --adapter faster-whisper --approve-dispatch
jarvis voice run-local --duration 2 --adapter faster-whisper --approve-dispatch --speak-result
jarvis voice doctor                                     # Safe local setup diagnostics
jarvis voice hotkey-bridge --adapter faster-whisper      # Print preview-only mic-run command
jarvis voice hotkey-bridge --format hammerspoon          # Print disabled helper example
jarvis voice hotkey-bridge --write-hammerspoon ./openjarvis-voice.lua
jarvis voice hotkey-bridge --validate-hammerspoon ./openjarvis-voice.lua
jarvis voice speak "preview complete"                    # Explicit local TTS only
jarvis voice logs                                        # Show recent local voice events
jarvis voice logs --event dispatch_result --json         # Filter local events as JSON
jarvis voice logs --approval-dispatch-only --limit 10
jarvis voice logs --export ./voice-events.jsonl          # Export filtered events as JSONL
jarvis voice logs --export ./voice-events.json           # Export filtered events as JSON
jarvis voice logs --clear --dry-run                      # Preview local log cleanup
jarvis voice logs --clear --confirm                      # Clear local voice log events
jarvis voice logs --clear-before 2026-01-01 --confirm    # Remove older local events
jarvis voice status
jarvis voice cancel
```

| Command                 | Description                                      |
|-------------------------|--------------------------------------------------|
| `voice submit TEXT`     | POST to `/v1/voice/ptt/submit-transcript` and show the intent preview/session state |
| `voice submit --approve-dispatch` | Explicitly approve and then POST to `/v1/voice/ptt/dispatch` |
| `voice record-local --duration N` | Write and intentionally retain a local WAV file; defaults to the dev silent recorder |
| `voice record-local --recorder sounddevice --duration N` | Use the optional real local microphone adapter for a bounded 0.1-30 second recording and intentionally retain the printed WAV |
| `voice mic-smoke --duration N` | Record with an explicitly selected/configured real microphone backend, inspect WAV metadata, and delete the file unless `--keep-file` is passed |
| `voice mic-transcribe-smoke --duration N` | Record with a selected/configured real microphone backend, transcribe locally, print WAV/transcript metadata and text, then delete the WAV unless `--keep-file` is passed; never submit, dispatch, or speak |
| `voice mic-preview --duration N` | Record with a selected/configured real microphone backend, transcribe locally, submit to `/v1/voice/ptt/submit-transcript`, print preview/session state, and delete the WAV unless `--keep-file` is passed; never dispatch or speak |
| `voice mic-run --duration N` | Run the bounded real-microphone preview path and delete the WAV unless `--keep-file` is passed; dispatch requires `--approve-dispatch`, and speech additionally requires `--speak-result` |
| `voice transcribe-file AUDIO` | Transcribe an existing local audio file with a local adapter and print the transcript only |
| `voice capture-preview --duration N` | Record a local WAV, transcribe it locally, POST the transcript to `/v1/voice/ptt/submit-transcript`, and print the preview only |
| `voice run-local --duration N` | Record, transcribe, submit preview, and print session state; dispatch and TTS require separate opt-in flags |
| `voice doctor`        | Inspect voice, recorder, microphone configuration, and local dependencies without probing hardware, recording, dispatching, speaking, or starting hotkeys |
| `voice hotkey-bridge` | Print or write a disabled macOS bridge example, or statically validate one with `--validate-hammerspoon PATH`, around the bounded preview-only `mic-run` pipeline |
| `voice speak TEXT`     | Speak text through an explicit local speech-output adapter; defaults to macOS `say` when available |
| `voice logs`           | Inspect, export, or explicitly clean up local structured voice command events |
| `voice status`          | GET `/v1/voice/ptt/status`, including the same read-only voice stack fields Mission Control uses |
| `voice cancel`          | POST `/v1/voice/ptt/cancel`                      |

The recording command family progresses without changing existing command
behavior:

| Command | Recording | Local transcription | Preview submission | Dispatch |
|---------|-----------|---------------------|--------------------|----------|
| `record-local` | Local recorder (`dev-silent`, `macos`, or `sounddevice`) | No | No | No |
| `mic-smoke` | Real microphone only; validates WAV | No | No | No |
| `mic-transcribe-smoke` | Real microphone only | Yes | No | No |
| `mic-preview` | Real microphone only | Yes | Yes | Never |
| `mic-run` | Real microphone only | Yes | Yes | Only with `--approve-dispatch` |
| `run-local` | Local recorder (`dev-silent`, `macos`, or `sounddevice`) | Yes | Yes | Only with `--approve-dispatch` |

Speech is never automatic. For `mic-run` and `run-local`, it additionally
requires `--speak-result` after approved dispatch.

`voice hotkey-bridge` is print-only unless `--write-hammerspoon PATH` is passed.
That option writes a disabled example to a new `.lua` file whose parent already
exists; it refuses existing files and the active `~/.hammerspoon/init.lua`.
The active example command uses the bounded real-microphone `voice mic-run`
preview path and omits both `--approve-dispatch` and `--speak-result`.
Approved-dispatch and speech variants are present only as commented manual
opt-in examples. OpenJarvis does not install Hammerspoon or the file, bind
Fn/F18, start a listener, request Accessibility permission, or execute any
generated command.

`--validate-hammerspoon PATH` reads a generated/example `.lua` file as text
only. It refuses the active `~/.hammerspoon/init.lua` and requires a disabled
bridge whose active command is preview-only `jarvis voice mic-run`, has a
0.1-30 second duration, and selects `macos` or `sounddevice`. It rejects active
`--approve-dispatch`, `--speak-result`, Hammerspoon install-path mutation, and
LaunchAgent markers. Validation does not execute Lua or commands from the file,
install anything, start listeners, request permissions, dispatch, or speak.

Current safe workflow:

1. `jarvis voice doctor`
2. `jarvis voice mic-smoke --recorder sounddevice --duration 1`
3. Configure a local transcription backend/model with
   `[voice_control].transcription_adapter` and `[voice_control].model_path`, or
   pass `--adapter` on transcription commands.
4. `jarvis voice mic-transcribe-smoke --duration 1 --recorder sounddevice --adapter faster-whisper`
5. `jarvis voice mic-preview --duration 1 --recorder sounddevice --adapter faster-whisper`
6. `jarvis voice record-local --duration 2`
7. `jarvis voice transcribe-file ./voice-sample.wav --adapter faster-whisper`
8. `jarvis voice capture-preview --duration 2 --adapter faster-whisper`
9. `jarvis voice run-local --duration 2 --adapter faster-whisper`
10. `jarvis voice logs`

Implemented safe local/manual behavior:

- `submit`, `status`, and `cancel` exercise the preview/approval/session API
  gates with typed transcripts.
- `record-local`, `mic-smoke`, `mic-transcribe-smoke`, `mic-preview`,
  `transcribe-file`, `capture-preview`, and `run-local` run only after an
  explicit terminal command and fixed duration or existing file input.
- `doctor` and Mission Control status/readiness views inspect setup without
  starting capture, hotkeys, dispatch, speech, model downloads, or settings
  mutation.
- `logs` inspects, exports, or confirmation-cleans local structured voice events
  without storing raw audio.

Optional configured behavior:

- `[voice_control]` can set safe defaults for local adapter/model selection,
  record duration, recorder selection, API base URL, explicit speech output,
  printed hotkey bridge command formatting, and local event logging.
- `--approve-dispatch` explicitly calls `/v1/voice/ptt/dispatch` after preview
  and sends `approved=true`.
- `voice speak` and `run-local --approve-dispatch --speak-result` explicitly use
  the selected local speech-output adapter.
- `--recorder macos` explicitly uses local macOS recording tools and may request
  macOS **Microphone** permission.

Deferred real activation behavior:

- Always-on listening, wake words, Fn/global hotkey capture, live Hammerspoon or
  Swift helper installation, voice-only mode, approval bypass, automatic
  dispatch, and automatic speech playback remain out of scope.
- Mission Control remains read-only for voice setup and does not run CLI
  commands, mutate settings, request permissions, export/clean logs, approve,
  dispatch, or speak.

These commands do not listen in the background, capture Fn hotkeys, call a cloud
speech API, automatically dispatch a transcript, or automatically play TTS for
results. Speech output runs only through explicit commands/flags such as
`voice speak` or `voice run-local --speak-result`. `voice record-local` and
`voice capture-preview` both have an explicit or configured duration stop
condition. When `voice record-local` resolves to a real microphone backend, its
duration is limited to 0.1-30 seconds and its printed WAV is intentionally
retained. All four `mic-*` commands require an explicit bounded 0.1-30 second
duration and delete their temporary WAV by default; only `--keep-file` retains
it.
`voice capture-preview` manually chains local recording, local transcription,
and the existing preview endpoint, then stops before dispatch. Text input
remains available; dispatch is skipped unless `--approve-dispatch` is present on
`voice submit` or `voice run-local`.

`voice mic-smoke --duration N` is a narrower real-microphone check. Its duration
must be supplied explicitly and must be between 0.1 and 30 seconds. It accepts
only the `macos` or `sounddevice` recorder from `--recorder` or
`[voice_control].default_recorder`; the default `dev-silent` recorder is not a
valid microphone smoke backend. The command records a local WAV, verifies basic
non-empty WAV metadata, and deletes the file by default. Pass `--keep-file` to
retain it. It never transcribes, submits, approves, dispatches, or speaks.

`voice mic-transcribe-smoke --duration N` explicitly records from only the
`macos` or `sounddevice` real microphone backend, validates the WAV, and uses an
explicit or `[voice_control].transcription_adapter` local adapter with the
configured `[voice_control].model_path` or `[speech].model`. It prints WAV and
transcription metadata plus transcript text. The WAV is deleted by default,
including when inspection or transcription fails; `--keep-file` retains it.
The command has no API, approval, dispatch, hotkey, or speech step.

`voice mic-preview --duration N` uses the same bounded real-microphone and local
transcription requirements, then submits the transcript only to
`/v1/voice/ptt/submit-transcript` and prints the returned preview/session state.
It deletes the temporary WAV by default after success or an expected failure;
`--keep-file` retains it. It exposes no dispatch or speech option, never calls
`/dispatch`, and leaves the existing approval gate unchanged.

`voice mic-run --duration N` extends that bounded real-microphone path through
the existing optional approval gate. Its default behavior records, transcribes
locally, submits only to `/v1/voice/ptt/submit-transcript`, prints the
preview/session state, and deletes the WAV. It calls the existing
`/v1/voice/ptt/dispatch` endpoint only with `--approve-dispatch`, sending
`approved=true`. `--speak-result` is rejected without that dispatch flag and is
the only way for this command to speak. `--keep-file` is the only way to retain
the WAV. The command does not start a hotkey listener or background capture.

`voice doctor --json` and `/v1/voice/ptt/status` expose this same recording
policy, including real-recorder requirements, duration bounds, default
temporary-WAV cleanup, explicit `--keep-file` retention, dispatch approval, and
dispatch-gated speech. The checks are configuration-only and never open the
microphone.

`voice run-local --duration N` is the explicit manual end-to-end local pipeline:
it records a local WAV, transcribes with the selected/configured local adapter,
submits the transcript to `/v1/voice/ptt/submit-transcript`, and prints the
preview/session state. By default it stops there. It calls `/dispatch` only when
`--approve-dispatch` is present, and it speaks the dispatch result only when
`--speak-result` is also present. Passing `--speak-result` without
`--approve-dispatch` is rejected so speech playback cannot imply dispatch.

Safe local defaults can be set in `~/.openjarvis/config.toml`:

```toml
[voice_control]
transcription_adapter = "faster-whisper"   # or "whisper.cpp"; empty disables it
model_path = "base"                        # model name or existing local path
default_record_duration = 2.0              # 0 keeps --duration required
default_recorder = "dev-silent"            # dev-silent, macos, or sounddevice
default_api_base_url = "http://127.0.0.1:8000"
speech_output_adapter = "macos-say"        # used only by speak/--speak-result
speech_voice = "Alex"
speech_rate = 180
hotkey_bridge_format = "command"           # command, hammerspoon, or json
hotkey_bridge_jarvis_bin = "jarvis"
hotkey_bridge_recorder = "macos"
hotkey_bridge_input_device = ":0"
hotkey_bridge_session_id = ""
voice_logs_enabled = true
voice_logs_path = "~/.openjarvis/voice-events.jsonl"
voice_logs_include_full_transcripts = false
voice_logs_preview_chars = 80
```

CLI flags and `OPENJARVIS_BASE_URL` override these config values. This section
does not enable listening, global/Fn hotkey capture, approval bypass,
auto-dispatch, or automatic speech playback. Dispatch still requires
`--approve-dispatch`; speech still requires `voice speak` or
`voice run-local --speak-result`.

`voice logs` reads recent JSONL events from the local `voice_logs_path`.
Logging is local-only and records command activity such as submit, status,
cancel, transcribe-file, record-local, mic-smoke, mic-transcribe-smoke,
mic-preview, mic-run, capture-preview, run-local, speak, doctor, and
hotkey-bridge. The
command is inspection-only: it does not record,
dispatch, approve, speak, call the API, or start hotkeys. Use `--limit N` to
show the last N matching events, repeat `--event TYPE` or `--status STATUS` to
filter exact event/status values, use `--success` or `--failure` for outcome
filtering, use `--approval-dispatch-only` to show approval/dispatch-related
events, and pass `--json` for machine-readable stdout.

Use `--export PATH` to write the same filtered events to a local file for
backup or offline inspection. Export defaults to JSONL, uses JSON automatically
for `.json` paths, and can be forced with `--export-format jsonl` or
`--export-format json`. Export paths must be local filesystem paths; the parent
directory must already exist, and the command does not create missing parent
directories implicitly.

Use `--clear --dry-run` to preview clearing all local voice log events, or
`--clear-before YYYY-MM-DD --dry-run` to preview date-based retention. Actual
cleanup requires `--confirm`: `--clear --confirm` removes all local voice log
events from the configured JSONL file, while
`--clear-before YYYY-MM-DD --confirm` removes dated events before that UTC date
and keeps newer, undated, or unparseable lines. Cleanup can also be reported
with `--json`. It does not delete audio files; voice logs do not store raw
audio.

Log exports never include raw audio. By default, transcripts are summarized as
length, SHA-256, and a redacted preview; `voice logs --json` and
`voice logs --export` return that same stored summary. Full transcript text is
available only for events that were originally written after
`voice_logs_include_full_transcripts = true` was explicitly enabled.

`voice doctor` reports the effective API base URL, configured local
transcription adapter, model path existence when a local path is required,
default record duration, configured recorder and static backend availability,
whether the `dev-silent` recorder is available, whether `sounddevice` is
importable, whether a real microphone recorder is explicitly configured, and
that microphone permission and hardware were not probed. It also reports the
configured speech-output adapter and macOS `say`
availability when relevant, print-only/disabled hotkey bridge state, and whether
explicit voice approval is still required. Apart from optional local structured
logging, it does not request microphone access, open an input stream, download
models, call dispatch, speak text, or start a hotkey listener.

Mission Control's Voice tab reads `/v1/voice/ptt/status` for a read-only status
panel showing the FSM state, configured/effective API base URL, configured
transcription adapter, model path status, default record duration, speech output
backend, macOS `say` availability, disabled/print-only hotkey bridge state,
approval requirement, and recent redacted voice events when local voice logging
is enabled. It also shows a read-only readiness summary from that same status
payload with an overall `ready`, `needs setup`, or `unsafe config` state,
blocking issues, warnings, the next safe manual step, and whether the
preview-only real-microphone pipeline, approval-gated microphone dispatch,
`dev-silent` recorder, `sounddevice` dependency, and optional speech output are
available. Mission Control does not run those steps. The diagnostics summary
continues to mirror the safe `voice doctor` data plus local voice logging and
full transcript logging state; Mission Control does not run `jarvis voice
doctor`. A separate read-only safety/audit summary shows approval required,
auto-dispatch disabled, auto-speech disabled, always-on listening disabled, the
hotkey bridge disabled/print-only state, default temporary-WAV cleanup and
explicit retention, transcript redaction defaults, full transcript logging
state, local-only event logging
state, and recent approval/dispatch/speech event counts when safe event data is
available. The setup checklist remains read-only for API base URL configuration,
transcription adapter selection, model path configuration and existence,
recorder boundary availability, speech output backend, macOS `say`, hotkey
bridge state, approval requirement, and full transcript logging state.
Mission Control also shows a read-only setup troubleshooting section derived
from those same status fields. It explains why setup items are missing or unsafe,
including no local transcription adapter selected, missing model path,
configured model path not found, unavailable speech backend, unavailable macOS
`say`, non-standard hotkey bridge state, disabled logging, and full transcript
logging warnings. The hints may reference manual terminal commands, but they are
display-only; Mission Control does not run them or change settings.
Missing checklist items show copyable suggestions labeled as manual terminal
commands, such as `jarvis voice doctor`,
`jarvis voice transcribe-file ./voice-sample.wav --adapter faster-whisper`,
`jarvis voice record-local --duration 2`, `jarvis voice hotkey-bridge`, or
`jarvis voice run-local --duration 2 --adapter faster-whisper`. Mission Control
does not run those commands; it only displays/copies the text for use in a
terminal.
Mission Control also shows a guarded local pipeline command helper for
`jarvis voice run-local --duration ...`. The default helper command is
preview-only. If safe status data already identifies a supported local
transcription adapter, Mission Control includes the matching `--adapter` flag;
otherwise it leaves adapter resolution to the CLI/config boundary. Optional
`--approve-dispatch` and `--approve-dispatch --speak-result` variants are
displayed separately as manual explicit terminal commands, and Mission Control
only copies their text.
Recent events can be expanded in place to inspect only sanitized fields: event
type, status, timestamp, transcript length/hash/redacted preview, approval
decision, dispatch and speech attempt/result summaries, and error summary when
available. The same returned event list can be filtered locally by event type,
status, derived success/failure outcome, approval/dispatch-only events, and text
search over those safe displayed fields. It does not record audio, start
hotkeys, approve, dispatch, speak, run CLI commands, mutate voice settings, or
show raw audio or full transcript text from status events. Log export and
cleanup remain available only through `jarvis voice logs`; Mission Control does
not add those controls.

For a lightweight frontend verification pass focused on that status panel, run
`npm run check:mission-control-voice` from `frontend/`. In environments where
the full TypeScript project check hangs silently while resolving existing UI
library wrappers, this command checks the Mission Control Voice status surface
directly. If Vite starts but does not bind port `5173`, `npm run dev:verify`
uses the same app entry with `OPENJARVIS_VITE_SKIP_TAILWIND=1` to verify the
local server bind path without changing normal `npm run dev` or build behavior.

`voice hotkey-bridge` is a print-only boundary for future macOS Fn or
push-to-talk integration. It formats a `jarvis voice run-local ...` command, or
a disabled Hammerspoon example with `enable_openjarvis_voice_hotkey = false`.
Running `voice hotkey-bridge` does not start Hammerspoon, install a listener,
capture global keys, record audio, call the API, dispatch actions, approve
anything, or speak results. The printed command intentionally omits
`--approve-dispatch` and `--speak-result`, so it follows the same preview-only
default as `voice run-local`.

`voice record-local` defaults to `--recorder dev-silent` for safe development.
`--recorder sounddevice` uses the optional Python `sounddevice` package as a
real local microphone adapter and writes only a local WAV file unless you
separately call an explicit transcription pipeline command. Install it with:

```bash
uv sync --extra voice-mic
```

On macOS, `--recorder macos` uses local command-line recording tools and may
prompt for **Microphone** permission. `--recorder sounddevice` may also require
Microphone permission for the terminal app running `jarvis`; grant it in System
Settings > Privacy & Security > Microphone, then restart that terminal. A future
Hammerspoon or Swift Fn/hotkey helper will require macOS **Accessibility**
permission, but this CLI does not install, enable, or run that helper.
Voice-only mode remains deferred.

Local transcription is disabled unless you explicitly select a local adapter
with `--adapter`, set `[voice_control].transcription_adapter`, or set
`[speech].backend` to a local adapter in `~/.openjarvis/config.toml`. The
current local adapter choices are `faster-whisper` and `whisper.cpp`; cloud
speech backends are not used by `jarvis voice transcribe-file` or
`jarvis voice capture-preview`.
The same local adapter requirement applies to `jarvis voice run-local`.

For `faster-whisper`, install the optional dependency with:

```bash
uv sync --extra speech
```

Then either keep `[speech].model = "base"` or set
`[voice_control].model_path = "base"` to let faster-whisper resolve a supported
model name. You can also set either field to an existing local CTranslate2 model
directory. If you configure a local model path that does not exist, the CLI
returns a clear error before transcription.

For `whisper.cpp`, install a `whisper-cli` compatible binary and either put it on
`PATH` or set `WHISPER_CPP_BINARY`. Set `WHISPER_CPP_MODEL` to an existing local
ggml model file. Missing binaries or model files are reported as configuration
errors.

Privacy behavior is unchanged: audio is read from the file you provide or from
the explicit fixed-duration recorder only, transcription runs through the
selected local adapter, raw recordings are not persisted unless
`[speech].persist_raw_audio = true`, and dispatch still requires the separate
`jarvis voice submit --approve-dispatch` path or
`voice run-local --approve-dispatch` or `voice mic-run --approve-dispatch`.
`voice speak` sends only the literal text you provide to the selected local
adapter; `voice run-local --speak-result` and `voice mic-run --speak-result`
speak only an explicitly approved dispatch result. The current speech-output
adapter is `macos-say`, which uses the local macOS `say` command when available;
Piper, Coqui, and other local TTS adapters remain deferred. Voice-only mode, Fn
hotkey listening, always-on listening, and automatic speech playback of
dispatch results remain deferred.

---

## LLM-guided spec search (no CLI yet)

LLM-guided spec search (the frontier-driven harness-learning subsystem)
is exposed as a Python library only — there is currently no top-level
`jarvis` subcommand for it. Construct a `SpecSearchOrchestrator`
directly from `openjarvis.learning.spec_search.orchestrator` and call
`.run(trigger)` with a trigger from
`openjarvis.learning.spec_search.triggers`. See
[`docs/user-guide/llm-guided-spec-search.md`](llm-guided-spec-search.md)
for the architecture and the building blocks
(`splits.py`, external corpora, `external_adapter`).
