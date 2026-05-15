"""Optional local WorldMonitor intelligence service."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from openjarvis.worldmonitor.adapters import (
    briefing_from_events,
    events_from_payload,
    to_morning_events,
    to_news_items,
)
from openjarvis.worldmonitor.cache import WorldMonitorCache
from openjarvis.worldmonitor.client import WorldMonitorClient, detect_local_repo
from openjarvis.worldmonitor.maps import map_events
from openjarvis.worldmonitor.models import (
    WorldMonitorBriefingData,
    WorldMonitorEvent,
    WorldMonitorStatus,
    WorldMonitorSyncStatus,
)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class WorldMonitorService:
    """Passive bridge from local WorldMonitor data into Siri."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        client: WorldMonitorClient | None = None,
        cache: WorldMonitorCache | None = None,
        memory_service: Any = None,
        cwd: str | Path | None = None,
    ) -> None:
        self.cache = cache or WorldMonitorCache(db_path)
        self.client = client or WorldMonitorClient()
        self.memory_service = memory_service
        self.cwd = Path(cwd).expanduser() if cwd else None

    def close(self) -> None:
        self.cache.close()

    def status(self, *, privacy_mode: bool = False) -> WorldMonitorStatus:
        repo = detect_local_repo(self.cwd)
        base_url = self.client.discover_base_url()
        latest = self.cache.latest_sync()
        return WorldMonitorStatus(
            installed=repo is not None or bool(base_url),
            connected=bool(base_url),
            base_url=base_url,
            local_repo_path=str(repo) if repo else "",
            api_available=bool(base_url),
            last_sync_at=latest.completed_at if latest else "",
            cached_event_count=self.cache.count_events(),
            privacy_mode=privacy_mode,
        )

    def sync(self, *, privacy_mode: bool = False) -> WorldMonitorSyncStatus:
        started = _utc_now()
        base_url = self.client.discover_base_url()
        if not base_url:
            sync = WorldMonitorSyncStatus(
                status="unavailable",
                imported_event_count=0,
                source_count=0,
                started_at=started,
                completed_at=_utc_now(),
                base_url="",
                privacy_mode=privacy_mode,
                error="No local WorldMonitor API detected.",
            )
            self.cache.record_sync(sync)
            return sync

        payload = self.client.fetch_bootstrap()
        if not payload:
            sync = WorldMonitorSyncStatus(
                status="cached_fallback",
                imported_event_count=0,
                source_count=0,
                started_at=started,
                completed_at=_utc_now(),
                base_url=base_url,
                privacy_mode=privacy_mode,
                error="Local WorldMonitor API returned no bootstrap data.",
            )
            self.cache.record_sync(sync)
            return sync

        events = events_from_payload(payload, imported_at=_utc_now())
        self.cache.upsert_events(events)
        sync = WorldMonitorSyncStatus(
            status="synced",
            imported_event_count=len(events),
            source_count=len(
                {event.source_url for event in events if event.source_url}
            ),
            started_at=started,
            completed_at=_utc_now(),
            base_url=base_url,
            privacy_mode=privacy_mode,
        )
        self.cache.record_sync(sync)
        self._record_memory(events, sync, privacy_mode=privacy_mode)
        return sync

    def imported_events(
        self,
        *,
        category: str | None = None,
        map_only: bool = False,
        limit: int = 100,
    ) -> list[WorldMonitorEvent]:
        events = self.cache.list_events(
            category=category,
            map_only=map_only,
            limit=limit,
        )
        return map_events(events) if map_only else events

    def briefing_data(self, *, limit: int = 40) -> WorldMonitorBriefingData:
        events = self.imported_events(limit=limit)
        imported_at = events[0].imported_at if events else ""
        return briefing_from_events(events, imported_at=imported_at)

    def morning_news_items(self, *, limit: int = 20) -> list:
        return to_news_items(self.imported_events(limit=limit))

    def morning_events(self, *, limit: int = 40) -> list:
        return to_morning_events(self.imported_events(limit=limit))

    def latest_sync(self) -> WorldMonitorSyncStatus | None:
        return self.cache.latest_sync()

    def _record_memory(
        self,
        events: list[WorldMonitorEvent],
        sync: WorldMonitorSyncStatus,
        *,
        privacy_mode: bool,
    ) -> None:
        if self.memory_service is None or privacy_mode or not events:
            return
        try:
            content = (
                f"Imported {len(events)} WorldMonitor events "
                "for local briefing context."
            )
            self.memory_service.create_memory(
                content,
                memory_type="worldmonitor_sync",
                source=(
                    {
                        "title": "WorldMonitor local sync",
                        "url": events[0].source_url,
                        "timestamp": sync.completed_at,
                        "relevance": 0.6,
                        "tags": ["worldmonitor"],
                    }
                    if events[0].source_url
                    else None
                ),
                metadata={
                    "event_count": len(events),
                    "source_count": sync.source_count,
                    "base_url": sync.base_url,
                    "local_only": True,
                    "remote_telemetry": False,
                },
                tags=["worldmonitor", "morning-briefing"],
            )
        except Exception:
            return


__all__ = ["WorldMonitorService"]
