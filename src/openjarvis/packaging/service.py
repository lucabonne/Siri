"""Lightweight local app packaging service."""

from __future__ import annotations

import json
import platform
import plistlib
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import openjarvis
from openjarvis.packaging.models import (
    AppMetadata,
    PackagingCheck,
    PackagingPaths,
    PackagingStatus,
)


class PackagingService:
    """Generate and inspect the local macOS Siri app bundle.

    Phase 1 deliberately stays local: no notarization, updater, telemetry, or
    remote installer integration is attempted.
    """

    def __init__(self, *, project_root: str | Path | None = None) -> None:
        self.project_root = (
            Path(project_root).expanduser().resolve()
            if project_root
            else _default_project_root()
        )

    def status(self, *, integrations: dict[str, Any] | None = None) -> PackagingStatus:
        metadata = self.metadata()
        paths = self.paths(metadata)
        checks = self.environment_checks(metadata)
        blockers = [
            check.name
            for check in checks
            if check.required and check.status not in {"ok", "warning"}
        ]
        ready = not blockers
        bundle_path = self.default_bundle_path(metadata)
        return PackagingStatus(
            status="ready" if ready else "not_ready",
            metadata=metadata,
            paths=paths,
            app_bundle_path=str(bundle_path),
            app_bundle_exists=bundle_path.exists(),
            install_readiness={
                "ready": ready,
                "blockers": blockers,
                "warnings": [
                    check.name for check in checks if check.status == "warning"
                ],
                "local_only": True,
                "remote_installer": False,
                "notarization_required": False,
                "updater_required": False,
            },
            checks=checks,
            integrations=integrations or {},
            local_only=True,
            telemetry_enabled=False,
            remote_installer=False,
            notarization_enabled=False,
            updater_enabled=False,
        )

    def diagnostics(
        self,
        *,
        launcher_state: dict[str, Any] | None = None,
        integrations: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        status = self.status(integrations=integrations)
        return {
            "package_status": status.to_dict(),
            "launcher_state": self.launcher_state(
                desktop_launcher_state=launcher_state
            ),
            "environment_checks": [check.to_dict() for check in status.checks],
            "local_only": True,
            "telemetry_enabled": False,
            "remote_installer": False,
            "notarization_enabled": False,
            "updater_enabled": False,
        }

    def launcher_state(
        self,
        *,
        desktop_launcher_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = self.metadata()
        launcher = self.launcher_script
        return {
            "script": str(launcher),
            "script_exists": launcher.exists(),
            "single_command_launch": f"{launcher} launch",
            "single_command_restart": f"{launcher} restart",
            "supported_actions": [
                "launch",
                "start",
                "backend",
                "frontend",
                "restart",
                "stop",
                "status",
                "diagnostics",
            ],
            "backend_health_url": metadata.backend_health_url,
            "frontend_health_url": metadata.frontend_health_url,
            "desktop_launcher_state": desktop_launcher_state or {},
            "local_only": True,
            "telemetry_enabled": False,
        }

    def build_app_bundle(
        self,
        *,
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        metadata = self.metadata()
        output_root = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else self.default_output_dir
        )
        app_path = output_root / f"{metadata.name}.app"
        contents = app_path / "Contents"
        macos = contents / "MacOS"
        resources = contents / "Resources"

        macos.mkdir(parents=True, exist_ok=True)
        resources.mkdir(parents=True, exist_ok=True)

        plist = {
            "CFBundleName": metadata.name,
            "CFBundleDisplayName": metadata.display_name,
            "CFBundleIdentifier": metadata.bundle_identifier,
            "CFBundleVersion": _plist_version(metadata.version),
            "CFBundleShortVersionString": _plist_version(metadata.version),
            "CFBundleExecutable": metadata.name,
            "CFBundlePackageType": "APPL",
            "CFBundleIconFile": metadata.name,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        }
        with (contents / "Info.plist").open("wb") as handle:
            plistlib.dump(plist, handle, sort_keys=False)

        executable = macos / metadata.name
        executable.write_text(self._app_executable_script(), encoding="utf-8")
        _make_executable(executable)

        icon_source = self.icon_path(metadata)
        icon_copied = False
        if icon_source.exists():
            shutil.copy2(icon_source, resources / f"{metadata.name}.icns")
            icon_copied = True

        return {
            "status": "built",
            "app_bundle_path": str(app_path),
            "executable": str(executable),
            "info_plist": str(contents / "Info.plist"),
            "icon_copied": icon_copied,
            "icon_source": str(icon_source),
            "local_only": True,
            "telemetry_enabled": False,
            "remote_installer": False,
            "notarization_enabled": False,
            "updater_enabled": False,
        }

    def metadata(self) -> AppMetadata:
        metadata = AppMetadata(version=openjarvis.__version__)
        path = self.metadata_file
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                raw.setdefault("version", openjarvis.__version__)
                metadata = AppMetadata(**{**metadata.to_dict(), **raw})
            except Exception:
                return metadata
        if metadata.version == "0.0.0+source":
            metadata.version = openjarvis.__version__
        return metadata

    def paths(self, metadata: AppMetadata | None = None) -> PackagingPaths:
        metadata = metadata or self.metadata()
        return PackagingPaths(
            project_root=str(self.project_root),
            packaging_dir=str(self.packaging_dir),
            app_bundle_template_dir=str(self.packaging_dir / "app_bundle"),
            launcher_script=str(self.launcher_script),
            backend_bootstrap=str(self.packaging_dir / "scripts/bootstrap_backend.sh"),
            frontend_bootstrap=str(
                self.packaging_dir / "scripts/bootstrap_frontend.sh"
            ),
            metadata_file=str(self.metadata_file),
            icon_file=str(self.project_root / metadata.icon),
            fallback_icon_file=str(self.fallback_icon_path),
            default_output_dir=str(self.default_output_dir),
        )

    def environment_checks(
        self,
        metadata: AppMetadata | None = None,
    ) -> list[PackagingCheck]:
        metadata = metadata or self.metadata()
        checks = [
            PackagingCheck(
                name="macos_supported",
                status="ok" if platform.system() == "Darwin" else "blocked",
                message=platform.system(),
                required=True,
            ),
            _path_check("project_root", self.project_root),
            _path_check("packaging_directory", self.packaging_dir),
            _path_check("app_bundle_directory", self.packaging_dir / "app_bundle"),
            _path_check("launcher_script", self.launcher_script),
            _path_check(
                "backend_bootstrap",
                self.packaging_dir / "scripts/bootstrap_backend.sh",
            ),
            _path_check(
                "frontend_bootstrap",
                self.packaging_dir / "scripts/bootstrap_frontend.sh",
            ),
            _path_check("metadata_file", self.metadata_file),
            _path_check("frontend_directory", self.project_root / "frontend"),
            _path_check("pyproject", self.project_root / "pyproject.toml"),
            PackagingCheck(
                name="python",
                status="ok" if Path(sys.executable).exists() else "missing",
                message=sys.executable,
                required=True,
            ),
            PackagingCheck(
                name="jarvis_cli",
                status="ok" if shutil.which("jarvis") else "warning",
                message=shutil.which("jarvis") or "python -m openjarvis.cli fallback",
                required=False,
            ),
            PackagingCheck(
                name="npm",
                status="ok" if shutil.which("npm") else "warning",
                message=shutil.which("npm") or "frontend bootstrap needs npm",
                required=False,
            ),
        ]
        icon = self.icon_path(metadata)
        checks.append(
            PackagingCheck(
                name="icon",
                status="ok" if icon.exists() else "warning",
                message=str(icon) if icon.exists() else "no .icns icon found",
                required=False,
            )
        )
        return checks

    def icon_path(self, metadata: AppMetadata | None = None) -> Path:
        metadata = metadata or self.metadata()
        configured = self.project_root / metadata.icon
        if configured.exists():
            return configured
        return self.fallback_icon_path

    def default_bundle_path(self, metadata: AppMetadata | None = None) -> Path:
        metadata = metadata or self.metadata()
        return self.default_output_dir / f"{metadata.name}.app"

    @property
    def packaging_dir(self) -> Path:
        return self.project_root / "packaging"

    @property
    def metadata_file(self) -> Path:
        return self.packaging_dir / "config/app_metadata.json"

    @property
    def launcher_script(self) -> Path:
        return self.packaging_dir / "launchers/siri-launcher.sh"

    @property
    def fallback_icon_path(self) -> Path:
        return self.project_root / "frontend/src-tauri/icons/icon.icns"

    @property
    def default_output_dir(self) -> Path:
        return self.project_root / "build/packaging"

    def _app_executable_script(self) -> str:
        launcher = self.launcher_script
        return (
            "#!/bin/sh\n"
            "set -eu\n"
            f'export SIRI_PROJECT_ROOT="{self.project_root}"\n'
            f'exec "{launcher}" launch\n'
        )


def _path_check(name: str, path: Path, *, required: bool = True) -> PackagingCheck:
    return PackagingCheck(
        name=name,
        status="ok" if path.exists() else "missing",
        message=str(path),
        required=required,
    )


def _default_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "packaging").exists() and (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd().resolve()


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _plist_version(version: str) -> str:
    clean = version.split("+", 1)[0].split("-", 1)[0]
    return clean if clean and clean[0].isdigit() else "0.0.0"


__all__ = ["PackagingService"]
