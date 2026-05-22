"""Typed local release hardening models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ReleaseCheck:
    """One release readiness check."""

    id: str
    label: str
    category: str
    status: str
    summary: str
    detail: str = ""
    required: bool = True
    repair_action: str = ""
    local_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StartupDiagnostic:
    """One startup diagnostic item."""

    id: str
    label: str
    status: str
    summary: str
    detail: str = ""
    required: bool = True
    local_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RecoveryAction:
    """A local repair helper exposed to Mission Control."""

    id: str
    label: str
    description: str
    status: str = "available"
    requires_confirmation: bool = True
    local_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RecoveryResult:
    """Result of a local repair helper."""

    action: str
    status: str
    summary: str
    changed_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    local_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReleaseReport:
    """Aggregated release readiness report."""

    installed_components: list[dict[str, Any]]
    enabled_modules: list[str]
    warnings: list[str]
    readiness_score: int
    readiness_status: str
    local_only: bool = True
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReleaseHealthSnapshot:
    """Mission Control release hardening snapshot."""

    health_checks: list[ReleaseCheck]
    diagnostics: list[StartupDiagnostic]
    recovery_actions: list[RecoveryAction]
    report: ReleaseReport
    privacy_mode: dict[str, Any]
    packaging_status: dict[str, Any] = field(default_factory=dict)
    install_readiness: dict[str, Any] = field(default_factory=dict)
    local_only: bool = True
    telemetry_enabled: bool = False
    autonomous_agents: bool = False
    wake_words: bool = False
    intelligence_features: bool = False
    active_profile_summary: dict[str, Any] = field(default_factory=dict)
    wake_status: dict[str, Any] = field(default_factory=dict)
    readiness_state: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "health_checks": [check.to_dict() for check in self.health_checks],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "recovery_actions": [
                action.to_dict() for action in self.recovery_actions
            ],
            "report": self.report.to_dict(),
            "privacy_mode": dict(self.privacy_mode),
            "packaging_status": dict(self.packaging_status),
            "install_readiness": dict(self.install_readiness),
            "local_only": self.local_only,
            "telemetry_enabled": self.telemetry_enabled,
            "autonomous_agents": self.autonomous_agents,
            "wake_words": self.wake_words,
            "intelligence_features": self.intelligence_features,
            "active_profile_summary": dict(self.active_profile_summary),
            "wake_status": dict(self.wake_status),
            "readiness_state": self.readiness_state,
        }


__all__ = [
    "RecoveryAction",
    "RecoveryResult",
    "ReleaseCheck",
    "ReleaseHealthSnapshot",
    "ReleaseReport",
    "StartupDiagnostic",
]
