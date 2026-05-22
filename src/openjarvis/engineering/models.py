"""Typed models for passive engineering and CAD workspace support."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CadFile:
    """One locally detected engineering/CAD file."""

    path: str
    name: str
    format: str
    role: str = "model"
    size_bytes: int = 0
    modified_at: str = ""
    local_only: bool = True
    passive_only: bool = True
    uploaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CadDetection:
    """Detection result for a directory or file."""

    is_engineering_project: bool = False
    project_kind: str = "unknown"
    formats: list[str] = field(default_factory=list)
    cad_files: list[CadFile] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cad_files"] = [item.to_dict() for item in self.cad_files]
        return data


@dataclass(slots=True)
class EngineeringProject:
    """A local engineering project candidate."""

    id: str
    name: str
    path: str
    project_kind: str = "unknown"
    formats: list[str] = field(default_factory=list)
    cad_files: list[CadFile] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    summary: str = ""
    opened_at: str = ""
    local_only: bool = True
    passive_only: bool = True
    autonomous_editing: bool = False
    cad_modifications_enabled: bool = False
    cloud_uploads_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cad_files"] = [item.to_dict() for item in self.cad_files]
        return data


@dataclass(slots=True)
class EngineeringProjectSummary:
    """Compact project summary for APIs and Mission Control."""

    project: EngineeringProject
    file_count: int = 0
    formats: dict[str, int] = field(default_factory=dict)
    largest_files: list[CadFile] = field(default_factory=list)
    recent_files: list[CadFile] = field(default_factory=list)
    viewer_hints: list[dict[str, Any]] = field(default_factory=list)
    analysis_notes: list[str] = field(default_factory=list)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True
    cloud_uploaded: bool = False
    autonomous_editing: bool = False
    cad_modifications_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "file_count": self.file_count,
            "formats": dict(self.formats),
            "largest_files": [item.to_dict() for item in self.largest_files],
            "recent_files": [item.to_dict() for item in self.recent_files],
            "viewer_hints": list(self.viewer_hints),
            "analysis_notes": list(self.analysis_notes),
            "privacy_mode": self.privacy_mode,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "cloud_uploaded": self.cloud_uploaded,
            "autonomous_editing": self.autonomous_editing,
            "cad_modifications_enabled": self.cad_modifications_enabled,
        }


@dataclass(slots=True)
class EngineeringWorkspaceState:
    """Persisted engineering workspace state."""

    active_project: EngineeringProject | None = None
    recent_projects: list[EngineeringProject] = field(default_factory=list)
    recent_files: list[CadFile] = field(default_factory=list)
    updated_at: str = ""
    local_only: bool = True
    passive_only: bool = True
    cloud_uploads_enabled: bool = False
    autonomous_editing: bool = False
    cad_modifications_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_project": (
                self.active_project.to_dict() if self.active_project else None
            ),
            "recent_projects": [item.to_dict() for item in self.recent_projects],
            "recent_files": [item.to_dict() for item in self.recent_files],
            "updated_at": self.updated_at,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "cloud_uploads_enabled": self.cloud_uploads_enabled,
            "autonomous_editing": self.autonomous_editing,
            "cad_modifications_enabled": self.cad_modifications_enabled,
        }


@dataclass(slots=True)
class EngineeringStatus:
    """Mission Control-ready engineering status."""

    active_project: EngineeringProject | None = None
    projects: list[EngineeringProject] = field(default_factory=list)
    recent_files: list[CadFile] = field(default_factory=list)
    workspace_state: EngineeringWorkspaceState = field(
        default_factory=EngineeringWorkspaceState,
    )
    supported_formats: list[str] = field(default_factory=list)
    integrations: dict[str, Any] = field(default_factory=dict)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True
    cloud_uploads_enabled: bool = False
    autonomous_editing: bool = False
    cad_modifications_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_project": (
                self.active_project.to_dict() if self.active_project else None
            ),
            "projects": [item.to_dict() for item in self.projects],
            "recent_files": [item.to_dict() for item in self.recent_files],
            "workspace_state": self.workspace_state.to_dict(),
            "supported_formats": list(self.supported_formats),
            "integrations": dict(self.integrations),
            "privacy_mode": self.privacy_mode,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "cloud_uploads_enabled": self.cloud_uploads_enabled,
            "autonomous_editing": self.autonomous_editing,
            "cad_modifications_enabled": self.cad_modifications_enabled,
        }


__all__ = [
    "CadDetection",
    "CadFile",
    "EngineeringProject",
    "EngineeringProjectSummary",
    "EngineeringStatus",
    "EngineeringWorkspaceState",
]
