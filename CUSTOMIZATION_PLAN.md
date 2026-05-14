# Customization Plan

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
- no deep semantic code indexing

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
