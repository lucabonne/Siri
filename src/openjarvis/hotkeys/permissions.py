"""Permission integration for global voice hotkey activation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openjarvis.hotkeys.models import HotkeyPermissionError


@dataclass
class HotkeyPermissionRequest:
    """Small request shape accepted by PermissionMiddleware."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    command: str | None = None
    permission_ceiling: Any = None
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class HotkeyPermissionGate:
    """Apply Privacy Mode and PermissionMiddleware rules to hotkeys."""

    def __init__(self, *, permission_middleware: Any) -> None:
        self._permission_middleware = permission_middleware

    def check_enable(
        self,
        *,
        active_mode: Any,
        explicit_approval: bool,
        binding: dict[str, Any],
    ) -> None:
        self._check(
            action="enable",
            active_mode=active_mode,
            explicit_approval=explicit_approval,
            binding=binding,
        )

    def check_trigger(
        self,
        *,
        active_mode: Any,
        explicit_approval: bool,
        binding: dict[str, Any],
        test: bool = False,
    ) -> None:
        self._check(
            action="test_trigger" if test else "trigger",
            active_mode=active_mode,
            explicit_approval=explicit_approval,
            binding=binding,
        )

    def _check(
        self,
        *,
        action: str,
        active_mode: Any,
        explicit_approval: bool,
        binding: dict[str, Any],
    ) -> None:
        request = HotkeyPermissionRequest(
            tool_name="voice_global_hotkey_listener",
            arguments={
                "action": action,
                "explicit_approval": explicit_approval,
                "binding": binding,
            },
            metadata={
                "active_mode": active_mode,
                "active_mode_id": getattr(active_mode, "id", ""),
                "source": "global_voice_hotkey",
                "push_to_talk_only": True,
                "wake_word_enabled": False,
                "background_transcription": False,
                "explicit_approval": explicit_approval,
            },
        )
        decision = self._permission_middleware.check(request)
        if decision.denied:
            raise HotkeyPermissionError(decision.reason)
        if decision.requires_confirmation and not explicit_approval:
            raise HotkeyPermissionError(decision.reason)


__all__ = ["HotkeyPermissionGate", "HotkeyPermissionRequest"]
