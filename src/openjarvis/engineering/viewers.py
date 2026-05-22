"""Viewer metadata for engineering files.

Phase 1 exposes hints only. It does not launch viewers, upload models, or
modify CAD assets.
"""

from __future__ import annotations

from typing import Any

from openjarvis.engineering.models import CadFile

VIEWER_HINTS = {
    "STEP": {
        "viewer": "CAD exchange viewer",
        "capabilities": ["inspect metadata", "measure manually"],
    },
    "STL": {
        "viewer": "mesh viewer",
        "capabilities": ["inspect mesh", "prepare print review"],
    },
    "OBJ": {
        "viewer": "mesh viewer",
        "capabilities": ["inspect mesh", "review materials manually"],
    },
    "Fusion export": {
        "viewer": "Fusion-compatible local viewer",
        "capabilities": ["inspect export"],
    },
    "FreeCAD project": {
        "viewer": "FreeCAD local project",
        "capabilities": ["inspect model tree manually"],
    },
    "FreeCAD backup": {
        "viewer": "FreeCAD local backup",
        "capabilities": ["inspect backup manually"],
    },
}


def viewer_hint_for_file(file: CadFile) -> dict[str, Any]:
    hint = VIEWER_HINTS.get(
        file.format,
        {"viewer": "local file viewer", "capabilities": ["inspect file"]},
    )
    return {
        "path": file.path,
        "name": file.name,
        "format": file.format,
        "viewer": hint["viewer"],
        "capabilities": list(hint["capabilities"]),
        "local_only": True,
        "passive_only": True,
        "launch_supported": False,
        "upload_supported": False,
    }


def viewer_hints(files: list[CadFile], *, limit: int = 12) -> list[dict[str, Any]]:
    return [viewer_hint_for_file(item) for item in files[:limit]]


__all__ = ["VIEWER_HINTS", "viewer_hint_for_file", "viewer_hints"]
