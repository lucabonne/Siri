"""Permission integration for local voice output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openjarvis.tts.models import TTSPermissionDecision, TTSPermissionError


@dataclass
class TTSPermissionRequest:
    """Small request shape accepted by PermissionMiddleware."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    command: str | None = None
    permission_ceiling: Any = None
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class TTSPermissionGate:
    """Apply mode, privacy, and PermissionMiddleware rules to voice output."""

    def __init__(self, *, permission_middleware: Any) -> None:
        self._permission_middleware = permission_middleware

    def check_speak(
        self,
        *,
        text: str,
        engine_id: str,
        voice_id: str,
        active_mode: Any,
        active_agent: str,
        user_triggered: bool,
        local_only: bool,
        agent_memory_scope: list[str],
    ) -> TTSPermissionDecision:
        mode_id = getattr(active_mode, "id", "")
        if not user_triggered:
            raise TTSPermissionError(
                "voice output only runs from explicit user triggers"
            )
        if mode_id == "privacy" and not local_only:
            raise TTSPermissionError("Privacy Mode allows local-only voice output only")

        request = TTSPermissionRequest(
            tool_name="text_to_speech",
            arguments={
                "engine": engine_id,
                "voice_id": voice_id,
                "text_length": len(text),
                "local_only": local_only,
                "user_triggered": user_triggered,
            },
            agent_id=active_agent,
            metadata={
                "active_mode": active_mode,
                "active_mode_id": mode_id,
                "agent_memory_scope": agent_memory_scope,
                "local_only": local_only,
                "passive_only": True,
                "autonomous_speech": False,
                "source": "voice_output",
            },
        )
        raw = self._permission_middleware.check(request)
        decision = TTSPermissionDecision(
            action=raw.action,
            level=raw.level.name,
            reason=raw.reason,
            requires_approval=raw.requires_confirmation,
            matched_pattern=raw.matched_pattern,
        )
        if raw.denied:
            raise TTSPermissionError(raw.reason)
        if raw.requires_confirmation:
            raise TTSPermissionError(raw.reason)
        return decision


__all__ = ["TTSPermissionGate", "TTSPermissionRequest"]
