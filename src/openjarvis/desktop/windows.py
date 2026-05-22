"""Passive foreground window detection."""

from __future__ import annotations

import platform
import subprocess

from openjarvis.desktop.models import WindowInfo


class WindowProvider:
    """Read foreground window metadata without installing a watcher."""

    def active_window(self, *, privacy_mode: bool = False) -> WindowInfo:
        system = platform.system()
        if system == "Darwin":
            return self._active_macos_window(privacy_mode=privacy_mode)
        return WindowInfo(platform=system, privacy_mode=privacy_mode)

    def _active_macos_window(self, *, privacy_mode: bool) -> WindowInfo:
        script = (
            'tell application "System Events"\n'
            "set frontApp to first application process whose frontmost is true\n"
            "set appName to name of frontApp\n"
            "set pidValue to unix id of frontApp\n"
            "set windowTitle to \"\"\n"
            "try\n"
            "set windowTitle to name of front window of frontApp\n"
            "end try\n"
            "return appName & linefeed & pidValue & linefeed & windowTitle\n"
            "end tell"
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.2,
            )
        except (OSError, subprocess.TimeoutExpired):
            return WindowInfo(platform="Darwin", privacy_mode=privacy_mode)
        if result.returncode != 0:
            return WindowInfo(platform="Darwin", privacy_mode=privacy_mode)

        parts = result.stdout.strip().splitlines()
        app_name = parts[0] if parts else ""
        process_id = _int_or_none(parts[1]) if len(parts) > 1 else None
        title = parts[2] if len(parts) > 2 else ""
        if privacy_mode and title:
            title = "[redacted window]"
        return WindowInfo(
            application_name=app_name,
            title=title,
            process_id=process_id,
            platform="Darwin",
            privacy_mode=privacy_mode,
        )


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["WindowProvider"]
