"""SQLite node lifecycle helpers for the local Knowledge Graph."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True)


def json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


NODE_SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_nodes (
    id          TEXT PRIMARY KEY,
    node_type   TEXT NOT NULL,
    title       TEXT NOT NULL,
    text        TEXT NOT NULL DEFAULT '',
    ref_id      TEXT,
    ref_table   TEXT,
    source      TEXT NOT NULL DEFAULT '',
    metadata    TEXT NOT NULL DEFAULT '{}',
    pinned_root INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_type ON graph_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_ref ON graph_nodes(ref_table, ref_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_root ON graph_nodes(pinned_root);
"""

NODE_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS graph_nodes_fts
USING fts5(id UNINDEXED, node_type, title, text, metadata)
"""


def ensure_schema(conn: sqlite3.Connection) -> bool:
    conn.executescript(NODE_SCHEMA)
    fts_ok = False
    try:
        conn.executescript(NODE_FTS_SCHEMA)
        fts_ok = True
    except sqlite3.Error:
        fts_ok = False
    conn.commit()
    return fts_ok


def row_to_node(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "node_type": row["node_type"],
        "title": row["title"],
        "text": row["text"],
        "ref_id": row["ref_id"],
        "ref_table": row["ref_table"],
        "source": row["source"],
        "metadata": json_loads(row["metadata"], {}),
        "pinned_root": bool(row["pinned_root"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def upsert_node(
    conn: sqlite3.Connection,
    *,
    node_id: str | None = None,
    node_type: str,
    title: str,
    text: str = "",
    ref_id: str | None = None,
    ref_table: str | None = None,
    source: str = "",
    metadata: dict[str, Any] | None = None,
    pinned_root: bool = False,
    fts_enabled: bool = True,
) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("graph node title cannot be empty")
    existing = (
        get_node_by_ref(conn, ref_table, ref_id) if ref_table and ref_id else None
    )
    node_id = node_id or (existing["id"] if existing else str(uuid.uuid4()))
    now = utc_now()
    created_at = existing["created_at"] if existing else now
    conn.execute(
        """
        INSERT INTO graph_nodes (
            id, node_type, title, text, ref_id, ref_table, source, metadata,
            pinned_root, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            node_type=excluded.node_type,
            title=excluded.title,
            text=excluded.text,
            ref_id=excluded.ref_id,
            ref_table=excluded.ref_table,
            source=excluded.source,
            metadata=excluded.metadata,
            pinned_root=excluded.pinned_root,
            updated_at=excluded.updated_at
        """,
        (
            node_id,
            node_type,
            title.strip(),
            text,
            ref_id,
            ref_table,
            source,
            json_dumps(metadata or {}),
            1 if pinned_root else 0,
            created_at,
            now,
        ),
    )
    upsert_fts(conn, node_id, node_type, title, text, metadata or {}, fts_enabled)
    return get_node(conn, node_id)


def get_node(conn: sqlite3.Connection, node_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (node_id,)).fetchone()
    if row is None:
        raise KeyError(node_id)
    return row_to_node(row)


def get_node_by_ref(
    conn: sqlite3.Connection,
    ref_table: str | None,
    ref_id: str | None,
) -> dict[str, Any] | None:
    if not ref_table or not ref_id:
        return None
    row = conn.execute(
        "SELECT * FROM graph_nodes WHERE ref_table = ? AND ref_id = ? LIMIT 1",
        (ref_table, ref_id),
    ).fetchone()
    return row_to_node(row) if row else None


def update_node(
    conn: sqlite3.Connection,
    node_id: str,
    *,
    title: str | None = None,
    text: str | None = None,
    metadata: dict[str, Any] | None = None,
    pinned_root: bool | None = None,
    fts_enabled: bool = True,
) -> dict[str, Any]:
    existing = get_node(conn, node_id)
    title = title if title is not None else existing["title"]
    text = text if text is not None else existing["text"]
    metadata = metadata if metadata is not None else existing["metadata"]
    pinned_root = (
        pinned_root if pinned_root is not None else existing["pinned_root"]
    )
    now = utc_now()
    conn.execute(
        """
        UPDATE graph_nodes
        SET title=?, text=?, metadata=?, pinned_root=?, updated_at=?
        WHERE id=?
        """,
        (title, text, json_dumps(metadata), 1 if pinned_root else 0, now, node_id),
    )
    upsert_fts(
        conn, node_id, existing["node_type"], title, text, metadata, fts_enabled
    )
    return get_node(conn, node_id)


def delete_node(
    conn: sqlite3.Connection,
    node_id: str,
    *,
    fts_enabled: bool = True,
) -> bool:
    cur = conn.execute("DELETE FROM graph_nodes WHERE id = ?", (node_id,))
    if fts_enabled:
        conn.execute("DELETE FROM graph_nodes_fts WHERE id = ?", (node_id,))
    return cur.rowcount > 0


def list_nodes(
    conn: sqlite3.Connection,
    *,
    node_type: str | None = None,
    pinned_root: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM graph_nodes WHERE 1=1"
    params: list[Any] = []
    if node_type:
        sql += " AND node_type = ?"
        params.append(node_type)
    if pinned_root is not None:
        sql += " AND pinned_root = ?"
        params.append(1 if pinned_root else 0)
    sql += " ORDER BY pinned_root DESC, updated_at DESC LIMIT ? OFFSET ?"
    params.extend([max(1, min(limit, 500)), max(0, offset)])
    rows = conn.execute(sql, params).fetchall()
    return [row_to_node(row) for row in rows]


def search_nodes(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
    fts_enabled: bool = True,
) -> list[dict[str, Any]]:
    if not query.strip():
        return list_nodes(conn, limit=limit)
    if fts_enabled:
        try:
            rows = conn.execute(
                """
                SELECT n.*, bm25(graph_nodes_fts) AS rank
                FROM graph_nodes_fts
                JOIN graph_nodes n ON n.id = graph_nodes_fts.id
                WHERE graph_nodes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, max(1, min(limit, 100))),
            ).fetchall()
            return [row_to_node(row) for row in rows]
        except sqlite3.Error:
            pass
    like = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM graph_nodes
        WHERE title LIKE ? OR text LIKE ? OR metadata LIKE ? OR node_type LIKE ?
        ORDER BY pinned_root DESC, updated_at DESC
        LIMIT ?
        """,
        (like, like, like, like, max(1, min(limit, 100))),
    ).fetchall()
    return [row_to_node(row) for row in rows]


def upsert_fts(
    conn: sqlite3.Connection,
    node_id: str,
    node_type: str,
    title: str,
    text: str,
    metadata: dict[str, Any],
    fts_enabled: bool,
) -> None:
    if not fts_enabled:
        return
    try:
        conn.execute("DELETE FROM graph_nodes_fts WHERE id = ?", (node_id,))
        conn.execute(
            """
            INSERT INTO graph_nodes_fts (id, node_type, title, text, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (node_id, node_type, title, text, json_dumps(metadata)),
        )
    except sqlite3.Error:
        return


__all__ = [
    "ensure_schema",
    "upsert_node",
    "get_node",
    "get_node_by_ref",
    "update_node",
    "delete_node",
    "list_nodes",
    "search_nodes",
    "utc_now",
    "json_dumps",
    "json_loads",
]
