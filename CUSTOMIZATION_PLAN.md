# Customization Plan

## Desktop Integration Phase 1

Phase 1 makes Siri aware of the local desktop as an operating layer while
keeping all actions explicit, local, and user-triggered.

- `src/openjarvis/desktop/` owns passive window/app awareness, local clipboard
  preview redaction, focused workspace resolution, launch helpers, session
  state, typed models, and the coordinating desktop service.
- Desktop awareness covers active window, active application, open apps,
  focused project/workspace, clipboard preview, session state, and recent
  explicit launches.
- Launch capabilities cover opening a local application, repository,
  workspace, and coding environment. These are exposed only through explicit
  API calls and do not run autonomously.
- `/v1/desktop/status`, `/active-app`, `/open-apps`, `/launch-app`,
  `/launch-workspace`, `/launch-repo`, and `/launch-coding-environment`
  expose the desktop surface for Mission Control and local clients.
- Integration points are local and conservative: Context Layer status can
  include the desktop snapshot; Memory can record explicit non-Privacy launch
  events; Workflow, Mode, and Coding Assistant state are summarized in the
  desktop status payload.
- Mission Control now includes a Desktop panel showing active app, open apps,
  focused workspace, privacy posture, and recent explicit launches.
- Privacy Mode remains local-only: clipboard/window titles are redacted where
  applicable, no external sync is performed, and launch telemetry/memory writes
  are disabled.

Deferred work remains intentionally untouched in this phase:

- no autonomous launching
- no background desktop monitoring
- no remote telemetry
- no scheduler-driven launch actions

## Frontend Build Stability

Production frontend builds now avoid the Vite/Rollup transform hang without
changing Siri UI behavior.

- `frontend/vite.config.ts` keeps the existing React, Tailwind, shadcn, and
  alias setup, and adds an `openjarvis-lucide-direct-imports` Vite transform
  that rewrites `lucide-react` named imports to per-icon imports during build.
  This preserves source ergonomics while avoiding the full Lucide barrel graph
  in production transforms.
- Vite is pinned to `6.3.5` and Rollup to `4.34.9` to avoid the floated
  `vite@6.4.1` / `rollup@4.60.0` build hang observed after TypeScript passed.
- `vite-plugin-pwa` is preserved but gated behind
  `OPENJARVIS_ENABLE_PWA=1`. Normal `npm run build` and Tauri/static builds no
  longer wait on PWA generation after chunks are written.
- `npm run build:diagnostics` verifies CSS package resolution for
  `tailwindcss`, `tw-animate-css`, and `shadcn/tailwind.css`, runs a tiny
  Tailwind utility build, checks Lucide icon direct-import coverage, and
  validates the `@/*` alias contract.
- `npm run build:verify` runs diagnostics before the production build.
- Verified: `npm run build:diagnostics && npm run build` completes and writes
  the production assets under `src/openjarvis/server/static`.

## Controlled Automation Workflows Phase 1

Phase 1 adds explicit, reusable workflow scaffolding on top of Siri's existing
permission, approval, memory, context, mode, agent workspace, and terminal
co-pilot layers.

- `src/openjarvis/workflows/` owns workflow definitions, typed models,
  validation, approval bridging, local run history, memory recording, the
  conservative runner, and the coordinating service.
- Built-in workflows cover opening a project environment, running tests,
  summarizing a repo, preparing research, collecting logs, backing up notes,
  launching a coding workspace, and starting a morning workflow.
- Workflow definitions declare id, name, steps, required permissions,
  approval requirements, rollback hints, allowed agents, mode restrictions,
  and local-only privacy metadata.
- Runs are user-triggered only. Safe local/passive steps can complete
  synchronously; approval-gated steps enqueue shared approval records and stop
  at `waiting_approval` instead of executing shell, file-write, memory-write,
  or agent-spawn style actions.
- Privacy Mode remains local-only and rejects workflows or steps that are not
  explicitly local-only. No external workflow sync is supported.
- `/v1/workflows`, `/{id}/run`, `/status/{run_id}`, `/history`,
  `/approvals`, and `/mission-control` expose workflow registry, runs,
  status, history, approval queue, and panel data.
- Mission Control now includes a Workflows panel for available workflows,
  running/waiting workflows, history, approvals, and failures.

Deferred work remains intentionally untouched in this phase:

- no autonomous workflow execution
- no background agents
- no external workflow sync
- no scheduler-driven workflow launches

## Autonomous Research Mode Phase 1

Phase 1 turns Siri Research Agent into an explicit local-first research
workflow without autonomous loops, background agents, sync, or notifications.

- `src/openjarvis/research/` owns planning, local/cached source search,
  claim extraction, citation generation, deterministic summarization, report
  rendering, memory writes, typed models, and the coordinating service.
- A research run is a synchronous one-shot workflow:
  question → plan → search → source collection → extraction → citations →
  summary → report → memory storage.
- Research plans include the original question, search strategy, subtopics,
  and open questions.
- Source records include title, URL, access date, relevance, snippets, source
  type, metadata, and extracted claims.
- Reports include notes, summaries, citations, unresolved questions, and a
  Markdown body suitable for local review.
- Storage is local SQLite. Research sessions and sources are cached in
  `research_sessions` and `research_sources`; summaries and source claims are
  also written to structured Memory as `research_report` and
  `research_source` memories.
- `/v1/research/start`, list, `/{id}/status`, `/{id}/report`,
  `/{id}/citations`, and `/{id}/memory` expose explicit research APIs.
- Integration points are passive: active Mode and active Agent Workspace ids
  are captured as metadata; cached Morning Briefing events, WorldMonitor
  imports, and structured Memory are searched as local sources.
- Privacy Mode forces cached/local sources only, blocks optional external
  search, marks artifacts local-only, and performs no external sync.
- Mission Control's Research tab now shows active research, notes, sources,
  reports, open questions, and stored memory entries from the backend.

Deferred work remains intentionally untouched in this phase:

- no autonomous research loops
- no background research agents
- no notifications
- no external sync
- no scheduler-driven research

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

## Voice Output / TTS Phase 1

Phase 1 adds explicit local voice output for Siri without autonomous speech,
cloud TTS, wake-word behavior, or always-on listening.

- `src/openjarvis/tts/` owns a dedicated local-only TTS subsystem:
  `engines.py` supports macOS `say` as the default local fallback and optional
  Piper when a local model is configured, `models.py` defines voice/status
  payloads, `permissions.py` integrates PermissionMiddleware, `state.py` owns
  active/latest speech state, and `service.py` coordinates user-triggered
  speech and stop behavior.
- `/v1/tts/speak`, `/v1/tts/stop`, `/v1/tts/status`, and `/v1/tts/voices`
  expose local voice output controls for Mission Control and local clients.
- Privacy Mode remains local-only: the service reports cloud TTS disabled and
  blocks any non-local output path.
- Quiet Mode marks output muted and blocks speech by default unless the caller
  explicitly opts into a user-triggered phrase. Focus Mode truncates spoken
  text to short responses, while Research Mode allows longer summaries.
- The service records active mode, active workspace agent, agent memory scope,
  passive voice-input status, and Context Layer snapshots as minimal metadata.
  Privacy Mode skips memory persistence.
- PermissionMiddleware continues to classify `text_to_speech` as a safe local
  action, and the TTS gate blocks non-user-triggered speech before playback.
- Mission Control's Voice tab now includes output controls for a test phrase,
  stop speaking, selected voice, local-only status, and quiet/muted mode state.

Deferred work remains intentionally untouched in this phase:

- no autonomous speech
- no response auto-play after chat completions
- no cloud TTS providers
- no scheduled or background voice output

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
