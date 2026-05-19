"""Explicit local launch helpers."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen

from openjarvis.desktop.apps import Runner, _run_launch
from openjarvis.desktop.models import (
    DesktopLauncherState,
    LauncherHealthCheck,
    LaunchResult,
)
from openjarvis.desktop.sessions import utc_now

PopenFactory = Callable[..., subprocess.Popen]
HealthProbe = Callable[[str, float], tuple[bool, str]]


class DesktopLauncher:
    """Open local paths, repos, workspaces, and coding environments."""

    def __init__(
        self,
        *,
        runner: Runner | None = None,
        popen_factory: PopenFactory | None = None,
        health_probe: HealthProbe | None = None,
        project_root: str | Path | None = None,
    ) -> None:
        self._runner = runner or subprocess.run
        self._popen_factory = popen_factory or subprocess.Popen
        self._health_probe = health_probe or _http_health_probe
        self._project_root = Path(project_root).expanduser() if project_root else None
        self._backend_process: subprocess.Popen | None = None
        self._frontend_process: subprocess.Popen | None = None
        self._backend_command: list[str] = []
        self._frontend_command: list[str] = []
        self._health_checks: list[LauncherHealthCheck] = []
        self._last_action = ""
        self._last_restart_at = ""

    def open_repo(
        self,
        path: str | Path,
        *,
        privacy_mode: bool = False,
    ) -> LaunchResult:
        repo = _resolve_path(path)
        if not repo.exists():
            return _missing("open_repo", repo, privacy_mode)
        return self._open_path(
            repo,
            action="open_repo",
            target=str(repo),
            workspace_path=str(repo),
            privacy_mode=privacy_mode,
        )

    def open_workspace(
        self,
        path: str | Path,
        *,
        app_name: str = "",
        privacy_mode: bool = False,
    ) -> LaunchResult:
        workspace = _resolve_path(path)
        if not workspace.exists():
            return _missing("open_workspace", workspace, privacy_mode)
        if app_name.strip():
            command = _open_path_with_app_command(workspace, app_name.strip())
            return _run_launch(
                self._runner,
                command,
                action="open_workspace",
                target=str(workspace),
                app_name=app_name.strip(),
                workspace_path=str(workspace),
                privacy_mode=privacy_mode,
            )
        return self._open_path(
            workspace,
            action="open_workspace",
            target=str(workspace),
            workspace_path=str(workspace),
            privacy_mode=privacy_mode,
        )

    def launch_coding_environment(
        self,
        path: str | Path,
        *,
        coding_environment: str = "",
        privacy_mode: bool = False,
    ) -> LaunchResult:
        workspace = _resolve_path(path)
        if not workspace.exists():
            return _missing("launch_coding_environment", workspace, privacy_mode)
        editor = (
            coding_environment.strip()
            or os.environ.get("OPENJARVIS_CODE_EDITOR", "").strip()
            or _default_editor()
        )
        if not editor:
            result = self.open_workspace(workspace, privacy_mode=privacy_mode)
            result.action = "launch_coding_environment"
            result.coding_environment = "system_default"
            return result
        command = [editor, str(workspace)]
        return _run_launch(
            self._runner,
            command,
            action="launch_coding_environment",
            target=str(workspace),
            workspace_path=str(workspace),
            coding_environment=editor,
            privacy_mode=privacy_mode,
        )

    def open_mission_control(self, *, privacy_mode: bool = False) -> LaunchResult:
        """Open the local Mission Control route in the system browser."""
        base_url = os.environ.get("OPENJARVIS_FRONTEND_URL", "http://127.0.0.1:5173")
        target = f"{base_url.rstrip('/')}/mission-control"
        return _run_launch(
            self._runner,
            _open_url_command(target),
            action="open_mission_control",
            target=target,
            privacy_mode=privacy_mode,
        )

    def state(self) -> DesktopLauncherState:
        return DesktopLauncherState(
            backend_status=self._process_status(self._backend_process),
            frontend_status=self._process_status(self._frontend_process),
            backend_command=list(self._backend_command),
            frontend_command=list(self._frontend_command),
            health_checks=list(self._health_checks),
            last_action=self._last_action,
            last_restart_at=self._last_restart_at,
        )

    def health_checks(
        self,
        *,
        backend_url: str = "http://127.0.0.1:8000/health",
        frontend_url: str = "http://127.0.0.1:5173",
        timeout: float = 1.0,
    ) -> DesktopLauncherState:
        checks = []
        for name, url in (("backend", backend_url), ("frontend", frontend_url)):
            ok, message = self._health_probe(url, timeout)
            checks.append(
                LauncherHealthCheck(
                    name=name,
                    status="healthy" if ok else "unavailable",
                    url=url,
                    message=message,
                    checked_at=utc_now(),
                )
            )
        self._health_checks = checks
        self._last_action = "health_checks"
        return self.state()

    def start_backend(
        self,
        command: list[str] | None = None,
    ) -> DesktopLauncherState:
        if self._is_running(self._backend_process):
            self._last_action = "start_backend"
            return self.state()
        self._backend_command = list(command or ["jarvis", "serve"])
        self._backend_process = self._popen_factory(
            self._backend_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._last_action = "start_backend"
        return self.state()

    def start_frontend(
        self,
        command: list[str] | None = None,
    ) -> DesktopLauncherState:
        if self._is_running(self._frontend_process):
            self._last_action = "start_frontend"
            return self.state()
        frontend_dir = self._frontend_dir()
        self._frontend_command = list(
            command or ["npm", "run", "dev", "--", "--host", "127.0.0.1"]
        )
        self._frontend_process = self._popen_factory(
            self._frontend_command,
            cwd=str(frontend_dir) if frontend_dir.exists() else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._last_action = "start_frontend"
        return self.state()

    def restart_backend(
        self,
        command: list[str] | None = None,
    ) -> DesktopLauncherState:
        self._terminate(self._backend_process)
        self._backend_process = None
        self._last_restart_at = utc_now()
        return self.start_backend(command or self._backend_command or None)

    def restart_frontend(
        self,
        command: list[str] | None = None,
    ) -> DesktopLauncherState:
        self._terminate(self._frontend_process)
        self._frontend_process = None
        self._last_restart_at = utc_now()
        return self.start_frontend(command or self._frontend_command or None)

    def restart_all(self) -> DesktopLauncherState:
        self.restart_backend()
        self.restart_frontend()
        self._last_action = "restart"
        self._last_restart_at = utc_now()
        return self.state()

    def _open_path(
        self,
        path: Path,
        *,
        action: str,
        target: str,
        workspace_path: str,
        privacy_mode: bool,
    ) -> LaunchResult:
        return _run_launch(
            self._runner,
            _open_path_command(path),
            action=action,
            target=target,
            workspace_path=workspace_path,
            privacy_mode=privacy_mode,
        )

    def _frontend_dir(self) -> Path:
        if self._project_root is not None:
            return self._project_root / "frontend"
        return Path(__file__).resolve().parents[3] / "frontend"

    @staticmethod
    def _is_running(process: subprocess.Popen | None) -> bool:
        return process is not None and process.poll() is None

    @staticmethod
    def _process_status(process: subprocess.Popen | None) -> str:
        if process is None:
            return "stopped"
        return "running" if process.poll() is None else "exited"

    @staticmethod
    def _terminate(process: subprocess.Popen | None) -> None:
        if process is None or process.poll() is not None:
            return
        process.terminate()


def _resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _open_path_command(path: Path) -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return ["open", str(path)]
    if system == "Windows":
        return ["cmd", "/c", "start", "", str(path)]
    return ["xdg-open", str(path)]


def _open_url_command(url: str) -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return ["open", url]
    if system == "Windows":
        return ["cmd", "/c", "start", "", url]
    return ["xdg-open", url]


def _open_path_with_app_command(path: Path, app_name: str) -> list[str]:
    if platform.system() == "Darwin":
        return ["open", "-a", app_name, str(path)]
    return [app_name, str(path)]


def _default_editor() -> str:
    for candidate in ("code", "codium", "cursor"):
        if shutil.which(candidate):
            return candidate
    return ""


def _missing(action: str, path: Path, privacy_mode: bool) -> LaunchResult:
    return LaunchResult(
        action=action,
        target=str(path),
        status="failed",
        message=f"path does not exist: {path}",
        workspace_path=str(path),
        privacy_mode=privacy_mode,
    )


def _http_health_probe(url: str, timeout: float) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if 200 <= status < 400:
                return True, f"HTTP {status}"
            return False, f"HTTP {status}"
    except (OSError, URLError) as exc:
        return False, str(exc)


__all__ = ["DesktopLauncher"]
