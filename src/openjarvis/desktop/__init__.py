"""Local desktop operating layer for OpenJarvis."""

from openjarvis.desktop.apps import AppController
from openjarvis.desktop.clipboard import ClipboardProvider
from openjarvis.desktop.focus import FocusResolver
from openjarvis.desktop.launcher import DesktopLauncher
from openjarvis.desktop.models import (
    AppInfo,
    DesktopSessionState,
    DesktopStatus,
    LaunchRequest,
    LaunchResult,
    WindowInfo,
    WorkspaceFocus,
)
from openjarvis.desktop.service import DesktopService
from openjarvis.desktop.sessions import DesktopSessionStore
from openjarvis.desktop.windows import WindowProvider

__all__ = [
    "AppController",
    "AppInfo",
    "ClipboardProvider",
    "DesktopLauncher",
    "DesktopService",
    "DesktopSessionState",
    "DesktopStatus",
    "DesktopSessionStore",
    "FocusResolver",
    "LaunchRequest",
    "LaunchResult",
    "WindowInfo",
    "WindowProvider",
    "WorkspaceFocus",
]
