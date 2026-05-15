"""Project stack, framework, package-manager, and build-system detection."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from openjarvis.repo_index.models import DetectedStack, RepoFile

try:  # pragma: no cover - fallback only on Python < 3.11.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def detect_stack(
    root: str | Path,
    files: Iterable[RepoFile],
    *,
    git_repository: str = "",
    current_branch: str = "",
    language_counts: Counter[str] | None = None,
) -> DetectedStack:
    """Detect a repository stack from manifest/config files only."""
    root_path = Path(root)
    file_map = {file.path: file for file in files}
    languages = sorted((language_counts or Counter()).keys())
    frameworks: set[str] = set()
    managers: set[str] = set()
    build_systems: set[str] = set()

    pyproject = _read_toml(root_path / "pyproject.toml")
    if pyproject:
        managers.add("pip/uv")
        build_systems.add("PEP 517")
        deps = _pyproject_deps(pyproject)
        frameworks.update(_frameworks_from_python(deps))
    if "requirements.txt" in file_map:
        managers.add("pip")
    if "uv.lock" in file_map:
        managers.add("uv")
    if "poetry.lock" in file_map:
        managers.add("Poetry")

    for rel in ("package.json", "frontend/package.json"):
        package = _read_json(root_path / rel)
        if not package:
            continue
        managers.add(_node_manager(root_path, rel))
        deps = {
            **package.get("dependencies", {}),
            **package.get("devDependencies", {}),
        }
        frameworks.update(_frameworks_from_node(deps.keys()))
        if "scripts" in package:
            build_systems.add("npm scripts")
    if any(
        rel in file_map for rel in ("package-lock.json", "frontend/package-lock.json")
    ):
        managers.add("npm")
    if any(rel in file_map for rel in ("pnpm-lock.yaml", "frontend/pnpm-lock.yaml")):
        managers.add("pnpm")
    if any(rel in file_map for rel in ("yarn.lock", "frontend/yarn.lock")):
        managers.add("Yarn")

    cargo_files = [rel for rel in ("Cargo.toml", "rust/Cargo.toml") if rel in file_map]
    if cargo_files:
        managers.add("Cargo")
        build_systems.add("Cargo")
        frameworks.add("Rust")

    gradle_files = [
        rel
        for rel in (
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
            "gradle.properties",
        )
        if rel in file_map
    ]
    if gradle_files or any(file.path.startswith("gradle/") for file in files):
        managers.add("Gradle")
        build_systems.add("Gradle")
        frameworks.add("Java")
        gradle_text = "\n".join(
            _read_text(root_path / rel, max_chars=80_000) for rel in gradle_files
        )
        lower = gradle_text.lower()
        if "fabric-loom" in lower or "loom" in lower:
            frameworks.add("Loom")
        if "net.fabricmc" in lower or "fabric-api" in lower or "fabricloader" in lower:
            frameworks.add("Fabric")
            frameworks.add("Minecraft Mod")
        if "minecraft" in lower or "yarn_mappings" in lower:
            frameworks.add("Minecraft Mod")

    if any(rel in file_map for rel in ("Makefile", "makefile")):
        build_systems.add("Make")
    if any(
        rel in file_map
        for rel in (
            "vite.config.ts",
            "vite.config.js",
            "frontend/vite.config.ts",
            "frontend/vite.config.js",
        )
    ):
        frameworks.add("Vite")
        build_systems.add("Vite")
    if any(
        rel in file_map
        for rel in (
            "tauri.conf.json",
            "src-tauri/tauri.conf.json",
            "frontend/src-tauri/tauri.conf.json",
        )
    ):
        frameworks.add("Tauri")

    if "Java" in languages:
        frameworks.add("Java")
    if "Rust" in languages:
        frameworks.add("Rust")
    if "Python" in languages:
        frameworks.add("Python")

    return DetectedStack(
        git_repository=git_repository,
        current_branch=current_branch,
        languages=languages,
        frameworks=sorted(frameworks),
        package_managers=sorted(managers),
        build_systems=sorted(build_systems),
        project_type=_project_type(frameworks, build_systems, languages, root_path),
    )


def _project_type(
    frameworks: set[str],
    build_systems: set[str],
    languages: list[str],
    root: Path,
) -> str:
    if "Minecraft Mod" in frameworks:
        return "minecraft mod"
    if "Tauri" in frameworks:
        return "desktop app"
    if {"FastAPI", "Django", "Flask"} & frameworks:
        return "api/backend service"
    if {"React", "Vue", "Vite", "Next.js"} & frameworks:
        return "web frontend"
    if "Gradle" in build_systems and "Java" in frameworks:
        return "java project"
    if "Cargo" in build_systems:
        return "rust project"
    if "Python" in languages:
        return "python project"
    if "JavaScript" in languages or "TypeScript" in languages:
        return "node project"
    return "unknown"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _read_text(path: Path, *, max_chars: int) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _pyproject_deps(data: dict[str, Any]) -> list[str]:
    deps = _flatten_dependency_names(data.get("project", {}).get("dependencies", []))
    optional = data.get("project", {}).get("optional-dependencies", {})
    if isinstance(optional, dict):
        for values in optional.values():
            deps.extend(_flatten_dependency_names(values))
    return deps


def _flatten_dependency_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names = []
    for value in values:
        if isinstance(value, str):
            names.append(re.split(r"[<>=; \[]", value, maxsplit=1)[0])
    return [name for name in names if name]


def _frameworks_from_python(dependencies: Iterable[str]) -> set[str]:
    names = {dep.lower() for dep in dependencies}
    frameworks: set[str] = set()
    mapping = {
        "django": "Django",
        "fastapi": "FastAPI",
        "flask": "Flask",
        "pytest": "pytest",
        "streamlit": "Streamlit",
    }
    for dep, label in mapping.items():
        if dep in names:
            frameworks.add(label)
    return frameworks


def _frameworks_from_node(dependencies: Iterable[str]) -> set[str]:
    names = {dep.lower() for dep in dependencies}
    frameworks: set[str] = set()
    mapping = {
        "@tauri-apps/api": "Tauri",
        "@vitejs/plugin-react": "React",
        "next": "Next.js",
        "react": "React",
        "vite": "Vite",
        "vue": "Vue",
    }
    for dep, label in mapping.items():
        if dep in names:
            frameworks.add(label)
    return frameworks


def _node_manager(root: Path, package_rel: str) -> str:
    base = root / Path(package_rel).parent
    if (base / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (base / "yarn.lock").exists():
        return "Yarn"
    return "npm"


__all__ = ["detect_stack"]
