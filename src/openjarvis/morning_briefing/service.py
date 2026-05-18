"""Service and SQLite storage for Siri Morning Briefing Phase 1."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from openjarvis.morning_briefing.events import categorize_events
from openjarvis.morning_briefing.models import (
    BriefingStatus,
    DailyBriefing,
    MorningEvent,
    NewsItem,
)
from openjarvis.morning_briefing.news_fetch import NewsFetcher
from openjarvis.morning_briefing.scheduler import MorningBriefingScheduler
from openjarvis.morning_briefing.summarizer import BriefingSummarizer
from openjarvis.morning_briefing.world_map import world_map_events


class PrivacyModeError(RuntimeError):
    """Raised when an action would require external fetching in Privacy Mode."""


class NewsFetcherProtocol(Protocol):
    def fetch(self, *, max_items: int = 12) -> list[NewsItem]: ...


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _date_for(now: datetime | None = None) -> str:
    return now.date().isoformat() if now is not None else _today()


def _timestamp_for(now: datetime | None = None) -> str:
    if now is None:
        return _utc_now()
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class MorningBriefingService:
    """Coordinate fetching, summarization, storage, and cached retrieval."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        news_fetcher: NewsFetcherProtocol | None = None,
        summarizer: BriefingSummarizer | None = None,
        scheduler: MorningBriefingScheduler | None = None,
        memory_service: Any = None,
        worldmonitor_service: Any = None,
    ) -> None:
        if db_path is None:
            db_path = Path.home() / ".openjarvis" / "siri_memory.db"
        self.db_path = Path(db_path).expanduser()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._fetcher = news_fetcher or NewsFetcher()
        self._summarizer = summarizer or BriefingSummarizer()
        self._scheduler = scheduler or MorningBriefingScheduler()
        self._memory_service = memory_service
        self._worldmonitor_service = worldmonitor_service
        self._create_schema()

    def close(self) -> None:
        self._conn.close()

    def _create_schema(self) -> None:
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_briefings (
                id TEXT PRIMARY KEY,
                briefing_date TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS morning_events (
                id TEXT PRIMARY KEY,
                briefing_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'world',
                summary TEXT NOT NULL DEFAULT '',
                latitude REAL,
                longitude REAL,
                location_name TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL DEFAULT '',
                importance INTEGER NOT NULL DEFAULT 3,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(briefing_id) REFERENCES daily_briefings(id)
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_daily_briefings_date
            ON daily_briefings(briefing_date, created_at);
            CREATE INDEX IF NOT EXISTS idx_morning_events_briefing
            ON morning_events(briefing_id);
            CREATE INDEX IF NOT EXISTS idx_morning_events_category
            ON morning_events(category);
            CREATE INDEX IF NOT EXISTS idx_morning_events_location
            ON morning_events(latitude, longitude);
            """
        )
        self._conn.commit()

    def latest_briefing(self) -> DailyBriefing | None:
        row = self._conn.execute(
            """
            SELECT * FROM daily_briefings
            ORDER BY briefing_date DESC, created_at DESC
            LIMIT 1
            """
        ).fetchone()
        return self._row_to_briefing(row) if row else None

    def list_briefings(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[DailyBriefing]:
        rows = self._conn.execute(
            """
            SELECT * FROM daily_briefings
            ORDER BY briefing_date DESC, created_at DESC
            LIMIT ? OFFSET ?
            """,
            (max(1, min(limit, 100)), max(0, offset)),
        ).fetchall()
        return [self._row_to_briefing(row) for row in rows]

    def events(
        self,
        *,
        category: str | None = None,
        world_map_only: bool = False,
        limit: int = 100,
    ) -> list[MorningEvent]:
        sql = "SELECT * FROM morning_events WHERE 1 = 1"
        params: list[Any] = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if world_map_only:
            sql += (
                " AND latitude IS NOT NULL"
                " AND longitude IS NOT NULL"
                " AND source_url != ''"
            )
        sql += " ORDER BY created_at DESC, importance DESC LIMIT ?"
        params.append(max(1, min(limit, 250)))
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def regenerate_briefing(
        self,
        *,
        location_name: str = "",
        max_items: int = 12,
        privacy_mode: bool = False,
        persist_memory: bool = True,
        now: datetime | None = None,
    ) -> DailyBriefing:
        """Generate and store a new briefing.

        In Privacy Mode, no network fetch is attempted. The newest cached
        briefing is returned when present; otherwise a PrivacyModeError is
        raised so callers can surface "cached only" clearly.
        """

        if privacy_mode:
            worldmonitor_events = self._worldmonitor_events(
                max_items=max_items,
                privacy_mode=True,
            )
            if worldmonitor_events:
                summary, content = self._summarizer.summarize(
                    worldmonitor_events,
                    location_name=location_name,
                )
                return self._store_briefing(
                    title=f"Morning Briefing - {_date_for(now)}",
                    summary=summary,
                    content=content,
                    events=worldmonitor_events,
                    location_name=location_name,
                    metadata={
                        "external_fetching": False,
                        "worldmonitor_source": True,
                        "privacy_mode_local_ingestion": True,
                        "source_count": len(
                            {
                                event.source_url
                                for event in worldmonitor_events
                                if event.source_url
                            }
                        ),
                        "world_map_event_count": len(
                            world_map_events(worldmonitor_events)
                        ),
                        "passive_only": True,
                        "notifications": False,
                        "cloud_persistence": False,
                    },
                    now=now,
                )
            cached = self.latest_briefing()
            if cached is not None:
                cached.metadata["privacy_mode_cached_only"] = True
                return cached
            raise PrivacyModeError("Privacy Mode allows cached briefings only.")

        worldmonitor_events = self._worldmonitor_events(
            max_items=max_items,
            privacy_mode=False,
        )
        items = self._fetcher.fetch(max_items=max_items)
        events = categorize_events(items, user_location=location_name)
        if worldmonitor_events:
            events = worldmonitor_events + events
        summary, content = self._summarizer.summarize(
            events,
            location_name=location_name,
        )
        briefing = self._store_briefing(
            title=f"Morning Briefing - {_date_for(now)}",
            summary=summary,
            content=content,
            events=events,
            location_name=location_name,
            metadata={
                "external_fetching": True,
                "worldmonitor_source": bool(worldmonitor_events),
                "source_count": len(
                    {event.source_url for event in events if event.source_url}
                ),
                "world_map_event_count": len(world_map_events(events)),
                "passive_only": True,
                "notifications": False,
                "cloud_persistence": False,
            },
            now=now,
        )
        if persist_memory:
            self._record_memory(briefing)
        return briefing

    def status(self, *, privacy_mode: bool = False) -> BriefingStatus:
        latest = self.latest_briefing()
        latest_date = latest.briefing_date if latest else ""
        return BriefingStatus(
            has_cached_briefing=latest is not None,
            latest_generated_at=latest.generated_at if latest else "",
            latest_briefing_date=latest_date,
            external_fetching_enabled=not privacy_mode,
            privacy_mode=privacy_mode,
            scheduler=self._scheduler.status(latest_briefing_date=latest_date),
            source_count=len(latest.source_links) if latest else 0,
            event_count=len(latest.events) if latest else 0,
        )

    def _worldmonitor_events(
        self,
        *,
        max_items: int,
        privacy_mode: bool,
    ) -> list[MorningEvent]:
        if self._worldmonitor_service is None:
            return []
        try:
            self._worldmonitor_service.sync(privacy_mode=privacy_mode)
        except Exception:
            pass
        try:
            return self._worldmonitor_service.morning_events(limit=max_items)
        except Exception:
            return []

    def _store_briefing(
        self,
        *,
        title: str,
        summary: str,
        content: str,
        events: list[MorningEvent],
        location_name: str,
        metadata: dict[str, Any],
        now: datetime | None = None,
    ) -> DailyBriefing:
        briefing_id = str(uuid.uuid4())
        generated_at = _timestamp_for(now)
        briefing_date = _date_for(now)
        source_links = sorted(
            {event.source_url for event in events if event.source_url}
        )
        enriched_metadata = {
            **metadata,
            "summary": summary,
            "source_links": source_links,
            "location_name": location_name,
            "generated_at": generated_at,
        }
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO daily_briefings (
                    id, briefing_date, title, content, metadata, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    briefing_id,
                    briefing_date,
                    title,
                    content,
                    _json_dumps(enriched_metadata),
                    generated_at,
                    generated_at,
                ),
            )
            for event in events:
                event.created_at = generated_at
                stored_event_id = f"{event.id}-{briefing_id[:8]}"
                self._conn.execute(
                    """
                    INSERT INTO morning_events (
                        id, briefing_id, title, category, summary, latitude, longitude,
                        location_name, source_url, source_name, published_at,
                        importance, metadata, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stored_event_id,
                        briefing_id,
                        event.title,
                        event.category,
                        event.summary,
                        event.latitude,
                        event.longitude,
                        event.location_name,
                        event.source_url,
                        event.source_name,
                        event.published_at,
                        event.importance,
                        _json_dumps(event.metadata),
                        generated_at,
                    ),
                )
        return self._row_to_briefing(
            self._conn.execute(
                "SELECT * FROM daily_briefings WHERE id = ?",
                (briefing_id,),
            ).fetchone()
        )

    def _record_memory(self, briefing: DailyBriefing) -> None:
        if self._memory_service is None:
            return
        try:
            self._memory_service.create_memory(
                briefing.summary,
                memory_type="daily_briefing",
                source=(
                    {
                        "title": briefing.title,
                        "url": briefing.source_links[0],
                        "timestamp": briefing.generated_at,
                        "relevance": 0.7,
                        "tags": ["morning-briefing"],
                    }
                    if briefing.source_links
                    else None
                ),
                metadata={
                    "briefing_id": briefing.id,
                    "briefing_date": briefing.briefing_date,
                    "event_count": len(briefing.events),
                    "local_only": True,
                    "cloud_persistence": False,
                },
                tags=["morning-briefing", "daily-briefing"],
            )
        except Exception:
            return

    def _row_to_briefing(self, row: sqlite3.Row) -> DailyBriefing:
        metadata = _json_loads(row["metadata"], {})
        events = self._events_for_briefing(row["id"])
        return DailyBriefing(
            id=row["id"],
            briefing_date=row["briefing_date"],
            title=row["title"],
            summary=str(metadata.get("summary") or row["content"][:240]),
            content=row["content"],
            events=events,
            source_links=list(metadata.get("source_links") or []),
            location_name=str(metadata.get("location_name") or ""),
            generated_at=str(metadata.get("generated_at") or row["created_at"]),
            updated_at=row["updated_at"],
            metadata=metadata,
        )

    def _events_for_briefing(self, briefing_id: str) -> list[MorningEvent]:
        rows = self._conn.execute(
            """
            SELECT * FROM morning_events
            WHERE briefing_id = ?
            ORDER BY importance DESC, created_at DESC
            """,
            (briefing_id,),
        ).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> MorningEvent:
        return MorningEvent(
            id=row["id"],
            title=row["title"],
            category=row["category"],
            summary=row["summary"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            location_name=row["location_name"],
            source_url=row["source_url"],
            source_name=row["source_name"],
            published_at=row["published_at"],
            importance=int(row["importance"]),
            metadata=_json_loads(row["metadata"], {}),
            created_at=row["created_at"],
        )


__all__ = ["MorningBriefingService", "PrivacyModeError"]
