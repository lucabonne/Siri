"""Timeline event storage for graph-aware history."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from openjarvis.knowledge_graph.nodes import json_dumps, json_loads, utc_now

TIMELINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_timeline_events (
    id          TEXT PRIMARY KEY,
    node_id     TEXT,
    project_id  TEXT,
    event_type  TEXT NOT NULL DEFAULT 'event',
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    FOREIGN KEY(node_id) REFERENCES graph_nodes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_graph_timeline_node ON graph_timeline_events(node_id);
CREATE INDEX IF NOT EXISTS idx_graph_timeline_project
ON graph_timeline_events(project_id);
CREATE INDEX IF NOT EXISTS idx_graph_timeline_time
ON graph_timeline_events(occurred_at);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(TIMELINE_SCHEMA)
    conn.commit()


def row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "node_id": row["node_id"],
        "project_id": row["project_id"],
        "event_type": row["event_type"],
        "title": row["title"],
        "summary": row["summary"],
        "occurred_at": row["occurred_at"],
        "metadata": json_loads(row["metadata"], {}),
        "created_at": row["created_at"],
    }


def create_event(
    conn: sqlite3.Connection,
    *,
    node_id: str | None = None,
    project_id: str | None = None,
    event_type: str = "event",
    title: str,
    summary: str = "",
    occurred_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("timeline event title cannot be empty")
    now = utc_now()
    event_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO graph_timeline_events (
            id, node_id, project_id, event_type, title, summary, occurred_at,
            metadata, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            node_id,
            project_id,
            event_type or "event",
            title.strip(),
            summary,
            occurred_at or now,
            json_dumps(metadata or {}),
            now,
        ),
    )
    return get_event(conn, event_id)


def get_event(conn: sqlite3.Connection, event_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM graph_timeline_events WHERE id = ?", (event_id,)
    ).fetchone()
    if row is None:
        raise KeyError(event_id)
    return row_to_event(row)


def list_events(
    conn: sqlite3.Connection,
    *,
    node_id: str | None = None,
    project_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM graph_timeline_events WHERE 1=1"
    params: list[Any] = []
    if node_id:
        sql += " AND node_id = ?"
        params.append(node_id)
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    sql += " ORDER BY occurred_at DESC, created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))
    rows = conn.execute(sql, params).fetchall()
    return [row_to_event(row) for row in rows]


__all__ = ["ensure_schema", "create_event", "get_event", "list_events"]
