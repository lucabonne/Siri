"""Local desktop session state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openjarvis.desktop.models import (
    DesktopLauncherState,
    DesktopNotification,
    DesktopSessionState,
    LauncherDiagnostic,
    LauncherHealthCheck,
    LaunchResult,
    WorkspaceFocus,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_desktop_session_path() -> Path:
    return Path.home() / ".openjarvis" / "state" / "desktop_sessions.json"


class DesktopSessionStore:
    """Persist focused workspace and recent launches in a local JSON file."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_launches: int = 20,
    ) -> None:
        self.path = (
            Path(path).expanduser()
            if path is not None
            else default_desktop_session_path()
        )
        self.max_launches = max(1, max_launches)

    def load(self) -> DesktopSessionState:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DesktopSessionState()
        return DesktopSessionState(
            focused_workspace=_workspace_from_dict(data.get("focused_workspace", {})),
            recent_launches=[
                _launch_from_dict(item)
                for item in data.get("recent_launches", [])
                if isinstance(item, dict)
            ][: self.max_launches],
            recent_notifications=[
                _notification_from_dict(item)
                for item in data.get("recent_notifications", [])
                if isinstance(item, dict)
            ][: self.max_launches],
            launcher_state=_launcher_state_from_dict(data.get("launcher_state", {})),
            updated_at=str(data.get("updated_at", "")),
            local_only=bool(data.get("local_only", True)),
            passive_only=bool(data.get("passive_only", True)),
            telemetry_enabled=bool(data.get("telemetry_enabled", False)),
        )

    def save(self, state: DesktopSessionState) -> None:
        state.updated_at = utc_now()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def set_focused_workspace(self, focus: WorkspaceFocus) -> DesktopSessionState:
        state = self.load()
        state.focused_workspace = focus
        state.passive_only = True
        state.telemetry_enabled = False
        self.save(state)
        return state

    def record_launch(
        self,
        launch: LaunchResult,
        *,
        focused_workspace: WorkspaceFocus | None = None,
    ) -> DesktopSessionState:
        state = self.load()
        if not launch.launched_at:
            launch.launched_at = utc_now()
        if focused_workspace is not None and focused_workspace.path:
            state.focused_workspace = focused_workspace
        state.recent_launches = [launch, *state.recent_launches][: self.max_launches]
        state.passive_only = True
        state.telemetry_enabled = False
        self.save(state)
        return state

    def record_notification(
        self,
        notification: DesktopNotification,
    ) -> DesktopSessionState:
        state = self.load()
        if not notification.created_at:
            notification.created_at = utc_now()
        state.recent_notifications = [
            notification,
            *state.recent_notifications,
        ][: self.max_launches]
        state.passive_only = True
        state.telemetry_enabled = False
        self.save(state)
        return state

    def set_launcher_state(
        self,
        launcher_state: DesktopLauncherState,
    ) -> DesktopSessionState:
        state = self.load()
        state.launcher_state = launcher_state
        state.passive_only = True
        state.telemetry_enabled = False
        self.save(state)
        return state


def _workspace_from_dict(data: Any) -> WorkspaceFocus:
    if not isinstance(data, dict):
        return WorkspaceFocus()
    return WorkspaceFocus(
        path=str(data.get("path", "")),
        name=str(data.get("name", "")),
        git_repository=str(data.get("git_repository", "")),
        current_branch=str(data.get("current_branch", "")),
        project_type=str(data.get("project_type", "unknown") or "unknown"),
        source=str(data.get("source", "session") or "session"),
        local_only=bool(data.get("local_only", True)),
        passive_only=bool(data.get("passive_only", True)),
    )


def _launch_from_dict(data: dict[str, Any]) -> LaunchResult:
    return LaunchResult(
        action=str(data.get("action", "")),
        target=str(data.get("target", "")),
        status=str(data.get("status", "unknown")),
        message=str(data.get("message", "")),
        app_name=str(data.get("app_name", "")),
        workspace_path=str(data.get("workspace_path", "")),
        coding_environment=str(data.get("coding_environment", "")),
        launched_at=str(data.get("launched_at", "")),
        command_preview=[str(item) for item in data.get("command_preview", [])],
        privacy_mode=bool(data.get("privacy_mode", False)),
        local_only=bool(data.get("local_only", True)),
        autonomous=bool(data.get("autonomous", False)),
        background_monitoring=bool(data.get("background_monitoring", False)),
        telemetry_enabled=bool(data.get("telemetry_enabled", False)),
    )


def _notification_from_dict(data: dict[str, Any]) -> DesktopNotification:
    return DesktopNotification(
        kind=str(data.get("kind", "")),
        title=str(data.get("title", "")),
        body=str(data.get("body", "")),
        status=str(data.get("status", "ready")),
        created_at=str(data.get("created_at", "")),
        user_triggered=bool(data.get("user_triggered", True)),
        delivered=bool(data.get("delivered", False)),
        local_only=bool(data.get("local_only", True)),
        autonomous=bool(data.get("autonomous", False)),
        telemetry_enabled=bool(data.get("telemetry_enabled", False)),
    )


def _launcher_state_from_dict(data: Any) -> DesktopLauncherState:
    if not isinstance(data, dict):
        return DesktopLauncherState()
    return DesktopLauncherState(
        backend_status=str(data.get("backend_status", "stopped")),
        frontend_status=str(data.get("frontend_status", "stopped")),
        backend_command=[
            str(item) for item in data.get("backend_command", []) if item is not None
        ],
        frontend_command=[
            str(item) for item in data.get("frontend_command", []) if item is not None
        ],
        health_checks=[
            _health_check_from_dict(item)
            for item in data.get("health_checks", [])
            if isinstance(item, dict)
        ],
        startup_diagnostics=[
            _diagnostic_from_dict(item)
            for item in data.get("startup_diagnostics", [])
            if isinstance(item, dict)
        ],
        last_action=str(data.get("last_action", "")),
        last_restart_at=str(data.get("last_restart_at", "")),
        local_only=bool(data.get("local_only", True)),
        passive_only=bool(data.get("passive_only", True)),
        telemetry_enabled=bool(data.get("telemetry_enabled", False)),
    )


def _health_check_from_dict(data: dict[str, Any]) -> LauncherHealthCheck:
    return LauncherHealthCheck(
        name=str(data.get("name", "")),
        status=str(data.get("status", "unknown")),
        url=str(data.get("url", "")),
        message=str(data.get("message", "")),
        checked_at=str(data.get("checked_at", "")),
        local_only=bool(data.get("local_only", True)),
        telemetry_enabled=bool(data.get("telemetry_enabled", False)),
    )


def _diagnostic_from_dict(data: dict[str, Any]) -> LauncherDiagnostic:
    return LauncherDiagnostic(
        name=str(data.get("name", "")),
        status=str(data.get("status", "unknown")),
        message=str(data.get("message", "")),
        checked_at=str(data.get("checked_at", "")),
        local_only=bool(data.get("local_only", True)),
        telemetry_enabled=bool(data.get("telemetry_enabled", False)),
    )


__all__ = ["DesktopSessionStore", "default_desktop_session_path", "utc_now"]
