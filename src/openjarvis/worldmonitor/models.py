"""Typed models for the optional WorldMonitor integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class WorldMonitorSource:
    title: str = ""
    url: str = ""
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorldMonitorEvent:
    id: str
    title: str
    summary: str = ""
    category: str = "world"
    signal: str = ""
    severity: str = ""
    latitude: float | None = None
    longitude: float | None = None
    location_name: str = ""
    source_url: str = ""
    source_name: str = "WorldMonitor"
    published_at: str = ""
    imported_at: str = ""
    raw_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorldMonitorBriefingData:
    title: str
    summary: str
    signals: list[str]
    events: list[WorldMonitorEvent]
    source_urls: list[str]
    imported_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["events"] = [event.to_dict() for event in self.events]
        return data


@dataclass(slots=True)
class WorldMonitorStatus:
    installed: bool
    connected: bool
    base_url: str
    local_repo_path: str
    api_available: bool
    last_sync_at: str
    cached_event_count: int
    privacy_mode: bool
    passive_only: bool = True
    local_only: bool = True
    remote_telemetry: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorldMonitorSyncStatus:
    status: str
    imported_event_count: int
    source_count: int
    started_at: str
    completed_at: str
    base_url: str
    privacy_mode: bool
    error: str = ""
    passive_only: bool = True
    local_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "WorldMonitorBriefingData",
    "WorldMonitorEvent",
    "WorldMonitorSource",
    "WorldMonitorStatus",
    "WorldMonitorSyncStatus",
]
