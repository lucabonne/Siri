"""Persisted local engineering workspace state."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from openjarvis.engineering.models import (
    CadFile,
    EngineeringProject,
    EngineeringWorkspaceState,
)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class EngineeringSessionStore:
    """Small JSON store for active engineering workspace state."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_projects: int = 12,
        max_files: int = 24,
    ) -> None:
        self.path = Path(path or Path.home() / ".openjarvis" / "engineering_state.json")
        self.max_projects = max_projects
        self.max_files = max_files

    def load(self) -> EngineeringWorkspaceState:
        if not self.path.exists():
            return EngineeringWorkspaceState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return EngineeringWorkspaceState()
        return EngineeringWorkspaceState(
            active_project=_project_from_dict(data.get("active_project")),
            recent_projects=[
                project
                for item in data.get("recent_projects", [])
                if (project := _project_from_dict(item)) is not None
            ],
            recent_files=[
                file
                for item in data.get("recent_files", [])
                if (file := _cad_file_from_dict(item)) is not None
            ],
            updated_at=str(data.get("updated_at", "")),
        )

    def record_project(self, project: EngineeringProject) -> EngineeringWorkspaceState:
        now = _utc_now()
        project.opened_at = now
        state = self.load()
        recent_projects = [
            item for item in state.recent_projects if item.id != project.id
        ]
        recent_projects.insert(0, project)
        recent_files = _dedupe_files(list(project.cad_files) + state.recent_files)
        state = EngineeringWorkspaceState(
            active_project=project,
            recent_projects=recent_projects[: self.max_projects],
            recent_files=recent_files[: self.max_files],
            updated_at=now,
        )
        self.save(state)
        return state

    def save(self, state: EngineeringWorkspaceState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _cad_file_from_dict(data: Any) -> CadFile | None:
    if not isinstance(data, dict):
        return None
    allowed = CadFile.__dataclass_fields__.keys()
    return CadFile(**{key: data[key] for key in allowed if key in data})


def _project_from_dict(data: Any) -> EngineeringProject | None:
    if not isinstance(data, dict):
        return None
    cad_files = [
        file
        for item in data.get("cad_files", [])
        if (file := _cad_file_from_dict(item)) is not None
    ]
    fields = {
        key: data[key]
        for key in EngineeringProject.__dataclass_fields__.keys()
        if key in data and key != "cad_files"
    }
    fields["cad_files"] = cad_files
    return EngineeringProject(**fields)


def _dedupe_files(files: list[CadFile]) -> list[CadFile]:
    seen: set[str] = set()
    result: list[CadFile] = []
    for item in files:
        if item.path in seen:
            continue
        result.append(item)
        seen.add(item.path)
    return result


__all__ = ["EngineeringSessionStore"]
