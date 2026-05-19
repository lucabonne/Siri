"""Menu bar state and explicit tray action metadata."""

from __future__ import annotations

from openjarvis.desktop.models import TrayMenuItem, TrayState

TRAY_LABELS = {
    "open_mission_control": "Open Mission Control",
    "toggle_voice_trigger": "Toggle Voice Trigger",
    "quick_morning_briefing": "Quick Morning Briefing",
    "open_current_workspace": "Open Current Workspace",
    "restart_backend": "Restart Backend",
    "quit": "Quit Siri",
}


class MenuBarController:
    """Build passive menu bar state for a native shell to render."""

    def state(
        self,
        *,
        voice_trigger_enabled: bool = False,
        current_workspace_available: bool = False,
        launcher_running: bool = False,
        pending_notifications: int = 0,
        last_action: str = "",
    ) -> TrayState:
        items = [
            TrayMenuItem(
                id="open_mission_control",
                label=TRAY_LABELS["open_mission_control"],
            ),
            TrayMenuItem(
                id="toggle_voice_trigger",
                label=TRAY_LABELS["toggle_voice_trigger"],
                checked=voice_trigger_enabled,
            ),
            TrayMenuItem(
                id="quick_morning_briefing",
                label=TRAY_LABELS["quick_morning_briefing"],
            ),
            TrayMenuItem(
                id="open_current_workspace",
                label=TRAY_LABELS["open_current_workspace"],
                enabled=current_workspace_available,
            ),
            TrayMenuItem(id="restart_backend", label=TRAY_LABELS["restart_backend"]),
            TrayMenuItem(
                id="quit",
                label=TRAY_LABELS["quit"],
                destructive=True,
            ),
        ]
        return TrayState(
            items=items,
            last_action=last_action,
            voice_trigger_enabled=voice_trigger_enabled,
            current_workspace_available=current_workspace_available,
            launcher_running=launcher_running,
            pending_notifications=pending_notifications,
            local_only=True,
            passive_only=True,
            telemetry_enabled=False,
        )


__all__ = ["MenuBarController", "TRAY_LABELS"]
