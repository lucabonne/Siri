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


@dataclass
class ScreenshotMetadata:
    id: str
    captured_at: str
    file_path: str = ""
    format: str = "png"
    width: int | None = None
    height: int | None = None
    byte_size: int | None = None
    sha256: str = ""
    active_application: str = ""
    active_window_title: str = ""
    privacy_mode: bool = False
    redacted: bool = False
    passive_only: bool = True
    local_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def redacted_copy(self) -> "ScreenshotMetadata":
        data = self.to_dict()
        data.update(
            {
                "file_path": "",
                "sha256": "",
                "active_window_title": "[redacted window]",
                "redacted": True,
                "privacy_mode": True,
            }
        )
        return ScreenshotMetadata(**data)


@dataclass
class VisualContext:
    latest_screenshot: ScreenshotMetadata | None = None
    screenshot_count: int = 0
    privacy_mode: bool = False
    passive_only: bool = True
    local_only: bool = True
    cloud_uploaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "latest_screenshot": (
                self.latest_screenshot.to_dict() if self.latest_screenshot else None
            ),
            "screenshot_count": self.screenshot_count,
            "privacy_mode": self.privacy_mode,
            "passive_only": self.passive_only,
            "local_only": self.local_only,
            "cloud_uploaded": self.cloud_uploaded,
        }
