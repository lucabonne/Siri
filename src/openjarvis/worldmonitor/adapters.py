"""Adapters from WorldMonitor payloads into Siri-native event models."""

from __future__ import annotations

from typing import Any

from openjarvis.morning_briefing.models import MorningEvent, NewsItem
from openjarvis.worldmonitor.events import (
    find_coordinates,
    first_text,
    infer_category,
    iter_event_dicts,
    stable_id,
)
from openjarvis.worldmonitor.models import WorldMonitorBriefingData, WorldMonitorEvent


def normalize_event(data: dict[str, Any], *, domain: str = "") -> WorldMonitorEvent:
    lat, lon = find_coordinates(data)
    title = (
        first_text(data, ("title", "headline", "name", "summary"))
        or "WorldMonitor event"
    )
    summary = first_text(
        data,
        ("summary", "description", "brief", "signal", "details", "content"),
    )
    source_url = first_text(data, ("sourceUrl", "source_url", "url", "link"))
    source_name = first_text(data, ("source", "provider", "feed", "sourceName"))
    location_name = first_text(
        data,
        ("locationName", "location_name", "place", "country"),
    )
    return WorldMonitorEvent(
        id=first_text(data, ("id", "eventId", "uid")) or stable_id(data),
        title=title,
        summary=summary or title,
        category=infer_category(data, domain=domain),
        signal=first_text(data, ("signal", "trend", "level", "status")),
        severity=first_text(data, ("severity", "risk", "riskLevel", "level")),
        latitude=lat,
        longitude=lon,
        location_name=location_name,
        source_url=source_url,
        source_name=source_name or "WorldMonitor",
        published_at=first_text(
            data,
            ("publishedAt", "published_at", "timestamp", "date", "createdAt"),
        ),
        raw_type=domain,
        metadata={"worldmonitor_domain": domain, "raw": data},
    )


def events_from_payload(payload: Any, *, imported_at: str) -> list[WorldMonitorEvent]:
    events: list[WorldMonitorEvent] = []
    seen: set[str] = set()
    for data, domain in iter_event_dicts(payload):
        event = normalize_event(data, domain=domain)
        event.imported_at = imported_at
        if event.id in seen:
            continue
        seen.add(event.id)
        events.append(event)
    return events


def to_news_items(events: list[WorldMonitorEvent]) -> list[NewsItem]:
    return [
        NewsItem(
            title=event.title,
            summary=event.summary,
            source_url=event.source_url,
            source_name=event.source_name or "WorldMonitor",
            published_at=event.published_at,
            location_name=event.location_name,
            metadata={
                "source": "worldmonitor",
                "category": event.category,
                "signal": event.signal,
                "severity": event.severity,
                "worldmonitor_event_id": event.id,
            },
        )
        for event in events
    ]


def to_morning_events(events: list[WorldMonitorEvent]) -> list[MorningEvent]:
    return [
        MorningEvent(
            id=event.id,
            title=event.title,
            category=event.category,
            summary=event.summary,
            source_url=event.source_url,
            source_name=event.source_name or "WorldMonitor",
            published_at=event.published_at,
            latitude=event.latitude,
            longitude=event.longitude,
            location_name=event.location_name,
            importance=4 if event.severity else 3,
            metadata={
                "source": "worldmonitor",
                "signal": event.signal,
                "severity": event.severity,
                "worldmonitor_event_id": event.id,
            },
            created_at=event.imported_at,
        )
        for event in events
    ]


def briefing_from_events(
    events: list[WorldMonitorEvent],
    *,
    imported_at: str,
) -> WorldMonitorBriefingData:
    signals = [
        event.signal
        for event in events
        if event.signal and event.signal not in {"normal", "unknown"}
    ][:8]
    source_urls = sorted({event.source_url for event in events if event.source_url})
    title = "WorldMonitor briefing data"
    summary = (
        f"{len(events)} imported WorldMonitor signals across "
        f"{len({event.category for event in events})} categories."
        if events
        else "No imported WorldMonitor events are cached yet."
    )
    return WorldMonitorBriefingData(
        title=title,
        summary=summary,
        signals=signals,
        events=events,
        source_urls=source_urls,
        imported_at=imported_at,
    )


__all__ = [
    "briefing_from_events",
    "events_from_payload",
    "normalize_event",
    "to_morning_events",
    "to_news_items",
]
