"""Permission and approval integration for push-to-talk voice capture."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openjarvis.voice.models import VoicePermissionDecision, VoicePermissionError


@dataclass
class VoicePermissionRequest:
    """Small request shape accepted by PermissionMiddleware."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    command: str | None = None
    permission_ceiling: Any = None
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class VoicePermissionGate:
    """Apply Privacy Mode and PermissionMiddleware rules to voice capture."""

    def __init__(
        self,
        *,
        permission_middleware: Any,
        approval_queue: Any = None,
        config: Any = None,
    ) -> None:
        self._permission_middleware = permission_middleware
        self._approval_queue = approval_queue
        self._config = config

    def check_start(
        self,
        *,
        active_mode: Any,
        active_agent: str,
        explicit_approval: bool,
        agent_memory_scope: list[str],
    ) -> VoicePermissionDecision:
        privacy_mode = getattr(active_mode, "id", "") == "privacy"
        voice_config = getattr(self._config, "speech", None)
        capture_enabled = bool(getattr(voice_config, "voice_capture_enabled", False))
        requires_explicit = bool(
            privacy_mode
            or getattr(voice_config, "require_explicit_voice_approval", True)
        )

        if not capture_enabled and not explicit_approval:
            decision = VoicePermissionDecision(
                action="blocked",
                level="CONFIRMED_EXECUTION",
                reason="voice capture is disabled until explicitly approved",
                requires_approval=True,
            )
            self._enqueue(active_agent, decision)
            raise VoicePermissionError(decision.reason)

        if requires_explicit and not explicit_approval:
            decision = VoicePermissionDecision(
                action="blocked",
                level="CONFIRMED_EXECUTION",
                reason="voice capture requires explicit push-to-talk approval",
                requires_approval=True,
            )
            self._enqueue(active_agent, decision)
            raise VoicePermissionError(decision.reason)

        request = VoicePermissionRequest(
            tool_name="voice_microphone_capture",
            arguments={
                "activation": "push_to_talk",
                "explicit_approval": explicit_approval,
            },
            agent_id=active_agent,
            metadata={
                "active_mode": active_mode,
                "active_mode_id": getattr(active_mode, "id", ""),
                "agent_memory_scope": agent_memory_scope,
                "explicit_approval": explicit_approval,
                "passive_only": True,
                "push_to_talk_only": True,
                "source": "voice_ptt",
            },
        )
        raw = self._permission_middleware.check(request)
        decision = VoicePermissionDecision(
            action=raw.action,
            level=raw.level.name,
            reason=raw.reason,
            requires_approval=raw.requires_confirmation,
            matched_pattern=raw.matched_pattern,
        )
        if raw.denied:
            self._enqueue(active_agent, decision)
            raise VoicePermissionError(raw.reason)
        if raw.requires_confirmation and not explicit_approval:
            self._enqueue(active_agent, decision)
            raise VoicePermissionError(raw.reason)
        return decision

    def _enqueue(
        self,
        active_agent: str,
        decision: VoicePermissionDecision,
    ) -> None:
        if self._approval_queue is None:
            return
        try:
            request = VoicePermissionRequest(
                tool_name="voice_microphone_capture",
                arguments={"activation": "push_to_talk"},
                agent_id=active_agent,
                metadata={"source": "voice_ptt"},
            )
            record = self._approval_queue.enqueue(
                request,
                type(
                    "Decision",
                    (),
                    {
                        "level": type("Level", (), {"name": decision.level})(),
                        "reason": decision.reason,
                        "matched_pattern": decision.matched_pattern,
                    },
                )(),
                source="voice_ptt",
            )
            decision.approval_id = record.id
        except Exception:
            return


__all__ = ["VoicePermissionGate", "VoicePermissionRequest"]
