"""Local desktop operating layer for OpenJarvis."""

from openjarvis.desktop.apps import AppController
from openjarvis.desktop.clipboard import ClipboardProvider
from openjarvis.desktop.config import DesktopWrapperConfig
from openjarvis.desktop.focus import FocusResolver
from openjarvis.desktop.launcher import DesktopLauncher
from openjarvis.desktop.models import (
    AppInfo,
    DesktopLauncherState,
    DesktopNotification,
    DesktopNotificationState,
    DesktopSessionState,
    DesktopStatus,
    LauncherHealthCheck,
    LaunchRequest,
    LaunchResult,
    TrayMenuItem,
    TrayState,
    WindowInfo,
    WorkspaceFocus,
)
from openjarvis.desktop.notifications import NotificationCenter
from openjarvis.desktop.service import DesktopService
from openjarvis.desktop.sessions import DesktopSessionStore
from openjarvis.desktop.tray import MenuBarController
from openjarvis.desktop.windows import WindowProvider

__all__ = [
    "AppController",
    "AppInfo",
    "ClipboardProvider",
    "DesktopWrapperConfig",
    "DesktopLauncherState",
    "DesktopLauncher",
    "DesktopNotification",
    "DesktopNotificationState",
    "DesktopService",
    "DesktopSessionState",
    "DesktopStatus",
    "DesktopSessionStore",
    "FocusResolver",
    "LauncherHealthCheck",
    "LaunchRequest",
    "LaunchResult",
    "MenuBarController",
    "NotificationCenter",
    "TrayMenuItem",
    "TrayState",
    "WindowInfo",
    "WindowProvider",
    "WorkspaceFocus",
]
