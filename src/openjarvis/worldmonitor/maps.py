"""WorldMonitor map helpers."""

from __future__ import annotations

from openjarvis.worldmonitor.models import WorldMonitorEvent


def map_events(events: list[WorldMonitorEvent]) -> list[WorldMonitorEvent]:
    return [event for event in events if event.has_coordinates]


__all__ = ["map_events"]
