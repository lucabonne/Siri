from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from openjarvis.morning_briefing import (
    MorningBriefingService,
    NewsItem,
    PrivacyModeError,
)
from openjarvis.morning_briefing.scheduler import MorningBriefingScheduler


class FakeFetcher:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, *, max_items: int = 12) -> list[NewsItem]:
        self.calls += 1
        return [
            NewsItem(
                title="Rome expands AI safety summit",
                summary="Officials in Rome announced a new technology policy forum.",
                source_url="https://example.test/rome-ai",
                source_name="Example News",
                published_at="2026-05-15T06:00:00Z",
            ),
            NewsItem(
                title="Tokyo markets watch bank earnings",
                summary="Market analysts are watching bank stocks.",
                source_url="https://example.test/tokyo-chip",
                source_name="Example Markets",
                published_at="2026-05-15T06:10:00Z",
            ),
        ][:max_items]


def test_regenerate_stores_briefing_events_and_world_map_points(tmp_path: Path) -> None:
    fetcher = FakeFetcher()
    service = MorningBriefingService(
        db_path=tmp_path / "briefings.db",
        news_fetcher=fetcher,
    )
    try:
        briefing = service.regenerate_briefing(location_name="Rome")

        assert briefing.title.startswith("Morning Briefing")
        assert briefing.source_links == [
            "https://example.test/rome-ai",
            "https://example.test/tokyo-chip",
        ]
        assert {event.category for event in briefing.events} >= {
            "technology",
            "economy",
        }
        assert service.latest_briefing().id == briefing.id
        assert service.events(world_map_only=True)

        conn = sqlite3.connect(tmp_path / "briefings.db")
        tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type IN ('table', 'virtual table')
                """
            )
        }
        assert {"daily_briefings", "morning_events"}.issubset(tables)
    finally:
        service.close()


def test_privacy_mode_uses_cache_without_fetching(tmp_path: Path) -> None:
    fetcher = FakeFetcher()
    service = MorningBriefingService(
        db_path=tmp_path / "briefings.db",
        news_fetcher=fetcher,
    )
    try:
        cached = service.regenerate_briefing()
        assert fetcher.calls == 1

        result = service.regenerate_briefing(privacy_mode=True)

        assert result.id == cached.id
        assert result.metadata["privacy_mode_cached_only"] is True
        assert fetcher.calls == 1
    finally:
        service.close()


def test_privacy_mode_without_cache_raises(tmp_path: Path) -> None:
    fetcher = FakeFetcher()
    service = MorningBriefingService(
        db_path=tmp_path / "briefings.db",
        news_fetcher=fetcher,
    )
    try:
        with pytest.raises(PrivacyModeError):
            service.regenerate_briefing(privacy_mode=True)
        assert fetcher.calls == 0
    finally:
        service.close()


def test_scheduler_reports_due_once_per_day() -> None:
    scheduler = MorningBriefingScheduler()
    status = scheduler.status(latest_briefing_date="1900-01-01")

    assert status["phase"] == "abstraction_only"
    assert status["background_notifications"] is False
