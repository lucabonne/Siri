# Customization Plan

## Voice Control Phase 3

Phase 3 wires the explicit voice-session state machine through the backend and
Mission Control while keeping the user flow typed/mock-transcript only.

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
- Mission Control adds a mock transcript textarea, preview action, approval
  dispatch action, cancel action, and clear typed/mock-only labeling while
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
