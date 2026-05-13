# Customization Plan

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
