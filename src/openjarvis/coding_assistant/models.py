"""Typed models for passive coding assistant intelligence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CodingStackProfile:
    """Detected developer stack plus specialized coding signals."""

    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    build_systems: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    specializations: list[str] = field(default_factory=list)
    project_type: str = "unknown"
    java_version: str = ""
    minecraft_version: str = ""
    loom_version: str = ""
    node_package_manager: str = ""
    vite_present: bool = False
    rust_workspace: bool = False
    python_project: bool = False
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BuildFailure:
    """One classified build/debug failure."""

    category: str
    severity: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    likely_causes: list[str] = field(default_factory=list)
    safe_fixes: list[str] = field(default_factory=list)
    related_stack: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SafeFixSuggestion:
    """A passive fix recommendation, optionally with a dry-run command preview."""

    title: str
    rationale: str
    steps: list[str] = field(default_factory=list)
    risk: str = "low"
    command: str = ""
    permission_preview: dict[str, Any] = field(default_factory=dict)
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BuildAnalysis:
    """Local build output analysis."""

    has_failure: bool = False
    status: str = "unknown"
    command: str = ""
    exit_code: int | None = None
    summary: str = ""
    failures: list[BuildFailure] = field(default_factory=list)
    suggested_fixes: list[SafeFixSuggestion] = field(default_factory=list)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["failures"] = [item.to_dict() for item in self.failures]
        data["suggested_fixes"] = [item.to_dict() for item in self.suggested_fixes]
        return data


@dataclass(slots=True)
class ArchitectureExplanation:
    """Repo-aware architecture explanation."""

    summary: str
    entry_points: list[str] = field(default_factory=list)
    major_systems: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[dict[str, str]] = field(default_factory=list)
    risky_refactors: list[str] = field(default_factory=list)
    debugging_entry_points: list[str] = field(default_factory=list)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DebuggingSummary:
    """Repo and terminal aware debugging overview."""

    summary: str
    recent_errors: list[BuildFailure] = field(default_factory=list)
    debugging_steps: list[str] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)
    terminal_context: dict[str, Any] = field(default_factory=dict)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["recent_errors"] = [item.to_dict() for item in self.recent_errors]
        return data


@dataclass(slots=True)
class ProjectHealthSummary:
    """Passive project health rollup for developer workflows."""

    status: str
    score: int
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    stack: CodingStackProfile = field(default_factory=CodingStackProfile)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stack"] = self.stack.to_dict()
        return data


@dataclass(slots=True)
class CodingPanelSnapshot:
    """Mission Control coding panel data."""

    build_health: BuildAnalysis
    repo_health: ProjectHealthSummary
    current_stack: CodingStackProfile
    recent_errors: list[BuildFailure] = field(default_factory=list)
    suggested_fixes: list[SafeFixSuggestion] = field(default_factory=list)
    architecture_overview: ArchitectureExplanation | None = None
    active_agent: dict[str, Any] = field(default_factory=dict)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True
    cloud_uploaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "build_health": self.build_health.to_dict(),
            "repo_health": self.repo_health.to_dict(),
            "current_stack": self.current_stack.to_dict(),
            "recent_errors": [item.to_dict() for item in self.recent_errors],
            "suggested_fixes": [item.to_dict() for item in self.suggested_fixes],
            "architecture_overview": (
                self.architecture_overview.to_dict()
                if self.architecture_overview is not None
                else None
            ),
            "active_agent": self.active_agent,
            "privacy_mode": self.privacy_mode,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "cloud_uploaded": self.cloud_uploaded,
        }


__all__ = [
    "ArchitectureExplanation",
    "BuildAnalysis",
    "BuildFailure",
    "CodingPanelSnapshot",
    "CodingStackProfile",
    "DebuggingSummary",
    "ProjectHealthSummary",
    "SafeFixSuggestion",
]
