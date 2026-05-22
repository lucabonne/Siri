"""Low-level SQLite CRUD helpers for vault notes.

All helpers accept an open ``sqlite3.Connection`` so they can be composed
inside transactions by higher-level callers (e.g. ``KnowledgeVaultService``).
The connection must have ``row_factory = sqlite3.Row`` set before calling.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from typing import Any


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _jd(value: Any) -> str:
    """JSON-encode a value, falling back to ``{}`` / ``[]``."""
    if value is None:
        return "[]"
    return json.dumps(value, sort_keys=True)


def _jl(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

VAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_notes (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    note_type   TEXT NOT NULL DEFAULT 'note',
    tags        TEXT NOT NULL DEFAULT '[]',
    pinned      INTEGER NOT NULL DEFAULT 0,
    source_links TEXT NOT NULL DEFAULT '[]',
    project_id  TEXT,
    date        TEXT,
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vault_backlinks (
    id              TEXT PRIMARY KEY,
    source_note_id  TEXT NOT NULL,
    target_note_id  TEXT NOT NULL,
    context_snippet TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    FOREIGN KEY(source_note_id) REFERENCES vault_notes(id) ON DELETE CASCADE,
    FOREIGN KEY(target_note_id) REFERENCES vault_notes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vault_notes_type    ON vault_notes(note_type);
CREATE INDEX IF NOT EXISTS idx_vault_notes_date    ON vault_notes(date);
CREATE INDEX IF NOT EXISTS idx_vault_notes_pinned  ON vault_notes(pinned);
CREATE INDEX IF NOT EXISTS idx_vault_notes_project ON vault_notes(project_id);
CREATE INDEX IF NOT EXISTS idx_vault_bl_source     ON vault_backlinks(source_note_id);
CREATE INDEX IF NOT EXISTS idx_vault_bl_target     ON vault_backlinks(target_note_id);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS vault_notes_fts
USING fts5(id UNINDEXED, title, content, tags)
"""


def ensure_schema(conn: sqlite3.Connection) -> bool:
    """Create vault tables.  Returns True if FTS was created successfully."""
    conn.executescript(VAULT_SCHEMA)
    fts_ok = False
    try:
        conn.executescript(FTS_SCHEMA)
        fts_ok = True
    except sqlite3.Error:
        pass
    conn.commit()
    return fts_ok


# ---------------------------------------------------------------------------
# Row converter
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "note_type": row["note_type"],
        "tags": _jl(row["tags"], []),
        "pinned": bool(row["pinned"]),
        "source_links": _jl(row["source_links"], []),
        "project_id": row["project_id"],
        "date": row["date"],
        "metadata": _jl(row["metadata"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "backlinks": [],
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_note(
    conn: sqlite3.Connection,
    *,
    title: str,
    content: str = "",
    note_type: str = "note",
    tags: list[str] | None = None,
    pinned: bool = False,
    source_links: list[dict] | None = None,
    project_id: str | None = None,
    date: str | None = None,
    metadata: dict | None = None,
    fts_enabled: bool = True,
) -> dict[str, Any]:
    note_id = str(uuid.uuid4())
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO vault_notes
            (id, title, content, note_type, tags, pinned, source_links,
             project_id, date, metadata, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            note_id, title, content, note_type or "note",
            _jd(tags or []), 1 if pinned else 0,
            _jd(source_links or []), project_id, date,
            json.dumps(metadata or {}, sort_keys=True), now, now,
        ),
    )
    _upsert_fts(conn, note_id, title, content, tags or [], fts_enabled=fts_enabled)
    return get_note(conn, note_id)


def get_note(conn: sqlite3.Connection, note_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM vault_notes WHERE id = ?", (note_id,)
    ).fetchone()
    if row is None:
        raise KeyError(note_id)
    return _row_to_dict(row)


def update_note(
    conn: sqlite3.Connection,
    note_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    pinned: bool | None = None,
    source_links: list[dict] | None = None,
    project_id: str | None = None,
    metadata: dict | None = None,
    fts_enabled: bool = True,
) -> dict[str, Any]:
    existing = get_note(conn, note_id)
    new_title = title if title is not None else existing["title"]
    new_content = content if content is not None else existing["content"]
    new_tags = tags if tags is not None else existing["tags"]
    new_pinned = pinned if pinned is not None else existing["pinned"]
    new_sl = source_links if source_links is not None else existing["source_links"]
    new_pid = project_id if project_id is not None else existing["project_id"]
    new_meta = metadata if metadata is not None else existing["metadata"]
    now = _utc_now()
    conn.execute(
        """
        UPDATE vault_notes SET
            title=?, content=?, tags=?, pinned=?, source_links=?,
            project_id=?, metadata=?, updated_at=?
        WHERE id=?
        """,
        (
            new_title, new_content, _jd(new_tags),
            1 if new_pinned else 0, _jd(new_sl),
            new_pid, json.dumps(new_meta, sort_keys=True), now, note_id,
        ),
    )
    _upsert_fts(
        conn, note_id, new_title, new_content, new_tags, fts_enabled=fts_enabled
    )
    return get_note(conn, note_id)


def delete_note(
    conn: sqlite3.Connection, note_id: str, *, fts_enabled: bool = True
) -> bool:
    cur = conn.execute("DELETE FROM vault_notes WHERE id = ?", (note_id,))
    if fts_enabled:
        conn.execute("DELETE FROM vault_notes_fts WHERE id = ?", (note_id,))
    # backlinks are deleted by ON DELETE CASCADE
    return cur.rowcount > 0


def pin_note(conn: sqlite3.Connection, note_id: str, pinned: bool) -> dict[str, Any]:
    now = _utc_now()
    cur = conn.execute(
        "UPDATE vault_notes SET pinned=?, updated_at=? WHERE id=?",
        (1 if pinned else 0, now, note_id),
    )
    if cur.rowcount == 0:
        raise KeyError(note_id)
    return get_note(conn, note_id)


# ---------------------------------------------------------------------------
# Listing / filtering
# ---------------------------------------------------------------------------

def list_notes(
    conn: sqlite3.Connection,
    *,
    note_type: str | None = None,
    tags: list[str] | None = None,
    pinned: bool | None = None,
    project_id: str | None = None,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM vault_notes WHERE 1=1"
    params: list[Any] = []
    if note_type:
        sql += " AND note_type = ?"
        params.append(note_type)
    if pinned is not None:
        sql += " AND pinned = ?"
        params.append(1 if pinned else 0)
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    if date:
        sql += " AND date = ?"
        params.append(date)
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    if tags:
        for tag in tags:
            sql += " AND tags LIKE ?"
            params.append(f"%{tag}%")
    sql += " ORDER BY pinned DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([max(1, min(limit, 200)), max(0, offset)])
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_note_by_title(conn: sqlite3.Connection, title: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM vault_notes WHERE lower(title) = lower(?)", (title,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_all_notes_index(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {title.lower(): note_id} for backlink resolution."""
    rows = conn.execute("SELECT id, title FROM vault_notes").fetchall()
    return {row["title"].lower(): row["id"] for row in rows}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_notes_fts(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
    fts_enabled: bool = True,
) -> list[dict[str, Any]]:
    if not fts_enabled:
        return search_notes_like(conn, query, limit=limit)
    tokens = re.findall(r"[\w]+", query)
    fts_query = " OR ".join(tokens) if tokens else query
    try:
        sql = """
            SELECT n.*, bm25(vault_notes_fts) * -1 AS score
            FROM vault_notes_fts
            JOIN vault_notes n ON n.id = vault_notes_fts.id
            WHERE vault_notes_fts MATCH ?
            ORDER BY score DESC, n.pinned DESC
            LIMIT ?
        """
        rows = conn.execute(sql, (fts_query, max(1, min(limit, 100)))).fetchall()
        return [_row_to_dict(row) for row in rows]
    except sqlite3.Error:
        return search_notes_like(conn, query, limit=limit)


def search_notes_like(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    like = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM vault_notes
        WHERE lower(title) LIKE lower(?) OR lower(content) LIKE lower(?)
           OR lower(tags) LIKE lower(?)
        ORDER BY pinned DESC, created_at DESC
        LIMIT ?
        """,
        (like, like, like, max(1, min(limit, 100))),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# FTS helpers
# ---------------------------------------------------------------------------

def _upsert_fts(
    conn: sqlite3.Connection,
    note_id: str,
    title: str,
    content: str,
    tags: list[str],
    *,
    fts_enabled: bool = True,
) -> None:
    if not fts_enabled:
        return
    try:
        conn.execute("DELETE FROM vault_notes_fts WHERE id = ?", (note_id,))
        conn.execute(
            "INSERT INTO vault_notes_fts"
            " (id, title, content, tags) VALUES (?, ?, ?, ?)",
            (note_id, title, content, " ".join(tags)),
        )
    except sqlite3.Error:
        pass


__all__ = [
    "ensure_schema",
    "create_note",
    "get_note",
    "update_note",
    "delete_note",
    "pin_note",
    "list_notes",
    "get_note_by_title",
    "get_all_notes_index",
    "search_notes_fts",
    "search_notes_like",
]
