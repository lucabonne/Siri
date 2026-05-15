"""Lightweight dependency graph extraction for local repositories."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from openjarvis.repo_index.models import DependencyGraph, RepoFile

try:  # pragma: no cover
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


BUILD_FILE_NAMES = {
    "Cargo.toml",
    "Makefile",
    "build.gradle",
    "build.gradle.kts",
    "gradle.properties",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "settings.gradle",
    "settings.gradle.kts",
    "vite.config.js",
    "vite.config.ts",
}


def build_dependency_graph(
    root: str | Path,
    files: Iterable[RepoFile],
    *,
    package_managers: list[str] | None = None,
) -> DependencyGraph:
    """Build dependency hints from manifests and import statements."""
    root_path = Path(root)
    file_list = list(files)
    rel_paths = {file.path for file in file_list}
    build_files = sorted(
        path for path in rel_paths if Path(path).name in BUILD_FILE_NAMES
    )
    dependencies: list[dict[str, str]] = []

    dependencies.extend(_pyproject_dependencies(root_path / "pyproject.toml"))
    dependencies.extend(_requirements_dependencies(root_path / "requirements.txt"))
    dependencies.extend(_package_json_dependencies(root_path / "package.json"))
    dependencies.extend(_package_json_dependencies(root_path / "frontend/package.json"))
    dependencies.extend(_cargo_dependencies(root_path / "Cargo.toml"))
    dependencies.extend(_cargo_dependencies(root_path / "rust/Cargo.toml"))
    for rel in ("build.gradle", "build.gradle.kts"):
        dependencies.extend(_gradle_dependencies(root_path / rel))

    return DependencyGraph(
        root=str(root_path),
        direct_dependencies=_dedupe_dependencies(dependencies),
        internal_edges=_internal_import_edges(root_path, file_list),
        build_files=build_files,
        package_managers=package_managers or [],
    )


def _pyproject_dependencies(path: Path) -> list[dict[str, str]]:
    data = _read_toml(path)
    project = data.get("project", {}) if isinstance(data, dict) else {}
    deps = _flatten_python_requirements(project.get("dependencies", []))
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for values in optional.values():
            deps.extend(_flatten_python_requirements(values))
    return [_dep(name, "python", str(path.name)) for name in deps]


def _requirements_dependencies(path: Path) -> list[dict[str, str]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    deps = []
    for line in lines:
        clean = line.split("#", 1)[0].strip()
        if not clean or clean.startswith("-"):
            continue
        deps.append(re.split(r"[<>=; \[]", clean, maxsplit=1)[0])
    return [_dep(name, "python", path.name) for name in deps if name]


def _package_json_dependencies(path: Path) -> list[dict[str, str]]:
    data = _read_json(path)
    deps = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        values = data.get(section, {})
        if isinstance(values, dict):
            deps.extend(_dep(name, "node", str(path), section) for name in values)
    return deps


def _cargo_dependencies(path: Path) -> list[dict[str, str]]:
    data = _read_toml(path)
    deps = []
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        values = data.get(section, {}) if isinstance(data, dict) else {}
        if isinstance(values, dict):
            deps.extend(_dep(name, "rust", str(path), section) for name in values)
    return deps


def _gradle_dependencies(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    deps = []
    for match in re.finditer(
        r"""(?:implementation|api|compileOnly|modImplementation)\s*\(?\s*["']([^"']+)["']""",
        text,
    ):
        coordinate = match.group(1)
        name = coordinate.split(":")[-2:] if ":" in coordinate else [coordinate]
        deps.append(_dep(":".join(name), "gradle", path.name))
    return deps


def _internal_import_edges(root: Path, files: list[RepoFile]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    safe_paths = {file.path for file in files}
    for file in files:
        if file.language not in {"Python", "Java", "Rust", "JavaScript", "TypeScript"}:
            continue
        text = _read_text(root / file.path, max_chars=40_000)
        for target in _imports_for_text(text, file.language):
            match = _match_internal_target(target, safe_paths)
            if match:
                edges.append({"from": file.path, "to": match, "kind": "import"})
    return _dedupe_edges(edges)[:250]


def _imports_for_text(text: str, language: str) -> list[str]:
    imports: list[str] = []
    if language == "Python":
        imports.extend(
            re.findall(r"^\s*from\s+([A-Za-z0-9_.]+)\s+import\s+", text, re.M)
        )
        imports.extend(re.findall(r"^\s*import\s+([A-Za-z0-9_.]+)", text, re.M))
    elif language == "Java":
        imports.extend(re.findall(r"^\s*import\s+([A-Za-z0-9_.]+);", text, re.M))
    elif language == "Rust":
        imports.extend(re.findall(r"^\s*use\s+([A-Za-z0-9_:]+)", text, re.M))
        imports.extend(re.findall(r"^\s*mod\s+([A-Za-z0-9_]+);", text, re.M))
    else:
        imports.extend(re.findall(r"""from\s+["']([^"']+)["']""", text))
        imports.extend(re.findall(r"""import\s+["']([^"']+)["']""", text))
    return imports[:80]


def _match_internal_target(target: str, paths: set[str]) -> str:
    normalized = target.replace(".", "/").replace("::", "/")
    if normalized.startswith("./") or normalized.startswith("../"):
        normalized = normalized.lstrip("./")
    candidates = [
        f"{normalized}.py",
        f"{normalized}.java",
        f"{normalized}.rs",
        f"{normalized}.ts",
        f"{normalized}.tsx",
        f"{normalized}.js",
        f"{normalized}/__init__.py",
        f"{normalized}/mod.rs",
        f"{normalized}/index.ts",
        f"{normalized}/index.js",
    ]
    for candidate in candidates:
        if candidate in paths:
            return candidate
    return ""


def _dep(
    name: str,
    ecosystem: str,
    source: str,
    section: str = "",
) -> dict[str, str]:
    return {
        "name": name,
        "ecosystem": ecosystem,
        "source": source,
        "section": section,
    }


def _flatten_python_requirements(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names = []
    for value in values:
        if isinstance(value, str):
            names.append(re.split(r"[<>=; \[]", value, maxsplit=1)[0])
    return [name for name in names if name]


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


def _dedupe_dependencies(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for item in items:
        key = (item["name"], item["ecosystem"], item["source"], item["section"])
        if item["name"] and key not in seen:
            result.append(item)
            seen.add(key)
    return sorted(result, key=lambda item: (item["ecosystem"], item["name"]))[:300]


def _dedupe_edges(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for item in items:
        key = (item["from"], item["to"], item["kind"])
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result


__all__ = ["BUILD_FILE_NAMES", "build_dependency_graph"]
