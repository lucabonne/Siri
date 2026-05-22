"""Lightweight local app packaging service."""

from __future__ import annotations

import json
import os
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
from openjarvis.startup.launchagent import LaunchAgentManager
from openjarvis.startup.models import LaunchAgentConfig


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
        installation = self.installation_status(metadata=metadata)
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
                "destinations": {
                    "user": str(self.user_applications_dir / f"{metadata.name}.app"),
                    "system": str(
                        self.system_applications_dir / f"{metadata.name}.app"
                    ),
                },
                "launch_agent_label": metadata.bundle_identifier,
            },
            installation=installation,
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
            "installation": status.installation,
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
        self._ensure_packaging_script_permissions()
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
        bundled_packaging = resources / "packaging"
        self._copy_runtime_scripts(bundled_packaging)

        return {
            "status": "built",
            "app_bundle_path": str(app_path),
            "executable": str(executable),
            "info_plist": str(contents / "Info.plist"),
            "bundled_packaging": str(bundled_packaging),
            "icon_copied": icon_copied,
            "icon_source": str(icon_source),
            "local_only": True,
            "telemetry_enabled": False,
            "remote_installer": False,
            "notarization_enabled": False,
            "updater_enabled": False,
        }

    def install_app_bundle(
        self,
        *,
        destination: str = "user",
        install_launch_agent: bool = True,
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        metadata = self.metadata()
        destination_root = self._destination_root(destination)
        build = self.build_app_bundle(output_dir=output_dir)
        built_app = Path(build["app_bundle_path"])
        installed_app = destination_root / f"{metadata.name}.app"

        destination_root.mkdir(parents=True, exist_ok=True)
        self._replace_app_bundle(built_app, installed_app)

        launch_agent: dict[str, Any] = {"installed": False, "skipped": True}
        if install_launch_agent:
            manager = self.launch_agent_manager(installed_app)
            launch_agent = manager.install().to_dict()
            launch_agent["skipped"] = False
            launch_agent["program"] = str(self.app_executable(installed_app))

        return {
            "status": "installed",
            "app_bundle_path": str(installed_app),
            "destination": destination,
            "launch_agent": launch_agent,
            "installation": self.installation_status(metadata=metadata),
            "local_only": True,
            "telemetry_enabled": False,
            "remote_installer": False,
            "notarization_enabled": False,
            "updater_enabled": False,
        }

    def uninstall_app_bundle(
        self,
        *,
        remove_launch_agent: bool = True,
        destinations: list[str] | None = None,
    ) -> dict[str, Any]:
        metadata = self.metadata()
        destination_names = destinations or ["user", "system"]
        removed_paths: list[str] = []
        warnings: list[str] = []

        launch_agent: dict[str, Any] = {"removed": False, "skipped": True}
        if remove_launch_agent:
            manager = self.launch_agent_manager()
            launch_agent = manager.remove().to_dict()
            launch_agent["removed"] = True
            launch_agent["skipped"] = False

        for destination in destination_names:
            app_path = self._destination_root(destination) / f"{metadata.name}.app"
            if not app_path.exists():
                continue
            try:
                shutil.rmtree(app_path)
                removed_paths.append(str(app_path))
            except OSError as exc:
                warnings.append(f"{app_path}: {exc}")

        return {
            "status": "uninstalled" if not warnings else "partial",
            "removed_paths": removed_paths,
            "warnings": warnings,
            "launch_agent": launch_agent,
            "installation": self.installation_status(metadata=metadata),
            "local_only": True,
            "telemetry_enabled": False,
            "remote_installer": False,
            "notarization_enabled": False,
            "updater_enabled": False,
        }

    def release_diagnostics(self) -> dict[str, Any]:
        status = self.status()
        return {
            "status": status.to_dict(),
            "launcher": self.launcher_state(),
            "installation": status.installation,
            "dependency_summary": {
                check.name: {
                    "status": check.status,
                    "message": check.message,
                    "required": check.required,
                }
                for check in status.checks
                if check.name
                in {
                    "python",
                    "uv",
                    "node",
                    "npm",
                    "ollama",
                    "ffmpeg",
                    "macos_permissions_guidance",
                }
            },
            "local_only": True,
            "telemetry_enabled": False,
            "remote_installer": False,
            "notarization_enabled": False,
            "updater_enabled": False,
        }

    def installation_status(
        self,
        *,
        metadata: AppMetadata | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or self.metadata()
        user_app = self.user_applications_dir / f"{metadata.name}.app"
        system_app = self.system_applications_dir / f"{metadata.name}.app"
        installed_locations = [
            str(path) for path in (user_app, system_app) if path.exists()
        ]
        preferred_app = (
            Path(installed_locations[0]) if installed_locations else user_app
        )
        launch_agent = self.launch_agent_manager(preferred_app).status().to_dict()
        return {
            "installed": bool(installed_locations),
            "installed_locations": installed_locations,
            "user_app_path": str(user_app),
            "system_app_path": str(system_app),
            "preferred_app_path": str(preferred_app),
            "app_executable": str(self.app_executable(preferred_app)),
            "launch_agent": launch_agent,
            "local_only": True,
            "telemetry_enabled": False,
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
            installer_script=str(self.packaging_dir / "scripts/install_macos.sh"),
            uninstaller_script=str(self.packaging_dir / "scripts/uninstall_macos.sh"),
            release_diagnostics_script=str(
                self.packaging_dir / "scripts/release_diagnostics.sh"
            ),
            script_command=str(self.packaging_dir / "scripts/package_app.py"),
            backend_bootstrap=str(self.packaging_dir / "scripts/bootstrap_backend.sh"),
            frontend_bootstrap=str(
                self.packaging_dir / "scripts/bootstrap_frontend.sh"
            ),
            metadata_file=str(self.metadata_file),
            icon_file=str(self.project_root / metadata.icon),
            fallback_icon_file=str(self.fallback_icon_path),
            default_output_dir=str(self.default_output_dir),
            user_applications_dir=str(self.user_applications_dir),
            system_applications_dir=str(self.system_applications_dir),
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
            _path_check("launcher_script", self.launcher_script, executable=True),
            _path_check(
                "installer_script",
                self.packaging_dir / "scripts/install_macos.sh",
                executable=True,
            ),
            _path_check(
                "uninstaller_script",
                self.packaging_dir / "scripts/uninstall_macos.sh",
                executable=True,
            ),
            _path_check(
                "release_diagnostics_script",
                self.packaging_dir / "scripts/release_diagnostics.sh",
                executable=True,
            ),
            _path_check(
                "script_command",
                self.packaging_dir / "scripts/package_app.py",
                executable=True,
            ),
            _path_check(
                "backend_bootstrap",
                self.packaging_dir / "scripts/bootstrap_backend.sh",
                executable=True,
            ),
            _path_check(
                "frontend_bootstrap",
                self.packaging_dir / "scripts/bootstrap_frontend.sh",
                executable=True,
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
            _command_check("uv", required=True, fallback="Install uv before release."),
            _command_check(
                "node",
                required=True,
                fallback="Install Node.js before launching the frontend.",
            ),
            _command_check(
                "npm",
                required=True,
                fallback="Install npm before launching the frontend.",
            ),
            _command_check(
                "ollama",
                required=True,
                fallback="Install Ollama before validating local models.",
            ),
            _command_check(
                "ffmpeg",
                required=True,
                fallback=(
                    "Install ffmpeg before validating audio features "
                    "(macOS: brew install ffmpeg)."
                ),
            ),
            PackagingCheck(
                name="jarvis_cli",
                status="ok" if shutil.which("jarvis") else "warning",
                message=shutil.which("jarvis") or "python -m openjarvis.cli fallback",
                required=False,
            ),
            PackagingCheck(
                name="macos_permissions_guidance",
                status="guidance",
                message=(
                    "Grant Microphone, Accessibility, Screen Recording, and "
                    "Notifications in System Settings when enabling voice, hotkeys, "
                    "screen context, or local notifications."
                ),
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

    def app_executable(self, app_path: str | Path) -> Path:
        metadata = self.metadata()
        return Path(app_path) / "Contents" / "MacOS" / metadata.name

    def launch_agent_manager(
        self,
        app_path: str | Path | None = None,
    ) -> LaunchAgentManager:
        metadata = self.metadata()
        if app_path is not None:
            program_arguments = ["/bin/bash", str(self.app_executable(app_path))]
        else:
            program_arguments = ["/bin/bash", str(self.launcher_script), "launch"]
        return LaunchAgentManager(
            config=LaunchAgentConfig(
                label=metadata.bundle_identifier,
                program_arguments=program_arguments,
            )
        )

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

    @property
    def user_applications_dir(self) -> Path:
        return Path.home() / "Applications"

    @property
    def system_applications_dir(self) -> Path:
        return Path("/Applications")

    def _destination_root(self, destination: str) -> Path:
        if destination == "user":
            return self.user_applications_dir
        if destination == "system":
            return self.system_applications_dir
        raise ValueError("destination must be 'user' or 'system'")

    def _replace_app_bundle(self, source: Path, destination: Path) -> None:
        staging = destination.with_name(f".{destination.name}.installing")
        backup = destination.with_name(f".{destination.name}.previous")
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists():
            shutil.rmtree(backup)
        shutil.copytree(source, staging, symlinks=True)
        try:
            if destination.exists():
                destination.rename(backup)
            staging.rename(destination)
        except Exception:
            if destination.exists():
                shutil.rmtree(destination)
            if backup.exists():
                backup.rename(destination)
            raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)
            if backup.exists():
                shutil.rmtree(backup)

    def _ensure_packaging_script_permissions(self) -> None:
        for path in (
            self.launcher_script,
            self.packaging_dir / "scripts/bootstrap_backend.sh",
            self.packaging_dir / "scripts/bootstrap_frontend.sh",
            self.packaging_dir / "scripts/install_macos.sh",
            self.packaging_dir / "scripts/uninstall_macos.sh",
            self.packaging_dir / "scripts/release_diagnostics.sh",
            self.packaging_dir / "scripts/package_app.py",
        ):
            if path.exists():
                _make_executable(path)

    def _copy_runtime_scripts(self, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        (destination / "launchers").mkdir(parents=True, exist_ok=True)
        (destination / "scripts").mkdir(parents=True, exist_ok=True)
        for source, target in (
            (
                self.packaging_dir / "launchers/siri-launcher.sh",
                destination / "launchers/siri-launcher.sh",
            ),
            (
                self.packaging_dir / "scripts/bootstrap_backend.sh",
                destination / "scripts/bootstrap_backend.sh",
            ),
            (
                self.packaging_dir / "scripts/bootstrap_frontend.sh",
                destination / "scripts/bootstrap_frontend.sh",
            ),
        ):
            shutil.copy2(source, target)
            _make_executable(target)

    def _app_executable_script(self) -> str:
        bundled_packaging = (
            "$(CDPATH= cd -- \"$(dirname -- \"$0\")/../Resources/packaging\" && pwd)"
        )
        return (
            "#!/bin/bash\n"
            "set -eu\n"
            f'export SIRI_PROJECT_ROOT="{self.project_root}"\n'
            f'export SIRI_PACKAGING_ROOT="{bundled_packaging}"\n'
            'exec /bin/bash "$SIRI_PACKAGING_ROOT/launchers/siri-launcher.sh" launch\n'
        )


def _path_check(
    name: str,
    path: Path,
    *,
    required: bool = True,
    executable: bool = False,
) -> PackagingCheck:
    exists = path.exists()
    can_execute = os.access(path, os.X_OK) if exists and executable else True
    status = "ok" if exists and can_execute else "missing" if not exists else "blocked"
    return PackagingCheck(
        name=name,
        status=status,
        message=str(path),
        required=required,
    )


def _command_check(name: str, *, required: bool, fallback: str) -> PackagingCheck:
    path = _which_command(name)
    return PackagingCheck(
        name=name,
        status="ok" if path else "missing",
        message=path or fallback,
        required=required,
    )


def _which_command(name: str) -> str | None:
    path = shutil.which(name)
    if path:
        return path
    for directory in ("/opt/homebrew/bin", "/usr/local/bin"):
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


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
