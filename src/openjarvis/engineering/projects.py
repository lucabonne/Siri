"""Engineering project discovery and project model helpers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from openjarvis.engineering.cad import detect_engineering_project
from openjarvis.engineering.models import EngineeringProject


def project_id_for_path(path: str | os.PathLike[str]) -> str:
    resolved = str(Path(path).expanduser().resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
    return f"eng-{digest}"


def project_from_path(path: str | os.PathLike[str]) -> EngineeringProject:
    target = Path(path).expanduser()
    detection = detect_engineering_project(target)
    name = target.stem if target.is_file() else target.name
    summary = _summary(
        name,
        detection.project_kind,
        detection.formats,
        len(detection.cad_files),
    )
    return EngineeringProject(
        id=project_id_for_path(target),
        name=name or str(target),
        path=str(target),
        project_kind=detection.project_kind,
        formats=detection.formats,
        cad_files=detection.cad_files,
        markers=detection.markers,
        summary=summary,
    )


def discover_projects(
    root: str | os.PathLike[str],
    *,
    limit: int = 24,
    max_depth: int = 3,
) -> list[EngineeringProject]:
    """Discover local engineering project candidates under *root*."""

    base = Path(root).expanduser()
    if base.is_file():
        project = project_from_path(base)
        return [project] if project.cad_files else []
    if not base.exists() or not base.is_dir():
        return []

    projects: list[EngineeringProject] = []
    seen: set[str] = set()
    detection = detect_engineering_project(base, limit=80)
    if detection.is_engineering_project:
        project = project_from_path(base)
        projects.append(project)
        seen.add(project.id)

    base_depth = len(base.resolve().parts)
    for current, dirs, _filenames in os.walk(base):
        current_path = Path(current)
        depth = len(current_path.resolve().parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [
                name
                for name in dirs
                if not name.startswith(".")
                and name
                not in {
                    ".git",
                    "node_modules",
                    "__pycache__",
                    ".venv",
                    "target",
                    "build",
                    "dist",
                }
            ]
        for dirname in sorted(dirs):
            candidate = current_path / dirname
            detection = detect_engineering_project(candidate, limit=80)
            if not detection.is_engineering_project:
                continue
            project = project_from_path(candidate)
            if project.id in seen:
                continue
            projects.append(project)
            seen.add(project.id)
            if len(projects) >= limit:
                return projects
    return projects[:limit]


def _summary(name: str, project_kind: str, formats: list[str], count: int) -> str:
    if not count:
        return f"{name} has engineering markers but no supported CAD files."
    format_text = ", ".join(formats) if formats else "supported CAD"
    return f"{name} is a {project_kind} workspace with {count} {format_text} file(s)."


__all__ = ["discover_projects", "project_from_path", "project_id_for_path"]
