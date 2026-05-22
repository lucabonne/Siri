"""Permission middleware for tool execution.

Phase 1 keeps this deliberately small: classify a tool request, make a
local allow/deny/confirmation decision, and write an append-only audit line.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse

from openjarvis.security.file_utils import secure_create

logger = logging.getLogger(__name__)


class PermissionLevel(IntEnum):
    """Coarse permission levels for tool requests."""

    READ_ONLY = 0
    SAFE_ACTION = 1
    CONFIRMED_EXECUTION = 2
    DANGEROUS = 3


@dataclass(slots=True)
class PermissionRequest:
    """Input to ``PermissionMiddleware.check``."""

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    command: Optional[str] = None
    permission_ceiling: Optional[PermissionLevel] = None
    dry_run: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PermissionDecision:
    """Decision returned by the permission middleware."""

    action: str
    level: PermissionLevel
    reason: str
    matched_pattern: Optional[str] = None
    dry_run: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.action == "allow"

    @property
    def denied(self) -> bool:
        return self.action == "deny"

    @property
    def requires_confirmation(self) -> bool:
        return self.action == "require_confirmation"


class PermissionMiddleware:
    """Classify tool calls and return coarse permission decisions."""

    _READ_ONLY_TOOLS = frozenset(
        {
            "browser_axtree",
            "browser_extract",
            "browser_screenshot",
            "calculator",
            "channel_list",
            "channel_status",
            "db_query",
            "file_read",
            "git_diff",
            "git_log",
            "git_status",
            "kg_neighbors",
            "kg_query",
            "knowledge_search",
            "list_scheduled_tasks",
            "retrieval",
            "scan_chunks",
            "terminal_context",
            "terminal_error_summary",
            "terminal_history",
            "terminal_suggested_fixes",
            "think",
            "web_search",
        }
    )
    _SAFE_ACTION_TOOLS = frozenset(
        {
            "agent_list",
            "browser_click",
            "browser_navigate",
            "browser_type",
            "digest_collect",
            "http_request",
            "knowledge_sql",
            "llm_tool",
            "mcp_adapter",
            "pdf_tool",
            "repl",
            "schedule_task",
            "skill_manage",
            "text_to_speech",
            "user_profile_manage",
            "vision_screenshot_capture",
        }
    )
    _CONFIRMED_TOOLS = frozenset(
        {
            "agent_kill",
            "agent_send",
            "agent_spawn",
            "apply_patch",
            "cancel_scheduled_task",
            "channel_send",
            "code_interpreter",
            "code_interpreter_docker",
            "file_write",
            "git_commit",
            "kg_add_entity",
            "kg_add_relation",
            "memory_manage",
            "pause_scheduled_task",
            "repl",
            "resume_scheduled_task",
            "shell_exec",
            "storage_delete",
            "storage_put",
            "terminal_suggested_command_approval",
            "voice_global_hotkey_listener",
            "voice_microphone_capture",
        }
    )
    _DANGEROUS_TOOLS = frozenset()

    _DANGEROUS_COMMAND_PATTERNS = tuple(
        (label, re.compile(pattern, re.IGNORECASE))
        for label, pattern in (
            (
                "recursive-root-delete",
                r"\brm\s+[^;&|]*-[^\s;&|]*r[f]?[^\s;&|]*\s+/(?:\s|$)",
            ),
            ("home-delete", r"\brm\s+[^;&|]*-[^\s;&|]*r[f]?[^\s;&|]*\s+~(?:/|\s|$)"),
            (
                "force-clean-current-dir",
                r"\brm\s+[^;&|]*-[^\s;&|]*r[f]?[^\s;&|]*\s+\.(?:\s|$)",
            ),
            (
                "disk-format",
                r"\b(?:mkfs|fdisk|parted|diskutil\s+erase|diskutil\s+partition)\b",
            ),
            ("raw-disk-write", r"\bdd\s+.*\bof=/dev/(?:disk|rdisk|sd|nvme)"),
            ("privilege-escalation", r"\b(?:sudo|su)\b"),
            (
                "permission-recursive-root",
                r"\b(?:chmod|chown|chgrp)\s+[^;&|]*-R[^;&|]*\s+/(?:\s|$)",
            ),
            ("shutdown", r"\b(?:shutdown|reboot|halt|poweroff)\b"),
            ("fork-bomb", r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;?\s*:"),
            ("pipe-to-shell", r"\b(?:curl|wget)\b.*\|\s*(?:sh|bash|zsh|python|perl)\b"),
            ("git-destructive", r"\bgit\s+(?:reset\s+--hard|clean\s+-[^\s;&|]*f)"),
            ("kill-all", r"\bkill\s+-9\s+-1\b"),
        )
    )

    def __init__(
        self,
        *,
        audit_log_path: Optional[Path | str] = None,
        dry_run: bool = False,
        mode_registry: Any = None,
    ) -> None:
        self._audit_log_path = (
            Path(audit_log_path).expanduser()
            if audit_log_path is not None
            else Path.home() / ".openjarvis" / "logs" / "permissions.log"
        )
        self._dry_run = dry_run
        self._mode_registry = mode_registry

    @property
    def audit_log_path(self) -> Path:
        return self._audit_log_path

    def check(self, request: PermissionRequest) -> PermissionDecision:
        """Return the permission decision for *request* and audit it."""
        level, reason, matched_pattern = self.classify(request)
        ceiling = request.permission_ceiling
        if ceiling is not None and level > ceiling:
            reason = (
                f"permission level {level.name} exceeds agent ceiling "
                f"{ceiling.name}: {reason}"
            )
            level = PermissionLevel.DANGEROUS
            matched_pattern = matched_pattern or "agent-permission-ceiling"
        action = self._action_for_level(level)
        dry_run = self._dry_run or request.dry_run

        metadata: Dict[str, Any] = {}
        if dry_run:
            metadata["would_action"] = action
            metadata["would_level"] = level.name
            action = "allow"
            reason = f"dry_run: would {metadata['would_action']} ({reason})"

        decision = PermissionDecision(
            action=action,
            level=level,
            reason=reason,
            matched_pattern=matched_pattern,
            dry_run=dry_run,
            metadata=metadata,
        )
        self._audit(request, decision)
        return decision

    def classify(
        self,
        request: PermissionRequest,
    ) -> tuple[PermissionLevel, str, Optional[str]]:
        """Classify a permission request without applying dry-run behavior."""
        tool_name = request.tool_name
        arguments = request.arguments if isinstance(request.arguments, Mapping) else {}
        active_mode = self._active_mode(request)

        privacy_block = self._privacy_mode_block(tool_name, arguments, active_mode)
        if privacy_block is not None:
            reason, matched_pattern = privacy_block
            return PermissionLevel.DANGEROUS, reason, matched_pattern

        command = self._extract_command(request, arguments)
        if tool_name == "shell_exec" or self._looks_like_shell_tool(tool_name):
            level, reason, matched_pattern = self.classify_shell_command(command)
            if (
                tool_name != "shell_exec"
                and level == PermissionLevel.CONFIRMED_EXECUTION
            ):
                reason = f"MCP shell-style tool requires confirmation: {tool_name}"
            return level, reason, matched_pattern

        if tool_name == "http_request":
            method = str(arguments.get("method", "GET")).upper()
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                return (
                    PermissionLevel.CONFIRMED_EXECUTION,
                    f"http_request with mutating method {method}",
                    None,
                )

        if tool_name == "memory_manage":
            action = str(arguments.get("action", "read")).lower()
            if action == "read":
                return PermissionLevel.READ_ONLY, "memory read", None
            return PermissionLevel.CONFIRMED_EXECUTION, f"memory {action}", None

        if tool_name in self._READ_ONLY_TOOLS:
            return PermissionLevel.READ_ONLY, "read-only tool", None
        if tool_name in self._SAFE_ACTION_TOOLS:
            return PermissionLevel.SAFE_ACTION, "safe action tool", None
        if tool_name in self._CONFIRMED_TOOLS:
            return (
                PermissionLevel.CONFIRMED_EXECUTION,
                "tool requires confirmation",
                None,
            )
        if tool_name in self._DANGEROUS_TOOLS:
            return PermissionLevel.DANGEROUS, "dangerous tool", None

        mcp_level = self._classify_mcp_style_tool(tool_name)
        if mcp_level is not None:
            return mcp_level, f"MCP-style {mcp_level.name.lower()} tool", None

        return (
            PermissionLevel.SAFE_ACTION,
            "unclassified tool defaults to safe action",
            None,
        )

    def _active_mode(self, request: PermissionRequest) -> Any:
        mode = request.metadata.get("active_mode")
        if mode is not None and not isinstance(mode, str):
            return mode
        registry = self._mode_registry
        if registry is None:
            return None
        try:
            mode_id = request.metadata.get("active_mode_id")
            if mode_id:
                return registry.get_mode(str(mode_id))
            return registry.get_active_mode().mode
        except Exception:
            return None

    def _privacy_mode_block(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        active_mode: Any,
    ) -> Optional[tuple[str, str]]:
        if getattr(active_mode, "id", "") != "privacy":
            return None

        normalized = tool_name.lower().replace("-", "_")
        if "mcp" in normalized:
            return "privacy mode blocks remote MCP tool execution", "privacy-remote-mcp"

        if tool_name == "http_request":
            url = str(arguments.get("url", ""))
            if not self._is_localhost_url(url):
                return (
                    "privacy mode blocks outbound non-localhost HTTP requests",
                    "privacy-network-localhost-only",
                )

        if normalized in {"web_search", "browser_navigate"}:
            url = str(arguments.get("url", ""))
            if not url or not self._is_localhost_url(url):
                return (
                    "privacy mode blocks outbound non-localhost networking",
                    "privacy-network-localhost-only",
                )

        if normalized in {"vision_screenshot_capture", "browser_screenshot"}:
            return (
                "privacy mode requires approval before screenshot capture",
                "privacy-vision-screenshot",
            )

        if normalized == "voice_microphone_capture" and not arguments.get(
            "explicit_approval"
        ):
            return (
                "privacy mode requires explicit approval before voice capture",
                "privacy-voice-capture",
            )

        if normalized == "voice_global_hotkey_listener":
            return (
                "privacy mode disables the global voice hotkey listener",
                "privacy-global-voice-hotkey",
            )

        return None

    @staticmethod
    def _is_localhost_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        host = parsed.hostname
        if not host:
            return False
        normalized = host.strip("[]").lower()
        if normalized in {"localhost", "localhost.localdomain"}:
            return True
        try:
            parsed_ip = ip_address(normalized)
        except ValueError:
            return False
        return parsed_ip.is_loopback

    def classify_shell_command(
        self,
        command: str,
    ) -> tuple[PermissionLevel, str, Optional[str]]:
        """Classify a shell command using known dangerous patterns."""
        normalized = " ".join(command.strip().split())
        if not normalized:
            return PermissionLevel.SAFE_ACTION, "empty shell command", None

        for label, pattern in self._DANGEROUS_COMMAND_PATTERNS:
            if pattern.search(normalized):
                return (
                    PermissionLevel.DANGEROUS,
                    f"dangerous shell command pattern: {label}",
                    label,
                )

        return (
            PermissionLevel.CONFIRMED_EXECUTION,
            "shell command requires confirmation",
            None,
        )

    @staticmethod
    def _action_for_level(level: PermissionLevel) -> str:
        if level == PermissionLevel.DANGEROUS:
            return "deny"
        if level == PermissionLevel.CONFIRMED_EXECUTION:
            return "require_confirmation"
        return "allow"

    @staticmethod
    def _extract_command(
        request: PermissionRequest,
        arguments: Mapping[str, Any],
    ) -> str:
        if request.command is not None:
            return request.command
        for key in ("command", "cmd", "shell_command", "script"):
            raw = arguments.get(key)
            if raw is not None:
                return raw if isinstance(raw, str) else str(raw)
        return ""

    @staticmethod
    def _looks_like_shell_tool(tool_name: str) -> bool:
        normalized = tool_name.lower().replace("-", "_")
        shell_tokens = ("shell", "bash", "zsh", "run_command")
        return any(token in normalized for token in shell_tokens)

    @staticmethod
    def _classify_mcp_style_tool(tool_name: str) -> Optional[PermissionLevel]:
        normalized = tool_name.lower().replace("-", "_")
        if any(token in normalized for token in ("read_file", "get_file")):
            return PermissionLevel.READ_ONLY
        if any(
            token in normalized
            for token in (
                "write_file",
                "create_file",
                "edit_file",
                "patch_file",
                "delete_file",
                "remove_file",
                "apply_patch",
                "run_code",
                "execute_code",
                "python",
            )
        ):
            return PermissionLevel.CONFIRMED_EXECUTION
        return None

    def _audit(
        self,
        request: PermissionRequest,
        decision: PermissionDecision,
    ) -> None:
        try:
            path = secure_create(self._audit_log_path)
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_id": request.agent_id,
                "tool": request.tool_name,
                "action": decision.action,
                "level": decision.level.name,
                "reason": decision.reason,
                "matched_pattern": decision.matched_pattern,
                "dry_run": decision.dry_run,
                "argument_keys": sorted(
                    str(key)
                    for key in (
                        request.arguments.keys()
                        if isinstance(request.arguments, Mapping)
                        else []
                    )
                ),
                "command_preview": self._command_preview(request),
                "request_metadata": request.metadata,
                "metadata": decision.metadata,
            }
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
        except Exception:
            logger.debug("Failed to write permission audit log", exc_info=True)

    @staticmethod
    def _command_preview(request: PermissionRequest) -> str:
        command = request.command
        if command is None and isinstance(request.arguments, Mapping):
            raw = request.arguments.get("command", "")
            command = raw if isinstance(raw, str) else ""
        return (command or "")[:200]


__all__ = [
    "PermissionDecision",
    "PermissionLevel",
    "PermissionMiddleware",
    "PermissionRequest",
]
