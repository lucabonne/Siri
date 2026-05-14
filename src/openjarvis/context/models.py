"""Data models for passive local context snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DesktopContext:
    active_application: str = ""
    active_window_title: str = ""
    clipboard_preview: str = ""
    clipboard_sensitive: bool = False
    current_working_directory: str = ""
    recent_files: list[str] = field(default_factory=list)
    privacy_mode: bool = False
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectContext:
    cwd: str = ""
    git_repository: str = ""
    current_branch: str = ""
    languages: list[str] = field(default_factory=list)
    framework_build_system: list[str] = field(default_factory=list)
    package_manager: list[str] = field(default_factory=list)
    project_type: str = "unknown"
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RepoSummary:
    root: str = ""
    file_count: int = 0
    language_breakdown: dict[str, int] = field(default_factory=dict)
    top_level_modules: list[dict[str, Any]] = field(default_factory=list)
    dependency_hints: list[str] = field(default_factory=list)
    architecture_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RepoIndex:
    root: str = ""
    inventory: list[str] = field(default_factory=list)
    module_summaries: list[dict[str, Any]] = field(default_factory=list)
    dependency_hints: list[str] = field(default_factory=list)
    architecture_metadata: dict[str, Any] = field(default_factory=dict)
    summary: RepoSummary = field(default_factory=RepoSummary)
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["summary"] = self.summary.to_dict()
        return data
