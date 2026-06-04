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

Run the local typed/mock voice flow against an already running OpenJarvis API
server. This is a development bridge for future Hammerspoon/Fn push-to-talk
automation: an external hotkey/transcription script can submit a transcript
here, while OpenJarvis keeps the same preview, approval, dispatch, and cancel
API gates.

```bash
jarvis voice submit "open notes"                         # Preview only
jarvis voice submit "open notes" --approve-dispatch      # Preview, then dispatch
jarvis voice submit "run tests" --agent-id agent-123 --approve-dispatch
jarvis voice record-local --duration 2                   # Local WAV only
jarvis voice transcribe-file ./clip.wav --adapter faster-whisper
jarvis voice capture-preview --duration 2 --adapter faster-whisper
jarvis voice run-local --duration 2 --adapter faster-whisper
jarvis voice run-local --duration 2 --adapter faster-whisper --approve-dispatch
jarvis voice run-local --duration 2 --adapter faster-whisper --approve-dispatch --speak-result
jarvis voice doctor                                     # Safe local setup diagnostics
jarvis voice hotkey-bridge --adapter faster-whisper      # Print bridge command only
jarvis voice hotkey-bridge --format hammerspoon          # Print disabled helper example
jarvis voice speak "preview complete"                    # Explicit local TTS only
jarvis voice logs                                        # Show recent local voice events
jarvis voice status
jarvis voice cancel
```

| Command                 | Description                                      |
|-------------------------|--------------------------------------------------|
| `voice submit TEXT`     | POST to `/v1/voice/ptt/submit-transcript` and show the intent preview/session state |
| `voice submit --approve-dispatch` | Explicitly approve and then POST to `/v1/voice/ptt/dispatch` |
| `voice record-local --duration N` | Write a local WAV file and print its path; defaults to the dev silent recorder |
| `voice transcribe-file AUDIO` | Transcribe an existing local audio file with a local adapter and print the transcript only |
| `voice capture-preview --duration N` | Record a local WAV, transcribe it locally, POST the transcript to `/v1/voice/ptt/submit-transcript`, and print the preview only |
| `voice run-local --duration N` | Record, transcribe, submit preview, and print session state; dispatch and TTS require separate opt-in flags |
| `voice doctor`        | Inspect configured voice defaults and local dependency paths without recording, dispatching, speaking, or starting hotkeys |
| `voice hotkey-bridge` | Print the disabled macOS hotkey bridge command/example that an external helper can call later |
| `voice speak TEXT`     | Speak text through an explicit local speech-output adapter; defaults to macOS `say` when available |
| `voice logs`           | Show recent local structured voice command events |
| `voice status`          | GET `/v1/voice/ptt/status`                       |
| `voice cancel`          | POST `/v1/voice/ptt/cancel`                      |

This command does not listen in the background, capture Fn hotkeys, call a cloud
speech API, automatically dispatch a transcript, or automatically play TTS for
results. Speech output runs only through explicit commands/flags such as
`voice speak` or `voice run-local --speak-result`. `voice record-local` and
`voice capture-preview` both have an explicit `--duration` stop condition.
`voice capture-preview` manually chains local recording, local transcription,
and the existing preview endpoint, then stops before dispatch. Text input
remains available; dispatch is skipped unless `--approve-dispatch` is present on
`voice submit` or `voice run-local`.

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
cancel, transcribe-file, record-local, capture-preview, run-local, speak,
doctor, and hotkey-bridge. Log events never store raw audio. By default,
transcripts are summarized as length, SHA-256, and a redacted preview; set
`voice_logs_include_full_transcripts = true` only if you explicitly want full
transcripts written to disk.

`voice doctor` reports the effective API base URL, configured local
transcription adapter, model path existence when a local path is required,
default record duration, configured speech-output adapter, macOS `say`
availability when relevant, print-only/disabled hotkey bridge state, and whether
explicit voice approval is still required. Apart from optional local structured
logging, it does not request microphone access, download models, call dispatch,
speak text, or start a hotkey listener.

`voice hotkey-bridge` is a print-only boundary for future macOS Fn or
push-to-talk integration. It formats a `jarvis voice run-local ...` command, or
a disabled Hammerspoon example with `enable_openjarvis_voice_hotkey = false`.
Running `voice hotkey-bridge` does not start Hammerspoon, install a listener,
capture global keys, record audio, call the API, dispatch actions, approve
anything, or speak results. The printed command intentionally omits
`--approve-dispatch` and `--speak-result`, so it follows the same preview-only
default as `voice run-local`.

`voice record-local` defaults to `--recorder dev-silent` for safe development.
On macOS, `--recorder macos` uses local command-line recording tools and may
prompt for **Microphone** permission. A future Hammerspoon or Swift Fn/hotkey
helper will require macOS **Accessibility** permission, but this CLI does not
install, enable, or run that helper. Voice-only mode remains deferred.

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
`voice run-local --approve-dispatch`. `voice speak` sends only the literal text
you provide to the selected local adapter; `voice run-local --speak-result`
speaks only the explicit dispatch result. The current speech-output adapter is
`macos-say`, which uses the local macOS `say` command when available; Piper,
Coqui, and other local TTS adapters remain deferred. Voice-only mode, Fn hotkey
listening, always-on listening, and automatic speech playback of dispatch
results remain deferred.

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
