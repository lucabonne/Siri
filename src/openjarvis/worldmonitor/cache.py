"""SQLite cache for imported WorldMonitor data."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from openjarvis.worldmonitor.models import WorldMonitorEvent, WorldMonitorSyncStatus


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class WorldMonitorCache:
    """Local SQLite cache for passive WorldMonitor imports."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".openjarvis" / "siri_memory.db"
        self.db_path = Path(db_path).expanduser()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._conn.close()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS worldmonitor_events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'world',
                signal TEXT NOT NULL DEFAULT '',
                severity TEXT NOT NULL DEFAULT '',
                latitude REAL,
                longitude REAL,
                location_name TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL DEFAULT 'WorldMonitor',
                published_at TEXT NOT NULL DEFAULT '',
                imported_at TEXT NOT NULL,
                raw_type TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS worldmonitor_syncs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                imported_event_count INTEGER NOT NULL DEFAULT 0,
                source_count INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                base_url TEXT NOT NULL DEFAULT '',
                privacy_mode INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_worldmonitor_events_imported
            ON worldmonitor_events(imported_at);
            CREATE INDEX IF NOT EXISTS idx_worldmonitor_events_category
            ON worldmonitor_events(category);
            CREATE INDEX IF NOT EXISTS idx_worldmonitor_events_map
            ON worldmonitor_events(latitude, longitude);
            """
        )
        self._conn.commit()

    def upsert_events(self, events: list[WorldMonitorEvent]) -> None:
        with self._conn:
            for event in events:
                self._conn.execute(
                    """
                    INSERT INTO worldmonitor_events (
                        id, title, summary, category, signal, severity, latitude,
                        longitude, location_name, source_url, source_name,
                        published_at, imported_at, raw_type, metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        summary=excluded.summary,
                        category=excluded.category,
                        signal=excluded.signal,
                        severity=excluded.severity,
                        latitude=excluded.latitude,
                        longitude=excluded.longitude,
                        location_name=excluded.location_name,
                        source_url=excluded.source_url,
                        source_name=excluded.source_name,
                        published_at=excluded.published_at,
                        imported_at=excluded.imported_at,
                        raw_type=excluded.raw_type,
                        metadata=excluded.metadata
                    """,
                    (
                        event.id,
                        event.title,
                        event.summary,
                        event.category,
                        event.signal,
                        event.severity,
                        event.latitude,
                        event.longitude,
                        event.location_name,
                        event.source_url,
                        event.source_name,
                        event.published_at,
                        event.imported_at,
                        event.raw_type,
                        _json_dumps(event.metadata),
                    ),
                )

    def list_events(
        self,
        *,
        category: str | None = None,
        map_only: bool = False,
        limit: int = 100,
    ) -> list[WorldMonitorEvent]:
        sql = "SELECT * FROM worldmonitor_events WHERE 1 = 1"
        params: list[Any] = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if map_only:
            sql += " AND latitude IS NOT NULL AND longitude IS NOT NULL"
        sql += " ORDER BY imported_at DESC, published_at DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def count_events(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS count FROM worldmonitor_events"
        ).fetchone()
        return int(row["count"] or 0)

    def record_sync(self, sync: WorldMonitorSyncStatus) -> None:
        self._conn.execute(
            """
            INSERT INTO worldmonitor_syncs (
                status, imported_event_count, source_count, started_at,
                completed_at, base_url, privacy_mode, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sync.status,
                sync.imported_event_count,
                sync.source_count,
                sync.started_at,
                sync.completed_at,
                sync.base_url,
                1 if sync.privacy_mode else 0,
                sync.error,
            ),
        )
        self._conn.commit()

    def latest_sync(self) -> WorldMonitorSyncStatus | None:
        row = self._conn.execute(
            """
            SELECT * FROM worldmonitor_syncs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return WorldMonitorSyncStatus(
            status=row["status"],
            imported_event_count=int(row["imported_event_count"]),
            source_count=int(row["source_count"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            base_url=row["base_url"],
            privacy_mode=bool(row["privacy_mode"]),
            error=row["error"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> WorldMonitorEvent:
        return WorldMonitorEvent(
            id=row["id"],
            title=row["title"],
            summary=row["summary"],
            category=row["category"],
            signal=row["signal"],
            severity=row["severity"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            location_name=row["location_name"],
            source_url=row["source_url"],
            source_name=row["source_name"],
            published_at=row["published_at"],
            imported_at=row["imported_at"],
            raw_type=row["raw_type"],
            metadata=_json_loads(row["metadata"], {}),
        )


__all__ = ["WorldMonitorCache"]
