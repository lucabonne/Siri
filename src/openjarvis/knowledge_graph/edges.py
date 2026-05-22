"""SQLite edge helpers for the local Knowledge Graph."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from openjarvis.knowledge_graph.nodes import json_dumps, json_loads, utc_now

EDGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_edges (
    id           TEXT PRIMARY KEY,
    source_id    TEXT NOT NULL,
    target_id    TEXT NOT NULL,
    relationship TEXT NOT NULL,
    weight       REAL NOT NULL DEFAULT 1.0,
    directed     INTEGER NOT NULL DEFAULT 1,
    metadata     TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES graph_nodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_rel ON graph_edges(relationship);
CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_edges_unique
ON graph_edges(source_id, target_id, relationship);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(EDGE_SCHEMA)
    conn.commit()


def row_to_edge(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source_id": row["source_id"],
        "target_id": row["target_id"],
        "relationship": row["relationship"],
        "weight": float(row["weight"]),
        "directed": bool(row["directed"]),
        "metadata": json_loads(row["metadata"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_edge(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    target_id: str,
    relationship: str,
    weight: float = 1.0,
    directed: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if source_id == target_id:
        raise ValueError("graph edge cannot connect a node to itself")
    now = utc_now()
    edge_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO graph_edges (
            id, source_id, target_id, relationship, weight, directed,
            metadata, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, target_id, relationship) DO UPDATE SET
            weight=excluded.weight,
            directed=excluded.directed,
            metadata=excluded.metadata,
            updated_at=excluded.updated_at
        """,
        (
            edge_id,
            source_id,
            target_id,
            relationship,
            float(weight),
            1 if directed else 0,
            json_dumps(metadata or {}),
            now,
            now,
        ),
    )
    return get_edge_between(conn, source_id, target_id, relationship)


def get_edge(conn: sqlite3.Connection, edge_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM graph_edges WHERE id = ?", (edge_id,)).fetchone()
    if row is None:
        raise KeyError(edge_id)
    return row_to_edge(row)


def get_edge_between(
    conn: sqlite3.Connection,
    source_id: str,
    target_id: str,
    relationship: str,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT * FROM graph_edges
        WHERE source_id = ? AND target_id = ? AND relationship = ?
        """,
        (source_id, target_id, relationship),
    ).fetchone()
    if row is None:
        raise KeyError(f"{source_id}->{target_id}:{relationship}")
    return row_to_edge(row)


def list_edges(
    conn: sqlite3.Connection,
    *,
    node_id: str | None = None,
    relationship: str | None = None,
    direction: str = "both",
    limit: int = 100,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM graph_edges WHERE 1=1"
    params: list[Any] = []
    if node_id:
        if direction == "out":
            sql += " AND source_id = ?"
            params.append(node_id)
        elif direction == "in":
            sql += " AND target_id = ?"
            params.append(node_id)
        else:
            sql += " AND (source_id = ? OR target_id = ?)"
            params.extend([node_id, node_id])
    if relationship:
        sql += " AND relationship = ?"
        params.append(relationship)
    sql += " ORDER BY weight DESC, updated_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))
    rows = conn.execute(sql, params).fetchall()
    return [row_to_edge(row) for row in rows]


def delete_edge(conn: sqlite3.Connection, edge_id: str) -> bool:
    cur = conn.execute("DELETE FROM graph_edges WHERE id = ?", (edge_id,))
    return cur.rowcount > 0


def neighbor_ids(
    conn: sqlite3.Connection,
    node_id: str,
) -> list[tuple[str, dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT * FROM graph_edges
        WHERE source_id = ? OR target_id = ?
        ORDER BY weight DESC, updated_at DESC
        """,
        (node_id, node_id),
    ).fetchall()
    pairs: list[tuple[str, dict[str, Any]]] = []
    for row in rows:
        edge = row_to_edge(row)
        other = edge["target_id"] if edge["source_id"] == node_id else edge["source_id"]
        pairs.append((other, edge))
    return pairs


__all__ = [
    "ensure_schema",
    "create_edge",
    "get_edge",
    "list_edges",
    "delete_edge",
    "neighbor_ids",
]
