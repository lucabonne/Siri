from __future__ import annotations

from pathlib import Path

from openjarvis.morning_briefing import MorningBriefingService
from openjarvis.worldmonitor import WorldMonitorService
from openjarvis.worldmonitor.adapters import events_from_payload


class FakeClient:
    base_url = "http://127.0.0.1:5173"

    def discover_base_url(self) -> str:
        return self.base_url

    def fetch_bootstrap(self) -> dict:
        return {
            "conflictEvents": {
                "events": [
                    {
                        "id": "wm-1",
                        "title": "Paris climate talks resume",
                        "summary": "Negotiators returned to Paris for climate talks.",
                        "lat": 48.8566,
                        "lon": 2.3522,
                        "sourceUrl": "https://example.test/paris",
                        "source": "WorldMonitor",
                        "severity": "medium",
                    }
                ]
            }
        }


class EmptyFetcher:
    def fetch(self, *, max_items: int = 12):
        return []


def test_events_from_bootstrap_payload() -> None:
    events = events_from_payload(FakeClient().fetch_bootstrap(), imported_at="now")

    assert len(events) == 1
    assert events[0].title == "Paris climate talks resume"
    assert events[0].latitude == 48.8566
    assert events[0].source_url == "https://example.test/paris"


def test_worldmonitor_sync_caches_events(tmp_path: Path) -> None:
    service = WorldMonitorService(
        db_path=tmp_path / "wm.db",
        client=FakeClient(),
    )
    try:
        sync = service.sync(privacy_mode=True)

        assert sync.status == "synced"
        assert sync.imported_event_count == 1
        assert service.status(privacy_mode=True).connected is True
        assert service.imported_events(map_only=True)[0].source_name == "WorldMonitor"
        assert service.briefing_data().source_urls == ["https://example.test/paris"]
    finally:
        service.close()


def test_morning_briefing_can_use_worldmonitor_in_privacy_mode(tmp_path: Path) -> None:
    wm = WorldMonitorService(
        db_path=tmp_path / "briefing.db",
        client=FakeClient(),
    )
    service = MorningBriefingService(
        db_path=tmp_path / "briefing.db",
        news_fetcher=EmptyFetcher(),
        worldmonitor_service=wm,
    )
    try:
        briefing = service.regenerate_briefing(privacy_mode=True)

        assert briefing.metadata["worldmonitor_source"] is True
        assert briefing.metadata["external_fetching"] is False
        assert briefing.events[0].metadata["source"] == "worldmonitor"
    finally:
        service.close()
        wm.close()
