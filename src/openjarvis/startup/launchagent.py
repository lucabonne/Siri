"""macOS LaunchAgent helpers for starting Siri at login."""

from __future__ import annotations

import os
import platform
import plistlib
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from openjarvis.startup.models import LaunchAgentConfig, LaunchAgentStatus


def default_launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def default_program_arguments() -> list[str]:
    jarvis = shutil.which("jarvis")
    if jarvis:
        return [jarvis, "serve", "--host", "127.0.0.1"]
    return [sys.executable, "-m", "openjarvis.cli", "serve", "--host", "127.0.0.1"]


def default_launch_agent_config() -> LaunchAgentConfig:
    return LaunchAgentConfig(program_arguments=default_program_arguments())


class LaunchAgentManager:
    """Generate, install, remove, and validate the user LaunchAgent plist."""

    def __init__(
        self,
        *,
        config: LaunchAgentConfig | None = None,
        launch_agents_dir: str | Path | None = None,
    ) -> None:
        self.config = config or default_launch_agent_config()
        self.launch_agents_dir = (
            Path(launch_agents_dir).expanduser()
            if launch_agents_dir
            else default_launch_agents_dir()
        )

    @property
    def plist_path(self) -> Path:
        return self.launch_agents_dir / f"{self.config.label}.plist"

    def plist_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "Label": self.config.label,
            "ProgramArguments": self.config.program_arguments,
            "RunAtLoad": self.config.run_at_load,
            "KeepAlive": self.config.keep_alive,
            "StandardOutPath": self.config.standard_out_path,
            "StandardErrorPath": self.config.standard_error_path,
        }
        return payload

    def plist_bytes(self) -> bytes:
        return plistlib.dumps(self.plist_payload(), sort_keys=False)

    def install(self) -> LaunchAgentStatus:
        self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
        data = self.plist_bytes()
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.config.label}.",
            suffix=".plist",
            dir=str(self.launch_agents_dir),
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp_name, self.plist_path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return self.status()

    def remove(self) -> LaunchAgentStatus:
        try:
            self.plist_path.unlink()
        except FileNotFoundError:
            pass
        return self.status()

    def status(self) -> LaunchAgentStatus:
        supported = platform.system() == "Darwin"
        if not self.plist_path.exists():
            return LaunchAgentStatus(
                supported=supported,
                installed=False,
                valid=False,
                label=self.config.label,
                plist_path=str(self.plist_path),
                expected_program_arguments=list(self.config.program_arguments),
                error="" if supported else "LaunchAgent is only supported on macOS.",
            )

        try:
            with self.plist_path.open("rb") as handle:
                payload = plistlib.load(handle)
        except Exception as exc:
            return LaunchAgentStatus(
                supported=supported,
                installed=True,
                valid=False,
                label=self.config.label,
                plist_path=str(self.plist_path),
                expected_program_arguments=list(self.config.program_arguments),
                error=f"Invalid plist: {exc}",
            )

        installed_args = payload.get("ProgramArguments", [])
        valid = (
            payload.get("Label") == self.config.label
            and installed_args == self.config.program_arguments
            and bool(payload.get("RunAtLoad")) == self.config.run_at_load
        )
        return LaunchAgentStatus(
            supported=supported,
            installed=True,
            valid=valid,
            label=str(payload.get("Label") or self.config.label),
            plist_path=str(self.plist_path),
            expected_program_arguments=list(self.config.program_arguments),
            installed_program_arguments=(
                list(installed_args) if isinstance(installed_args, list) else []
            ),
            error="" if supported else "LaunchAgent is only supported on macOS.",
        )


__all__ = [
    "LaunchAgentManager",
    "default_launch_agent_config",
    "default_launch_agents_dir",
    "default_program_arguments",
]
