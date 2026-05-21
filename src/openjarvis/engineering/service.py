"""Coordinating service for Engineering / CAD Workspace Phase 1."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from openjarvis.engineering.analysis import summarize_project
from openjarvis.engineering.cad import scan_cad_files, supported_formats
from openjarvis.engineering.models import (
    CadFile,
    EngineeringProject,
    EngineeringProjectSummary,
    EngineeringStatus,
)
from openjarvis.engineering.projects import discover_projects, project_from_path
from openjarvis.engineering.sessions import EngineeringSessionStore


class EngineeringService:
    """Passive local engineering workspace coordinator.

    Phase 1 detects projects, tracks active workspace state, and summarizes
    local CAD files. It never edits CAD files, launches autonomous CAD actions,
    or uploads model data.
    """

    def __init__(
        self,
        *,
        root: str | os.PathLike[str] | None = None,
        session_store: EngineeringSessionStore | None = None,
        memory_service: Any = None,
        context_layer: Any = None,
        agent_workspace_registry: Any = None,
        research_service: Any = None,
        workflow_service: Any = None,
    ) -> None:
        self.root = Path(root or os.getcwd()).expanduser()
        self.session_store = session_store or EngineeringSessionStore()
        self.memory_service = memory_service
        self.context_layer = context_layer
        self.agent_workspace_registry = agent_workspace_registry
        self.research_service = research_service
        self.workflow_service = workflow_service

    def status(
        self,
        *,
        cwd: str | os.PathLike[str] | None = None,
        privacy_mode: bool = False,
    ) -> EngineeringStatus:
        root = Path(cwd).expanduser() if cwd else self.root
        projects = self.list_projects(root=root, limit=12)
        state = self.session_store.load()
        active_project = state.active_project
        if active_project is None and projects:
            active_project = projects[0]
        recent_files = self.recent_files(root=root, limit=12)
        return EngineeringStatus(
            active_project=active_project,
            projects=projects,
            recent_files=recent_files,
            workspace_state=state,
            supported_formats=supported_formats(),
            integrations=self._integration_snapshot(
                active_project,
                privacy_mode=privacy_mode,
            ),
            privacy_mode=privacy_mode,
        )

    def list_projects(
        self,
        *,
        root: str | os.PathLike[str] | None = None,
        limit: int = 24,
    ) -> list[EngineeringProject]:
        return discover_projects(root or self.root, limit=limit)

    def project_summary(
        self,
        path: str | os.PathLike[str],
        *,
        privacy_mode: bool = False,
    ) -> EngineeringProjectSummary:
        project = project_from_path(path)
        return summarize_project(project, privacy_mode=privacy_mode)

    def open_project(
        self,
        path: str | os.PathLike[str],
        *,
        requested_by: str = "user",
        privacy_mode: bool = False,
    ) -> EngineeringProject:
        if requested_by != "user":
            raise PermissionError("engineering projects must be opened by a user")
        target = Path(path).expanduser()
        if not target.exists():
            raise FileNotFoundError(str(path))
        project = project_from_path(target)
        if not project.cad_files and not project.markers:
            raise ValueError("no supported engineering files or markers detected")
        self.session_store.record_project(project)
        if not privacy_mode:
            self._record_memory(project)
        return project

    def recent_files(
        self,
        *,
        root: str | os.PathLike[str] | None = None,
        limit: int = 12,
    ) -> list[CadFile]:
        files = scan_cad_files(root or self.root, limit=max(limit, 1) * 8)
        files.sort(key=lambda item: item.modified_at, reverse=True)
        return files[: max(1, min(limit, 100))]

    def mission_control_snapshot(
        self,
        *,
        cwd: str | os.PathLike[str] | None = None,
        privacy_mode: bool = False,
    ) -> dict[str, Any]:
        status = self.status(cwd=cwd, privacy_mode=privacy_mode)
        return {
            "active_project": (
                status.active_project.to_dict() if status.active_project else None
            ),
            "recent_files": [item.to_dict() for item in status.recent_files],
            "workspace_state": status.workspace_state.to_dict(),
            "project_count": len(status.projects),
            "privacy_mode": privacy_mode,
            "local_only": True,
            "passive_only": True,
            "cloud_uploads_enabled": False,
            "autonomous_editing": False,
            "cad_modifications_enabled": False,
        }

    def _record_memory(self, project: EngineeringProject) -> None:
        if self.memory_service is None:
            return
        try:
            self.memory_service.create_memory(
                f"Engineering project opened: {project.name}",
                memory_type="engineering_project",
                metadata={
                    "project": project.to_dict(),
                    "local_only": True,
                    "passive_only": True,
                    "cloud_uploads_enabled": False,
                    "cad_modifications_enabled": False,
                },
                tags=["engineering", "cad", "project"],
            )
        except Exception:
            return

    def _integration_snapshot(
        self,
        active_project: EngineeringProject | None,
        *,
        privacy_mode: bool,
    ) -> dict[str, Any]:
        return {
            "desktop": {
                "active_project_path": active_project.path if active_project else "",
                "workspace_state": "active" if active_project else "idle",
                "local_only": True,
                "passive_only": True,
            },
            "memory": {
                "available": self.memory_service is not None,
                "writes_enabled": self.memory_service is not None and not privacy_mode,
                "memory_type": "engineering_project",
                "local_only": True,
            },
            "context": {
                "available": self.context_layer is not None,
                "project_context": active_project.to_dict() if active_project else None,
                "local_only": True,
                "passive_only": True,
            },
            "agent_workspace": {
                "available": self.agent_workspace_registry is not None,
                "recommended_agent": "engineering",
                "tools": [
                    "engineering_status",
                    "engineering_project_summary",
                    "engineering_recent_files",
                ],
            },
            "research": {
                "available": self.research_service is not None,
                "seed_source_type": "engineering_project_summary",
                "local_only": True,
            },
            "workflows": {
                "available": self.workflow_service is not None,
                "workflow_id": "open_engineering_workspace",
                "passive_only": True,
            },
        }


__all__ = ["EngineeringService"]
