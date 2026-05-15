"""World-map helpers for geolocated briefing events."""

from __future__ import annotations

from openjarvis.morning_briefing.models import MorningEvent


def world_map_events(events: list[MorningEvent]) -> list[MorningEvent]:
    """Return only events that have enough location data for map rendering."""

    return [event for event in events if event.has_coordinates and event.source_url]


__all__ = ["world_map_events"]
