"""Lightweight architecture summary extraction."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from openjarvis.repo_index.dependency_graph import BUILD_FILE_NAMES
from openjarvis.repo_index.language_detection import detect_languages
from openjarvis.repo_index.models import ArchitectureMap, DependencyGraph, RepoFile

CONFIG_FILE_NAMES = {
    ".editorconfig",
    "Cargo.toml",
    "Dockerfile",
    "components.json",
    "gradle.properties",
    "mkdocs.yml",
    "package.json",
    "pyproject.toml",
    "ruff.toml",
    "settings.gradle",
    "settings.gradle.kts",
    "tsconfig.json",
    "vite.config.js",
    "vite.config.ts",
}


def build_architecture_map(
    root: str | Path,
    files: list[RepoFile],
    *,
    stack: dict[str, Any],
    dependency_graph: DependencyGraph,
) -> ArchitectureMap:
    root_path = Path(root)
    return ArchitectureMap(
        root=str(root_path),
        packages=_packages(root_path, files),
        modules=_modules(root_path, files),
        build_files=sorted(
            file.path for file in files if Path(file.path).name in BUILD_FILE_NAMES
        ),
        entry_points=_entry_points(root_path, files),
        major_directories=_major_directories(files),
        configuration_files=sorted(
            file.path for file in files if Path(file.path).name in CONFIG_FILE_NAMES
        ),
        dependency_hints=[
            item["name"] for item in dependency_graph.direct_dependencies[:80]
        ],
        metadata={
            "has_frontend": _has_prefix(files, "frontend/")
            or "React" in stack.get("frameworks", []),
            "has_backend": _has_prefix(files, "src/")
            or bool({"FastAPI", "Django", "Flask"} & set(stack.get("frameworks", []))),
            "has_tests": _has_prefix(files, "tests/")
            or any("/test/" in file.path for file in files),
            "has_gradle": "Gradle" in stack.get("build_systems", []),
            "has_fabric_mod": "Fabric" in stack.get("frameworks", []),
            "has_minecraft_mod": "Minecraft Mod" in stack.get("frameworks", []),
            "has_rust_workspace": "Cargo" in stack.get("build_systems", []),
            "languages": stack.get("languages", []),
            "frameworks": stack.get("frameworks", []),
            "package_managers": stack.get("package_managers", []),
            "build_systems": stack.get("build_systems", []),
        },
    )


def _packages(root: Path, files: list[RepoFile]) -> list[dict[str, Any]]:
    packages: Counter[str] = Counter()
    for file in files:
        text = _read_text(root / file.path, max_chars=16_000)
        if file.language == "Python":
            parts = Path(file.path).parts
            if "__init__.py" in parts:
                package = ".".join(parts[:-1])
                if package:
                    packages[package] += 1
        elif file.language == "Java":
            match = re.search(r"^\s*package\s+([A-Za-z0-9_.]+);", text, re.M)
            if match:
                packages[match.group(1)] += 1
    return [
        {"name": name, "file_count": count}
        for name, count in packages.most_common(40)
    ]


def _modules(root: Path, files: list[RepoFile]) -> list[dict[str, Any]]:
    grouped: dict[str, list[RepoFile]] = defaultdict(list)
    for file in files:
        parts = Path(file.path).parts
        module = parts[0] if len(parts) > 1 else "."
        grouped[module].append(file)
    modules = []
    for name, module_files in grouped.items():
        languages = dict(detect_languages(module_files))
        notable = [
            file.path
            for file in module_files
            if Path(file.path).name
            in {
                "__init__.py",
                "Cargo.toml",
                "package.json",
                "pyproject.toml",
                "README.md",
            }
        ][:6]
        modules.append(
            {
                "name": name,
                "file_count": len(module_files),
                "languages": languages,
                "notable_files": notable,
            }
        )
    return sorted(modules, key=lambda item: item["file_count"], reverse=True)[:50]


def _entry_points(root: Path, files: list[RepoFile]) -> list[str]:
    entries: list[str] = []
    for file in files:
        name = Path(file.path).name
        if file.path in {"src/main.rs", "rust/src/main.rs"}:
            entries.append(file.path)
        elif name in {"__main__.py", "main.py", "app.py", "manage.py"}:
            entries.append(file.path)
        elif name in {"App.tsx", "App.jsx", "main.tsx", "main.jsx"}:
            entries.append(file.path)
        elif file.language == "Java":
            text = _read_text(root / file.path, max_chars=40_000)
            if "public static void main" in text or "implements ModInitializer" in text:
                entries.append(file.path)
    return sorted(dict.fromkeys(entries))[:60]


def _major_directories(files: list[RepoFile]) -> list[dict[str, Any]]:
    counts: dict[str, list[RepoFile]] = defaultdict(list)
    for file in files:
        parts = Path(file.path).parts
        if len(parts) > 1:
            counts[parts[0]].append(file)
    result = []
    for name, dir_files in counts.items():
        result.append(
            {
                "path": name,
                "file_count": len(dir_files),
                "languages": dict(detect_languages(dir_files)),
            }
        )
    return sorted(result, key=lambda item: item["file_count"], reverse=True)[:30]


def _has_prefix(files: list[RepoFile], prefix: str) -> bool:
    return any(file.path.startswith(prefix) for file in files)


def _read_text(path: Path, *, max_chars: int) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


__all__ = ["CONFIG_FILE_NAMES", "build_architecture_map"]
