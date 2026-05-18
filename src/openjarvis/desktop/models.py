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
class DesktopSessionState:
    """Persisted local desktop session state."""

    focused_workspace: WorkspaceFocus = field(default_factory=WorkspaceFocus)
    recent_launches: list[LaunchResult] = field(default_factory=list)
    updated_at: str = ""
    local_only: bool = True
    passive_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "focused_workspace": self.focused_workspace.to_dict(),
            "recent_launches": [launch.to_dict() for launch in self.recent_launches],
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
    "DesktopSessionState",
    "DesktopStatus",
    "LaunchRequest",
    "LaunchResult",
    "WindowInfo",
    "WorkspaceFocus",
]
