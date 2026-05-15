"""Safe local repository scanner for semantic indexing."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

from openjarvis.repo_index.language_detection import detect_language_for_path
from openjarvis.repo_index.models import RepoFile

IGNORED_DIRS = {
    ".cache",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    ".idea",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "vendor",
}

SENSITIVE_NAME_PATTERNS = (
    re.compile(r"(^|[._-])env($|[._-])", re.IGNORECASE),
    re.compile(r"(secret|credential|token|password|passwd|private[_-]?key)", re.I),
    re.compile(r"\.(pem|p12|pfx|key|crt|cer|sqlite|db)$", re.I),
)

TEXT_EXTENSIONS = {
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".css",
    ".gradle",
    ".groovy",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".kts",
    ".md",
    ".properties",
    ".py",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}

TEXT_FILE_NAMES = {
    "Cargo.toml",
    "Dockerfile",
    "Makefile",
    "README",
    "README.md",
    "build.gradle",
    "build.gradle.kts",
    "gradle.properties",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "settings.gradle",
    "settings.gradle.kts",
}


class RepoScanner:
    """Read-only scanner that respects ignore rules and sensitive paths."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        max_files: int = 1200,
        max_file_bytes: int = 250_000,
    ) -> None:
        self.cwd = Path(root or os.getcwd()).expanduser()
        self.root = self.git_root(self.cwd) or self.cwd
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes

    @staticmethod
    def run_git(args: list[str], cwd: Path, *, timeout: float = 1.5) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    @classmethod
    def git_root(cls, path: str | Path) -> Path | None:
        cwd = Path(path).expanduser()
        output = cls.run_git(["rev-parse", "--show-toplevel"], cwd)
        return Path(output) if output else None

    @classmethod
    def current_branch(cls, root: str | Path) -> str:
        cwd = Path(root).expanduser()
        return cls.run_git(["branch", "--show-current"], cwd)

    def scan(self) -> tuple[list[RepoFile], list[str]]:
        """Return indexable files and skipped paths."""
        candidates = self._git_candidates() or self._walk_candidates()
        files: list[RepoFile] = []
        skipped: list[str] = []
        for rel in candidates:
            rel = rel.strip().replace("\\", "/")
            if not rel or rel.startswith("../"):
                continue
            abs_path = self.root / rel
            if self._ignored_path(rel) or not abs_path.is_file():
                skipped.append(rel)
                continue
            sensitive = self.is_sensitive_path(rel)
            if sensitive or not self._text_candidate(abs_path):
                skipped.append(rel)
                continue
            try:
                size = abs_path.stat().st_size
            except OSError:
                skipped.append(rel)
                continue
            if size > self.max_file_bytes:
                skipped.append(rel)
                continue
            files.append(
                RepoFile(
                    path=rel,
                    absolute_path=str(abs_path),
                    language=detect_language_for_path(rel),
                    size_bytes=size,
                    sensitive=False,
                )
            )
            if len(files) >= self.max_files:
                break
        return files, skipped[:200]

    def read_text(self, file: RepoFile, *, max_chars: int = 20_000) -> str:
        """Read a safe file sample for summarization."""
        path = Path(file.absolute_path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[:max_chars]

    def _git_candidates(self) -> list[str]:
        if not (self.root / ".git").exists():
            return []
        output = self.run_git(
            ["ls-files", "-co", "--exclude-standard"],
            self.root,
            timeout=3.0,
        )
        return output.splitlines() if output else []

    def _walk_candidates(self) -> list[str]:
        paths: list[str] = []
        for current, dirs, filenames in os.walk(self.root):
            dirs[:] = [
                name
                for name in dirs
                if name not in IGNORED_DIRS and not name.startswith(".")
            ]
            current_path = Path(current)
            for filename in sorted(filenames):
                try:
                    rel = str((current_path / filename).relative_to(self.root))
                except ValueError:
                    continue
                paths.append(rel)
                if len(paths) >= self.max_files * 3:
                    return paths
        return paths

    @staticmethod
    def is_sensitive_path(path: str | Path) -> bool:
        rel = str(path).replace("\\", "/")
        name = Path(rel).name
        return any(
            pattern.search(name) or pattern.search(rel)
            for pattern in SENSITIVE_NAME_PATTERNS
        )

    @staticmethod
    def _ignored_path(path: str) -> bool:
        parts = Path(path).parts
        return any(part in IGNORED_DIRS or part.startswith(".") for part in parts[:-1])

    @staticmethod
    def _text_candidate(path: Path) -> bool:
        if path.name in TEXT_FILE_NAMES:
            return True
        return path.suffix.lower() in TEXT_EXTENSIONS


def safe_relative_paths(files: Iterable[RepoFile]) -> list[str]:
    return [file.path for file in files if not file.sensitive and not file.ignored]


__all__ = [
    "IGNORED_DIRS",
    "SENSITIVE_NAME_PATTERNS",
    "RepoScanner",
    "safe_relative_paths",
]
