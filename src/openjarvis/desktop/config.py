"""Configuration defaults for the lightweight desktop wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_TRAY_ACTIONS = [
    "open_mission_control",
    "toggle_voice_trigger",
    "quick_morning_briefing",
    "open_current_workspace",
    "restart_backend",
    "quit",
]

ALLOWED_NOTIFICATION_KINDS = [
    "briefing_ready",
    "workflow_finished",
    "approval_required",
    "mcp_registration",
    "morning_briefing_ready",
    "workflow_completed",
    "research_completed",
    "build_completed",
    "startup_complete",
]


@dataclass(slots=True)
class DesktopWrapperConfig:
    """Local-only guardrails for the native wrapper facade."""

    tray_actions: list[str] = field(default_factory=lambda: list(DEFAULT_TRAY_ACTIONS))
    allowed_notification_kinds: list[str] = field(
        default_factory=lambda: list(ALLOWED_NOTIFICATION_KINDS)
    )
    local_only: bool = True
    passive_only: bool = True
    telemetry_enabled: bool = False
    autonomous_notifications: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "tray_actions": list(self.tray_actions),
            "allowed_notification_kinds": list(self.allowed_notification_kinds),
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "telemetry_enabled": self.telemetry_enabled,
            "autonomous_notifications": self.autonomous_notifications,
        }


__all__ = [
    "ALLOWED_NOTIFICATION_KINDS",
    "DEFAULT_TRAY_ACTIONS",
    "DesktopWrapperConfig",
]
