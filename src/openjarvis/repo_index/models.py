"""Typed models for local repository semantic indexing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class DetectedStack:
    """Local-only technology stack detection result."""

    git_repository: str = ""
    current_branch: str = ""
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    build_systems: list[str] = field(default_factory=list)
    project_type: str = "unknown"
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RepoFile:
    """A source/config file considered safe for indexing."""

    path: str
    absolute_path: str
    language: str = ""
    size_bytes: int = 0
    ignored: bool = False
    sensitive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FileSummary:
    """Compact searchable summary for one repository file."""

    path: str
    language: str = ""
    summary: str = ""
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ArchitectureMap:
    """Lightweight architecture view assembled from local files."""

    root: str = ""
    packages: list[dict[str, Any]] = field(default_factory=list)
    modules: list[dict[str, Any]] = field(default_factory=list)
    build_files: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    major_directories: list[dict[str, Any]] = field(default_factory=list)
    configuration_files: list[str] = field(default_factory=list)
    dependency_hints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DependencyGraph:
    """Dependency overview without executing project code."""

    root: str = ""
    direct_dependencies: list[dict[str, str]] = field(default_factory=list)
    internal_edges: list[dict[str, str]] = field(default_factory=list)
    build_files: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SemanticSearchResult:
    """Semantic repo search result."""

    path: str
    summary: str
    score: float
    language: str = ""
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RepoSummary:
    """Repo-wide summary returned by service and API endpoints."""

    root: str = ""
    git_repository: str = ""
    current_branch: str = ""
    file_count: int = 0
    indexed_file_count: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    detected_stack: DetectedStack = field(default_factory=DetectedStack)
    architecture: ArchitectureMap = field(default_factory=ArchitectureMap)
    dependency_graph: DependencyGraph = field(default_factory=DependencyGraph)
    file_summaries: list[FileSummary] = field(default_factory=list)
    skipped_paths: list[str] = field(default_factory=list)
    privacy_mode: bool = False
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["detected_stack"] = self.detected_stack.to_dict()
        data["architecture"] = self.architecture.to_dict()
        data["dependency_graph"] = self.dependency_graph.to_dict()
        data["file_summaries"] = [item.to_dict() for item in self.file_summaries]
        return data


__all__ = [
    "ArchitectureMap",
    "DependencyGraph",
    "DetectedStack",
    "FileSummary",
    "RepoFile",
    "RepoSummary",
    "SemanticSearchResult",
]
