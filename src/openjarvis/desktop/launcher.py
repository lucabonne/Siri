"""Explicit local launch helpers."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from openjarvis.desktop.apps import Runner, _run_launch
from openjarvis.desktop.models import LaunchResult


class DesktopLauncher:
    """Open local paths, repos, workspaces, and coding environments."""

    def __init__(self, *, runner: Runner | None = None) -> None:
        self._runner = runner or subprocess.run

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


def _resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _open_path_command(path: Path) -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return ["open", str(path)]
    if system == "Windows":
        return ["cmd", "/c", "start", "", str(path)]
    return ["xdg-open", str(path)]


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


__all__ = ["DesktopLauncher"]
