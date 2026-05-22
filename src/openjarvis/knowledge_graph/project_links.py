"""Project decision tracking helpers for the local Knowledge Graph."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from openjarvis.knowledge_graph.nodes import json_dumps, json_loads, utc_now

DECISION_SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_project_decisions (
    id         TEXT PRIMARY KEY,
    node_id    TEXT,
    project_id TEXT NOT NULL,
    title      TEXT NOT NULL,
    decision   TEXT NOT NULL,
    rationale  TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'accepted',
    made_at    TEXT NOT NULL,
    note_id    TEXT,
    metadata   TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(node_id) REFERENCES graph_nodes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_graph_decisions_project
ON graph_project_decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_graph_decisions_note
ON graph_project_decisions(note_id);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DECISION_SCHEMA)
    conn.commit()


def row_to_decision(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "node_id": row["node_id"],
        "project_id": row["project_id"],
        "title": row["title"],
        "decision": row["decision"],
        "rationale": row["rationale"],
        "status": row["status"],
        "made_at": row["made_at"],
        "note_id": row["note_id"],
        "metadata": json_loads(row["metadata"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_decision(
    conn: sqlite3.Connection,
    *,
    node_id: str | None = None,
    project_id: str,
    title: str,
    decision: str,
    rationale: str = "",
    status: str = "accepted",
    made_at: str | None = None,
    note_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not project_id.strip():
        raise ValueError("project_id cannot be empty")
    if not title.strip():
        raise ValueError("project decision title cannot be empty")
    if not decision.strip():
        raise ValueError("project decision cannot be empty")
    now = utc_now()
    decision_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO graph_project_decisions (
            id, node_id, project_id, title, decision, rationale, status,
            made_at, note_id, metadata, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            decision_id,
            node_id,
            project_id,
            title.strip(),
            decision,
            rationale,
            status or "accepted",
            made_at or now,
            note_id,
            json_dumps(metadata or {}),
            now,
            now,
        ),
    )
    return get_decision(conn, decision_id)


def get_decision(conn: sqlite3.Connection, decision_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM graph_project_decisions WHERE id = ?", (decision_id,)
    ).fetchone()
    if row is None:
        raise KeyError(decision_id)
    return row_to_decision(row)


def list_decisions(
    conn: sqlite3.Connection,
    *,
    project_id: str | None = None,
    note_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM graph_project_decisions WHERE 1=1"
    params: list[Any] = []
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    if note_id:
        sql += " AND note_id = ?"
        params.append(note_id)
    sql += " ORDER BY made_at DESC, created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))
    rows = conn.execute(sql, params).fetchall()
    return [row_to_decision(row) for row in rows]


__all__ = ["ensure_schema", "create_decision", "get_decision", "list_decisions"]
