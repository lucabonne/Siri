"""Passive desktop and project context collection.

The context layer only observes local state. It does not control applications,
execute project code, contact network services, or mutate the filesystem.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from openjarvis.context.models import (
    DesktopContext,
    ProjectContext,
    RepoIndex,
    RepoSummary,
)

try:  # pragma: no cover - exercised through either stdlib or fallback import.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


_IGNORED_DIRS = {
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

_LANGUAGE_BY_EXTENSION = {
    ".bat": "Batch",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".h": "C/C++",
    ".hpp": "C++",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".lua": "Lua",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sh": "Shell",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
}

_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|bearer)\b"),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
]


class ContextLayer:
    """Read-only collector for desktop, project, and repository context."""

    def __init__(
        self,
        *,
        cwd: str | os.PathLike[str] | None = None,
        max_files: int = 800,
    ) -> None:
        self.cwd = Path(cwd or os.getcwd()).expanduser()
        self.max_files = max_files

    def current_desktop_context(self, *, privacy_mode: bool = False) -> DesktopContext:
        app_name, window_title = self._active_macos_window()
        clipboard_preview, clipboard_sensitive = self._clipboard_preview(
            privacy_mode=privacy_mode
        )
        recent_root = self._git_root(self.cwd) or self.cwd
        return DesktopContext(
            active_application=app_name,
            active_window_title=window_title,
            clipboard_preview=clipboard_preview,
            clipboard_sensitive=clipboard_sensitive,
            current_working_directory=str(self.cwd),
            recent_files=self._recent_files(recent_root),
            privacy_mode=privacy_mode,
        )

    def current_project_context(self) -> ProjectContext:
        from openjarvis.repo_index import RepoIndexService

        summary = RepoIndexService(max_files=self.max_files).repo_summary(self.cwd)
        stack = summary.detected_stack
        return ProjectContext(
            cwd=str(self.cwd),
            git_repository=summary.git_repository,
            current_branch=summary.current_branch,
            languages=stack.languages,
            framework_build_system=sorted(
                set(stack.frameworks) | set(stack.build_systems)
            ),
            package_manager=stack.package_managers,
            project_type=stack.project_type,
        )

    def repo_index(self) -> RepoIndex:
        from openjarvis.repo_index import RepoIndexService

        summary_data = RepoIndexService(max_files=self.max_files).repo_summary(self.cwd)
        architecture = summary_data.architecture
        dependency_hints = architecture.dependency_hints
        architecture_metadata = {
            **architecture.metadata,
            "detected_stack": summary_data.detected_stack.to_dict(),
            "build_files": architecture.build_files,
            "entry_points": architecture.entry_points,
            "configuration_files": architecture.configuration_files,
            "indexed_file_count": summary_data.indexed_file_count,
            "local_only": True,
        }
        summary = RepoSummary(
            root=summary_data.root,
            file_count=summary_data.file_count,
            language_breakdown=summary_data.languages,
            top_level_modules=architecture.modules[:12],
            dependency_hints=dependency_hints[:24],
            architecture_metadata=architecture_metadata,
        )
        return RepoIndex(
            root=summary_data.root,
            inventory=[item.path for item in summary_data.file_summaries],
            module_summaries=architecture.modules,
            dependency_hints=dependency_hints,
            architecture_metadata=architecture_metadata,
            summary=summary,
        )

    @staticmethod
    def sanitize_clipboard(
        text: str,
        *,
        privacy_mode: bool = False,
    ) -> tuple[str, bool]:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return "", False
        sensitive = privacy_mode or any(
            pattern.search(cleaned) for pattern in _SECRET_PATTERNS
        )
        if sensitive:
            return "[redacted clipboard]", True
        if len(cleaned) > 160:
            return f"{cleaned[:157]}...", False
        return cleaned, False

    def _run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        timeout: float = 1.0,
    ) -> str:
        try:
            result = subprocess.run(
                args,
                cwd=str(cwd or self.cwd),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _active_macos_window(self) -> tuple[str, str]:
        if platform.system() != "Darwin":
            return "", ""
        script = (
            'tell application "System Events"\n'
            "set frontApp to first application process whose frontmost is true\n"
            "set appName to name of frontApp\n"
            "set windowTitle to \"\"\n"
            "try\n"
            "set windowTitle to name of front window of frontApp\n"
            "end try\n"
            "return appName & linefeed & windowTitle\n"
            "end tell"
        )
        output = self._run(["osascript", "-e", script], timeout=1.2)
        if not output:
            return "", ""
        parts = output.splitlines()
        return parts[0] if parts else "", parts[1] if len(parts) > 1 else ""

    def _clipboard_preview(self, *, privacy_mode: bool) -> tuple[str, bool]:
        if platform.system() != "Darwin":
            return "", False
        text = self._run(["pbpaste"], timeout=0.6)
        return self.sanitize_clipboard(text, privacy_mode=privacy_mode)

    def _git_root(self, path: Path) -> Path | None:
        output = self._run(["git", "rev-parse", "--show-toplevel"], cwd=path)
        return Path(output) if output else None

    def _git_branch(self, path: Path) -> str:
        return self._run(["git", "branch", "--show-current"], cwd=path)

    def _recent_files(self, root: Path, *, limit: int = 8) -> list[str]:
        files = self._file_inventory(root, limit=250)
        files.sort(key=_safe_mtime, reverse=True)
        return [str(path) for path in files[:limit]]

    def _file_inventory(self, root: Path, *, limit: int) -> list[Path]:
        root = root.resolve()
        files: list[Path] = []
        for current, dirs, filenames in os.walk(root):
            dirs[:] = [
                name
                for name in dirs
                if name not in _IGNORED_DIRS and not name.startswith(".")
            ]
            current_path = Path(current)
            for filename in sorted(filenames):
                if filename.startswith("."):
                    continue
                path = current_path / filename
                if path.is_file():
                    files.append(path)
                    if len(files) >= limit:
                        return files
        return files

    def _language_counts(self, inventory: Iterable[Path]) -> Counter[str]:
        counts: Counter[str] = Counter()
        for path in inventory:
            language = _LANGUAGE_BY_EXTENSION.get(path.suffix.lower())
            if language:
                counts[language] += 1
        return counts

    def _detect_stack(self, root: Path) -> dict[str, list[str]]:
        frameworks: set[str] = set()
        managers: set[str] = set()

        if (root / "pyproject.toml").exists():
            managers.add("pip/uv")
            frameworks.add("PEP 517")
            data = self._read_toml(root / "pyproject.toml")
            deps = _flatten_dependency_names(
                data.get("project", {}).get("dependencies", [])
            )
            optional = data.get("project", {}).get("optional-dependencies", {})
            for values in optional.values() if isinstance(optional, dict) else []:
                deps.extend(_flatten_dependency_names(values))
            frameworks.update(_frameworks_from_dependencies(deps))
        if (root / "requirements.txt").exists():
            managers.add("pip")
        if (root / "uv.lock").exists():
            managers.add("uv")
        if (root / "poetry.lock").exists():
            managers.add("Poetry")

        package_json_paths = [root / "package.json", root / "frontend" / "package.json"]
        for package_json in package_json_paths:
            if not package_json.exists():
                continue
            managers.add("npm")
            data = self._read_json(package_json)
            deps = {
                **data.get("dependencies", {}),
                **data.get("devDependencies", {}),
            }
            frameworks.update(_frameworks_from_dependencies(deps.keys()))
        if (
            (root / "pnpm-lock.yaml").exists()
            or (root / "frontend" / "pnpm-lock.yaml").exists()
        ):
            managers.add("pnpm")
        if (
            (root / "yarn.lock").exists()
            or (root / "frontend" / "yarn.lock").exists()
        ):
            managers.add("Yarn")
        if (
            (root / "package-lock.json").exists()
            or (root / "frontend" / "package-lock.json").exists()
        ):
            managers.add("npm")

        if (root / "Cargo.toml").exists() or (root / "rust" / "Cargo.toml").exists():
            managers.add("Cargo")
            frameworks.add("Cargo")
        if (root / "Makefile").exists():
            frameworks.add("Make")
        if (
            (root / "vite.config.ts").exists()
            or (root / "vite.config.js").exists()
            or (root / "frontend" / "vite.config.ts").exists()
            or (root / "frontend" / "vite.config.js").exists()
        ):
            frameworks.add("Vite")
        if (
            (root / "tauri.conf.json").exists()
            or (root / "src-tauri").exists()
            or (root / "frontend" / "src-tauri").exists()
        ):
            frameworks.add("Tauri")

        return {
            "framework_build_system": sorted(frameworks),
            "package_manager": sorted(managers),
        }

    def _project_type(
        self,
        root: Path,
        stack: dict[str, list[str]],
        language_counts: Counter[str],
    ) -> str:
        frameworks = set(stack["framework_build_system"])
        if "Tauri" in frameworks:
            return "desktop app"
        if {"FastAPI", "Django", "Flask"} & frameworks:
            return "api/backend service"
        if {"React", "Vue", "Vite"} & frameworks:
            return "web frontend"
        if (root / "pyproject.toml").exists() and (
            (root / "Cargo.toml").exists()
            or (root / "rust" / "Cargo.toml").exists()
        ):
            return "polyglot application"
        if "Rust" in language_counts:
            return "rust project"
        if "Python" in language_counts:
            return "python project"
        return "unknown"

    def _module_summaries(
        self,
        root: Path,
        inventory: list[Path],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[Path]] = defaultdict(list)
        for path in inventory:
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            module = rel.parts[0] if len(rel.parts) > 1 else "."
            grouped[module].append(path)

        summaries = []
        for module, files in sorted(grouped.items()):
            language_counts = self._language_counts(files)
            notable = [
                str(path.relative_to(root))
                for path in files
                if path.name
                in {
                    "__init__.py",
                    "Cargo.toml",
                    "package.json",
                    "pyproject.toml",
                    "README.md",
                    "vite.config.ts",
                }
            ][:5]
            summaries.append(
                {
                    "name": module,
                    "file_count": len(files),
                    "languages": dict(language_counts),
                    "notable_files": notable,
                }
            )
        return sorted(summaries, key=lambda item: item["file_count"], reverse=True)

    def _dependency_hints(self, root: Path) -> list[str]:
        hints: list[str] = []
        pyproject = self._read_toml(root / "pyproject.toml")
        project = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
        hints.extend(_flatten_dependency_names(project.get("dependencies", [])))
        for package_json_path in (
            root / "package.json",
            root / "frontend" / "package.json",
        ):
            package_json = self._read_json(package_json_path)
            for section in ("dependencies", "devDependencies"):
                values = package_json.get(section, {})
                if isinstance(values, dict):
                    hints.extend(sorted(values.keys()))
        for cargo_path in (root / "Cargo.toml", root / "rust" / "Cargo.toml"):
            cargo = self._read_toml(cargo_path)
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                values = cargo.get(section, {})
                if isinstance(values, dict):
                    hints.extend(sorted(values.keys()))
        return sorted(dict.fromkeys(hints))

    def _architecture_metadata(
        self,
        root: Path,
        inventory: list[Path],
        stack: dict[str, list[str]],
        language_counts: Counter[str],
    ) -> dict[str, Any]:
        rel_files = {str(path.relative_to(root)) for path in inventory}
        return {
            "has_frontend": any(path.startswith("frontend/") for path in rel_files)
            or "React" in stack["framework_build_system"],
            "has_backend": any(path.startswith("src/") for path in rel_files)
            or "FastAPI" in stack["framework_build_system"],
            "has_rust_workspace": (root / "Cargo.toml").exists() or any(
                path.startswith("rust/") for path in rel_files
            ),
            "has_tests": any(path.startswith("tests/") for path in rel_files),
            "languages": list(language_counts.keys()),
            "framework_build_system": stack["framework_build_system"],
            "package_manager": stack["package_manager"],
        }

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _read_toml(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("rb") as handle:
                return tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            return {}


def _flatten_dependency_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names = []
    for value in values:
        if isinstance(value, str):
            names.append(re.split(r"[<>=; \[]", value, maxsplit=1)[0])
    return [name for name in names if name]


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _frameworks_from_dependencies(dependencies: Iterable[str]) -> set[str]:
    names = {dep.lower() for dep in dependencies}
    frameworks: set[str] = set()
    if "fastapi" in names:
        frameworks.add("FastAPI")
    if "django" in names:
        frameworks.add("Django")
    if "flask" in names:
        frameworks.add("Flask")
    if "react" in names or "@vitejs/plugin-react" in names:
        frameworks.add("React")
    if "vite" in names:
        frameworks.add("Vite")
    if "next" in names:
        frameworks.add("Next.js")
    if "vue" in names:
        frameworks.add("Vue")
    if "tauri" in names or "@tauri-apps/api" in names:
        frameworks.add("Tauri")
    if "pytest" in names:
        frameworks.add("pytest")
    return frameworks
