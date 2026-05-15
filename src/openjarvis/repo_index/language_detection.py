"""Repository language detection helpers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from openjarvis.repo_index.models import RepoFile

LANGUAGE_BY_EXTENSION = {
    ".bat": "Batch",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".gradle": "Gradle",
    ".groovy": "Groovy",
    ".h": "C/C++",
    ".hpp": "C++",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".json": "JSON",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".lua": "Lua",
    ".m": "Objective-C",
    ".md": "Markdown",
    ".mm": "Objective-C++",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sh": "Shell",
    ".swift": "Swift",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
}

SOURCE_LANGUAGES = {
    "C",
    "C#",
    "C++",
    "C/C++",
    "Go",
    "Gradle",
    "Groovy",
    "Java",
    "JavaScript",
    "Kotlin",
    "Python",
    "Rust",
    "Shell",
    "Swift",
    "TypeScript",
    "Vue",
}


def detect_language_for_path(path: str | Path) -> str:
    """Return a language name for a path using conservative extension rules."""
    p = Path(path)
    name = p.name.lower()
    if name in {"dockerfile", "containerfile"}:
        return "Dockerfile"
    if name == "makefile":
        return "Makefile"
    if name in {"build.gradle", "settings.gradle"}:
        return "Gradle"
    if name in {"build.gradle.kts", "settings.gradle.kts"}:
        return "Kotlin"
    return LANGUAGE_BY_EXTENSION.get(p.suffix.lower(), "")


def detect_languages(files: Iterable[RepoFile]) -> Counter[str]:
    """Count languages for safe indexed files."""
    counts: Counter[str] = Counter()
    for file in files:
        language = file.language or detect_language_for_path(file.path)
        if language:
            counts[language] += 1
    return counts


def is_source_language(language: str) -> bool:
    return language in SOURCE_LANGUAGES


__all__ = [
    "LANGUAGE_BY_EXTENSION",
    "SOURCE_LANGUAGES",
    "detect_language_for_path",
    "detect_languages",
    "is_source_language",
]
