"""Local desktop application inventory and launching."""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable

from openjarvis.desktop.models import AppInfo, LaunchResult

Runner = Callable[..., subprocess.CompletedProcess[str]]


class AppController:
    """List and launch applications through local OS facilities."""

    def __init__(self, *, runner: Runner | None = None) -> None:
        self._runner = runner or subprocess.run

    def open_apps(self, *, active_app_name: str = "") -> list[AppInfo]:
        system = platform.system()
        if system == "Darwin":
            apps = self._macos_open_apps(active_app_name=active_app_name)
            if apps:
                return apps
        return self._process_fallback(active_app_name=active_app_name)

    def launch_app(self, app_name: str, *, privacy_mode: bool = False) -> LaunchResult:
        app_name = app_name.strip()
        if not app_name:
            return LaunchResult(
                action="launch_app",
                status="failed",
                message="application name is required",
                privacy_mode=privacy_mode,
            )
        command = _open_app_command(app_name)
        return _run_launch(
            self._runner,
            command,
            action="launch_app",
            target=app_name,
            app_name=app_name,
            privacy_mode=privacy_mode,
        )

    def _macos_open_apps(self, *, active_app_name: str) -> list[AppInfo]:
        script = (
            'tell application "System Events"\n'
            "set appLines to {}\n"
            "repeat with proc in application processes whose background only is false\n"
            "set end of appLines to "
            '(name of proc as text) & tab & (unix id of proc as text) & tab & '
            "((frontmost of proc) as text)\n"
            "end repeat\n"
            "return appLines as text\n"
            "end tell"
        )
        try:
            result = self._runner(
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if result.returncode != 0:
            return []

        apps: list[AppInfo] = []
        seen: set[str] = set()
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if not parts or not parts[0].strip():
                continue
            name = parts[0].strip()
            if name in seen:
                continue
            seen.add(name)
            apps.append(
                AppInfo(
                    name=name,
                    process_id=_int_or_none(parts[1]) if len(parts) > 1 else None,
                    frontmost=(
                        name == active_app_name
                        or (len(parts) > 2 and parts[2].strip().lower() == "true")
                    ),
                )
            )
        return sorted(apps, key=lambda app: (not app.frontmost, app.name.lower()))

    def _process_fallback(self, *, active_app_name: str) -> list[AppInfo]:
        try:
            result = self._runner(
                ["ps", "-axo", "pid=,comm="],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.2,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if result.returncode != 0:
            return []
        apps: list[AppInfo] = []
        seen: set[str] = set()
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            pid_text, _, command = stripped.partition(" ")
            name = command.rsplit("/", 1)[-1]
            if not name or name in seen:
                continue
            seen.add(name)
            apps.append(
                AppInfo(
                    name=name,
                    process_id=_int_or_none(pid_text),
                    executable=command,
                    frontmost=name == active_app_name,
                )
            )
            if len(apps) >= 50:
                break
        return apps


def _open_app_command(app_name: str) -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return ["open", "-a", app_name]
    if system == "Windows":
        return ["cmd", "/c", "start", "", app_name]
    return ["gtk-launch", app_name]


def _run_launch(
    runner: Runner,
    command: list[str],
    *,
    action: str,
    target: str,
    app_name: str = "",
    workspace_path: str = "",
    coding_environment: str = "",
    privacy_mode: bool,
) -> LaunchResult:
    try:
        result = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return LaunchResult(
            action=action,
            target=target,
            status="failed",
            message=str(exc),
            app_name=app_name,
            workspace_path=workspace_path,
            coding_environment=coding_environment,
            command_preview=command,
            privacy_mode=privacy_mode,
        )

    ok = result.returncode == 0
    message = "launch requested" if ok else (result.stderr.strip() or "launch failed")
    return LaunchResult(
        action=action,
        target=target,
        status="launched" if ok else "failed",
        message=message,
        app_name=app_name,
        workspace_path=workspace_path,
        coding_environment=coding_environment,
        command_preview=command,
        privacy_mode=privacy_mode,
    )


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["AppController"]
