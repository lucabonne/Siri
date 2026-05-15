"""Typed models for Siri's lightweight morning briefing subsystem."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class NewsItem:
    """A source-backed news item before briefing classification."""

    title: str
    summary: str = ""
    source_url: str = ""
    source_name: str = ""
    published_at: str = ""
    location_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MorningEvent:
    """A categorized briefing event that can optionally appear on the world map."""

    id: str
    title: str
    category: str
    summary: str
    source_url: str = ""
    source_name: str = ""
    published_at: str = ""
    latitude: float | None = None
    longitude: float | None = None
    location_name: str = ""
    importance: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DailyBriefing:
    """A stored daily briefing with timestamp, source links, and events."""

    id: str
    briefing_date: str
    title: str
    summary: str
    content: str
    events: list[MorningEvent]
    source_links: list[str]
    location_name: str = ""
    generated_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["events"] = [event.to_dict() for event in self.events]
        return data


@dataclass(slots=True)
class BriefingStatus:
    """Current operational status for the briefing subsystem."""

    has_cached_briefing: bool
    latest_generated_at: str
    latest_briefing_date: str
    external_fetching_enabled: bool
    privacy_mode: bool
    scheduler: dict[str, Any]
    source_count: int
    event_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["BriefingStatus", "DailyBriefing", "MorningEvent", "NewsItem"]
