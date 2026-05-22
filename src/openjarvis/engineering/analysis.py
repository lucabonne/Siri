"""Passive engineering project summaries."""

from __future__ import annotations

from openjarvis.engineering.cad import format_counts
from openjarvis.engineering.models import (
    CadFile,
    EngineeringProject,
    EngineeringProjectSummary,
)
from openjarvis.engineering.viewers import viewer_hints


def summarize_project(
    project: EngineeringProject,
    *,
    privacy_mode: bool = False,
) -> EngineeringProjectSummary:
    """Build a lightweight summary without parsing or editing CAD geometry."""

    files = list(project.cad_files)
    recent = sorted(files, key=lambda item: item.modified_at, reverse=True)[:10]
    largest = sorted(files, key=lambda item: item.size_bytes, reverse=True)[:8]
    notes = _analysis_notes(project, files)
    return EngineeringProjectSummary(
        project=project,
        file_count=len(files),
        formats=format_counts(files),
        largest_files=largest,
        recent_files=recent,
        viewer_hints=viewer_hints(recent or files),
        analysis_notes=notes,
        privacy_mode=privacy_mode,
    )


def _analysis_notes(project: EngineeringProject, files: list[CadFile]) -> list[str]:
    if not files:
        return ["No STEP, STL, OBJ, Fusion, or FreeCAD files were detected."]
    counts = format_counts(files)
    notes = [f"Detected {len(files)} engineering file(s) across {len(counts)} formats."]
    if counts.get("STEP"):
        notes.append("STEP exchange files are available for passive design review.")
    if counts.get("STL") or counts.get("OBJ"):
        notes.append(
            "Mesh files are present; geometry analysis remains manual in Phase 1."
        )
    if counts.get("Fusion export"):
        notes.append("Fusion export files were detected locally.")
    if counts.get("FreeCAD project"):
        notes.append("FreeCAD project files were detected locally.")
    if project.project_kind == "mesh":
        notes.append("Workspace appears mesh-focused rather than parametric.")
    return notes


__all__ = ["summarize_project"]
