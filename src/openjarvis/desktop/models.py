"""Typed models for local desktop integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class WindowInfo:
    """Current foreground window metadata."""

    application_name: str = ""
    title: str = ""
    process_id: int | None = None
    platform: str = ""
    privacy_mode: bool = False
    passive_only: bool = True
    local_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AppInfo:
    """One locally running desktop application."""

    name: str
    bundle_id: str = ""
    process_id: int | None = None
    executable: str = ""
    frontmost: bool = False
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkspaceFocus:
    """Focused project or workspace state."""

    path: str = ""
    name: str = ""
    git_repository: str = ""
    current_branch: str = ""
    project_type: str = "unknown"
    source: str = "cwd"
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LaunchRequest:
    """Explicit desktop launch request."""

    action: str
    target: str = ""
    app_name: str = ""
    workspace_path: str = ""
    coding_environment: str = ""
    requested_by: str = "user"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LaunchResult:
    """Result from an explicit launch request."""

    action: str
    target: str = ""
    status: str = "unknown"
    message: str = ""
    app_name: str = ""
    workspace_path: str = ""
    coding_environment: str = ""
    launched_at: str = ""
    command_preview: list[str] = field(default_factory=list)
    privacy_mode: bool = False
    local_only: bool = True
    autonomous: bool = False
    background_monitoring: bool = False
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LauncherHealthCheck:
    """One local launcher health probe."""

    name: str
    status: str = "unknown"
    url: str = ""
    message: str = ""
    checked_at: str = ""
    local_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DesktopLauncherState:
    """Local backend/frontend launcher state."""

    backend_status: str = "stopped"
    frontend_status: str = "stopped"
    backend_command: list[str] = field(default_factory=list)
    frontend_command: list[str] = field(default_factory=list)
    health_checks: list[LauncherHealthCheck] = field(default_factory=list)
    last_action: str = ""
    last_restart_at: str = ""
    local_only: bool = True
    passive_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_status": self.backend_status,
            "frontend_status": self.frontend_status,
            "backend_command": list(self.backend_command),
            "frontend_command": list(self.frontend_command),
            "health_checks": [check.to_dict() for check in self.health_checks],
            "last_action": self.last_action,
            "last_restart_at": self.last_restart_at,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "telemetry_enabled": self.telemetry_enabled,
        }


@dataclass(slots=True)
class DesktopNotification:
    """A lightweight local desktop notification record."""

    kind: str
    title: str
    body: str = ""
    status: str = "ready"
    created_at: str = ""
    user_triggered: bool = True
    delivered: bool = False
    local_only: bool = True
    autonomous: bool = False
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DesktopNotificationState:
    """Current lightweight local notification state."""

    recent: list[DesktopNotification] = field(default_factory=list)
    allowed_kinds: list[str] = field(default_factory=list)
    last_notification_at: str = ""
    enabled: bool = True
    autonomous_notifications: bool = False
    local_only: bool = True
    passive_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "recent": [item.to_dict() for item in self.recent],
            "allowed_kinds": list(self.allowed_kinds),
            "last_notification_at": self.last_notification_at,
            "enabled": self.enabled,
            "autonomous_notifications": self.autonomous_notifications,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "telemetry_enabled": self.telemetry_enabled,
        }


@dataclass(slots=True)
class TrayMenuItem:
    """One menu bar item exposed by the desktop wrapper."""

    id: str
    label: str
    enabled: bool = True
    checked: bool = False
    destructive: bool = False
    user_triggered_only: bool = True
    local_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrayState:
    """Menu bar status for Mission Control."""

    items: list[TrayMenuItem] = field(default_factory=list)
    last_action: str = ""
    voice_trigger_enabled: bool = False
    current_workspace_available: bool = False
    launcher_running: bool = False
    pending_notifications: int = 0
    local_only: bool = True
    passive_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "last_action": self.last_action,
            "voice_trigger_enabled": self.voice_trigger_enabled,
            "current_workspace_available": self.current_workspace_available,
            "launcher_running": self.launcher_running,
            "pending_notifications": self.pending_notifications,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "telemetry_enabled": self.telemetry_enabled,
        }


@dataclass(slots=True)
class DesktopSessionState:
    """Persisted local desktop session state."""

    focused_workspace: WorkspaceFocus = field(default_factory=WorkspaceFocus)
    recent_launches: list[LaunchResult] = field(default_factory=list)
    recent_notifications: list[DesktopNotification] = field(default_factory=list)
    launcher_state: DesktopLauncherState = field(default_factory=DesktopLauncherState)
    updated_at: str = ""
    local_only: bool = True
    passive_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "focused_workspace": self.focused_workspace.to_dict(),
            "recent_launches": [launch.to_dict() for launch in self.recent_launches],
            "recent_notifications": [
                notification.to_dict() for notification in self.recent_notifications
            ],
            "launcher_state": self.launcher_state.to_dict(),
            "updated_at": self.updated_at,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "telemetry_enabled": self.telemetry_enabled,
        }


@dataclass(slots=True)
class DesktopStatus:
    """Mission Control desktop status payload."""

    active_window: WindowInfo = field(default_factory=WindowInfo)
    active_application: AppInfo | None = None
    open_apps: list[AppInfo] = field(default_factory=list)
    focused_workspace: WorkspaceFocus = field(default_factory=WorkspaceFocus)
    session_state: DesktopSessionState = field(default_factory=DesktopSessionState)
    clipboard_preview: str = ""
    clipboard_sensitive: bool = False
    recent_launches: list[LaunchResult] = field(default_factory=list)
    launcher_state: DesktopLauncherState = field(default_factory=DesktopLauncherState)
    notification_state: DesktopNotificationState = field(
        default_factory=DesktopNotificationState
    )
    tray_state: TrayState = field(default_factory=TrayState)
    integrations: dict[str, Any] = field(default_factory=dict)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True
    autonomous_launching: bool = False
    background_monitoring: bool = False
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_window": self.active_window.to_dict(),
            "active_application": (
                self.active_application.to_dict()
                if self.active_application is not None
                else None
            ),
            "open_apps": [app.to_dict() for app in self.open_apps],
            "focused_workspace": self.focused_workspace.to_dict(),
            "session_state": self.session_state.to_dict(),
            "clipboard_preview": self.clipboard_preview,
            "clipboard_sensitive": self.clipboard_sensitive,
            "recent_launches": [launch.to_dict() for launch in self.recent_launches],
            "launcher_state": self.launcher_state.to_dict(),
            "notification_state": self.notification_state.to_dict(),
            "tray_state": self.tray_state.to_dict(),
            "integrations": self.integrations,
            "privacy_mode": self.privacy_mode,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "autonomous_launching": self.autonomous_launching,
            "background_monitoring": self.background_monitoring,
            "telemetry_enabled": self.telemetry_enabled,
        }


__all__ = [
    "AppInfo",
    "DesktopLauncherState",
    "DesktopNotification",
    "DesktopNotificationState",
    "DesktopSessionState",
    "DesktopStatus",
    "LauncherHealthCheck",
    "LaunchRequest",
    "LaunchResult",
    "TrayMenuItem",
    "TrayState",
    "WindowInfo",
    "WorkspaceFocus",
]
