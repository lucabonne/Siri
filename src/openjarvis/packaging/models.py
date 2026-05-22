"""Typed models for local Siri packaging status."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AppMetadata:
    """Static app metadata used for the local macOS bundle."""

    name: str = "Siri"
    display_name: str = "Siri"
    bundle_identifier: str = "com.openjarvis.siri"
    version: str = "0.0.0+source"
    icon: str = "packaging/icons/Siri.icns"
    backend_health_url: str = "http://127.0.0.1:8000/health"
    frontend_health_url: str = "http://127.0.0.1:5173"
    local_only: bool = True
    telemetry_enabled: bool = False
    remote_installer: bool = False
    notarization: bool = False
    updater: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PackagingCheck:
    """One packaging readiness or diagnostics check."""

    name: str
    status: str
    message: str = ""
    required: bool = True
    local_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PackagingPaths:
    """Important local paths used by the packaging layer."""

    project_root: str
    packaging_dir: str
    app_bundle_template_dir: str
    launcher_script: str
    installer_script: str
    uninstaller_script: str
    release_diagnostics_script: str
    script_command: str
    backend_bootstrap: str
    frontend_bootstrap: str
    metadata_file: str
    icon_file: str
    fallback_icon_file: str
    default_output_dir: str
    user_applications_dir: str
    system_applications_dir: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PackagingStatus:
    """Mission Control package status and install readiness."""

    status: str
    metadata: AppMetadata
    paths: PackagingPaths
    app_bundle_path: str
    app_bundle_exists: bool
    install_readiness: dict[str, Any]
    installation: dict[str, Any] = field(default_factory=dict)
    checks: list[PackagingCheck] = field(default_factory=list)
    integrations: dict[str, Any] = field(default_factory=dict)
    local_only: bool = True
    telemetry_enabled: bool = False
    remote_installer: bool = False
    notarization_enabled: bool = False
    updater_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "metadata": self.metadata.to_dict(),
            "paths": self.paths.to_dict(),
            "app_bundle_path": self.app_bundle_path,
            "app_bundle_exists": self.app_bundle_exists,
            "install_readiness": dict(self.install_readiness),
            "installation": dict(self.installation),
            "checks": [check.to_dict() for check in self.checks],
            "integrations": self.integrations,
            "local_only": self.local_only,
            "telemetry_enabled": self.telemetry_enabled,
            "remote_installer": self.remote_installer,
            "notarization_enabled": self.notarization_enabled,
            "updater_enabled": self.updater_enabled,
        }


__all__ = [
    "AppMetadata",
    "PackagingCheck",
    "PackagingPaths",
    "PackagingStatus",
]
