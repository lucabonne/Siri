"""Passive CAD and engineering file detection."""

from __future__ import annotations

import os
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

from openjarvis.engineering.models import CadDetection, CadFile

CAD_FORMATS_BY_SUFFIX = {
    ".step": "STEP",
    ".stp": "STEP",
    ".stl": "STL",
    ".obj": "OBJ",
    ".f3d": "Fusion export",
    ".f3z": "Fusion export",
    ".fcstd": "FreeCAD project",
    ".fcstd1": "FreeCAD backup",
}

ENGINEERING_MARKERS = {
    "drawings",
    "exports",
    "fabrication",
    "freecad",
    "fusion",
    "cad",
    "cam",
}

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}


def supported_formats() -> list[str]:
    """Return user-facing supported engineering file families."""

    return sorted(set(CAD_FORMATS_BY_SUFFIX.values()))


def detect_cad_file(path: str | os.PathLike[str]) -> CadFile | None:
    """Return a CAD file model when *path* has a supported extension."""

    target = Path(path).expanduser()
    fmt = CAD_FORMATS_BY_SUFFIX.get(target.suffix.lower())
    if not fmt or not target.is_file():
        return None
    try:
        stat = target.stat()
        size = stat.st_size
        modified_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime))
    except OSError:
        size = 0
        modified_at = ""
    return CadFile(
        path=str(target),
        name=target.name,
        format=fmt,
        role=_file_role(target, fmt),
        size_bytes=size,
        modified_at=modified_at,
    )


def scan_cad_files(
    root: str | os.PathLike[str],
    *,
    limit: int = 300,
    max_depth: int = 6,
) -> list[CadFile]:
    """Walk a local tree and return supported CAD files.

    This scan is read-only and only collects path/stat metadata.
    """

    base = Path(root).expanduser()
    if base.is_file():
        item = detect_cad_file(base)
        return [item] if item else []
    if not base.exists() or not base.is_dir():
        return []

    files: list[CadFile] = []
    base_depth = len(base.resolve().parts)
    for current, dirs, filenames in os.walk(base):
        current_path = Path(current)
        depth = len(current_path.resolve().parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [
                name
                for name in dirs
                if name not in IGNORED_DIRS and not name.startswith(".")
            ]
        for filename in sorted(filenames):
            item = detect_cad_file(current_path / filename)
            if item is None:
                continue
            files.append(item)
            if len(files) >= limit:
                return files
    return files


def detect_engineering_project(
    root: str | os.PathLike[str],
    *,
    limit: int = 300,
) -> CadDetection:
    """Detect whether a path looks like an engineering/CAD project."""

    base = Path(root).expanduser()
    cad_files = scan_cad_files(base, limit=limit)
    formats = sorted({item.format for item in cad_files})
    markers = _markers(base)
    is_project = bool(cad_files or markers)
    return CadDetection(
        is_engineering_project=is_project,
        project_kind=_project_kind(cad_files, markers),
        formats=formats,
        cad_files=cad_files,
        markers=markers,
    )


def format_counts(files: Iterable[CadFile]) -> dict[str, int]:
    """Count CAD files by user-facing format."""

    return dict(Counter(item.format for item in files))


def _file_role(path: Path, fmt: str) -> str:
    lower = path.name.lower()
    if fmt == "STL":
        return "mesh"
    if fmt == "OBJ":
        return "mesh"
    if fmt == "STEP":
        return "exchange"
    if "drawing" in lower or "print" in lower:
        return "drawing"
    if fmt.startswith("FreeCAD"):
        return "parametric_project"
    if fmt.startswith("Fusion"):
        return "fusion_export"
    return "model"


def _markers(base: Path) -> list[str]:
    if base.is_file():
        base = base.parent
    found: set[str] = set()
    try:
        names = [item.name for item in base.iterdir()]
    except OSError:
        return []
    for name in names:
        lower = name.lower()
        if lower in ENGINEERING_MARKERS:
            found.add(lower)
        if lower.endswith(".fcstd"):
            found.add("freecad")
        if lower.endswith((".f3d", ".f3z")):
            found.add("fusion")
    return sorted(found)


def _project_kind(files: list[CadFile], markers: list[str]) -> str:
    formats = {item.format for item in files}
    if "FreeCAD project" in formats or "freecad" in markers:
        return "freecad"
    if "Fusion export" in formats or "fusion" in markers:
        return "fusion_export"
    if formats <= {"STL", "OBJ"} and formats:
        return "mesh"
    if "STEP" in formats:
        return "cad_exchange"
    if files:
        return "cad_project"
    if markers:
        return "engineering_workspace"
    return "unknown"


__all__ = [
    "CAD_FORMATS_BY_SUFFIX",
    "detect_cad_file",
    "detect_engineering_project",
    "format_counts",
    "scan_cad_files",
    "supported_formats",
]
