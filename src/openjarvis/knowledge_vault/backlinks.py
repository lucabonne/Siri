"""Backlink extraction and storage for the Siri Knowledge Vault.

Backlinks are derived from ``[[Note Title]]`` wiki-link syntax in note
content.  Whenever a note is saved the service calls
``update_backlinks_for_note`` to recompute outgoing links from that note.

The ``vault_backlinks`` table stores *directed* edges:
    source_note_id -> target_note_id

``get_backlinks_for(note_id)`` returns all notes that link *to* ``note_id``.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from typing import Any

# Obsidian-style wiki link: [[Some Title]]
_WIKI_LINK_RE = re.compile(r"\[\[([^\[\]]+?)(?:\|[^\[\]]+?)?\]\]")


def extract_wiki_links(content: str) -> list[str]:
    """Return a list of raw wiki-link targets from *content*.

    Supports ``[[Title]]`` and ``[[Title|Alias]]`` syntax.  Returns the
    target portion only (before the ``|`` if present).
    """
    return [m.group(1).strip() for m in _WIKI_LINK_RE.finditer(content)]


def resolve_links(
    raw_titles: list[str],
    title_to_id: dict[str, str],
) -> list[tuple[str, str]]:
    """Resolve raw wiki-link titles to note IDs using *title_to_id*.

    Returns a list of ``(title, note_id)`` pairs for titles that match an
    existing note (case-insensitive).
    """
    results: list[tuple[str, str]] = []
    for title in raw_titles:
        note_id = title_to_id.get(title.lower())
        if note_id:
            results.append((title, note_id))
    return results


def _context_snippet(content: str, title: str, max_chars: int = 120) -> str:
    """Extract a short excerpt around the first occurrence of *title*."""
    idx = content.lower().find(title.lower())
    if idx == -1:
        return ""
    start = max(0, idx - 30)
    end = min(len(content), idx + len(title) + 90)
    snippet = content[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(content):
        snippet = snippet + "…"
    return snippet[:max_chars]


def update_backlinks_for_note(
    conn: sqlite3.Connection,
    source_note_id: str,
    content: str,
    title_to_id: dict[str, str],
) -> list[dict[str, Any]]:
    """Recompute outgoing backlinks from *source_note_id*.

    Deletes all existing outgoing links from this note and inserts the
    current set derived from the content.  Returns the new backlink records.
    """
    import time

    conn.execute(
        "DELETE FROM vault_backlinks WHERE source_note_id = ?",
        (source_note_id,),
    )

    raw_titles = extract_wiki_links(content)
    resolved = resolve_links(raw_titles, title_to_id)

    records: list[dict[str, Any]] = []
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for title, target_id in resolved:
        if target_id == source_note_id:
            continue  # skip self-links
        bl_id = str(uuid.uuid4())
        snippet = _context_snippet(content, title)
        conn.execute(
            """
            INSERT INTO vault_backlinks
                (id, source_note_id, target_note_id, context_snippet, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (bl_id, source_note_id, target_id, snippet, now),
        )
        records.append(
            {
                "id": bl_id,
                "source_note_id": source_note_id,
                "target_note_id": target_id,
                "context_snippet": snippet,
                "created_at": now,
            }
        )
    return records


def get_backlinks_for(
    conn: sqlite3.Connection,
    target_note_id: str,
) -> list[dict[str, Any]]:
    """Return all notes linking *to* ``target_note_id``, with source title."""
    rows = conn.execute(
        """
        SELECT bl.id, bl.source_note_id, bl.target_note_id,
               bl.context_snippet, bl.created_at,
               n.title AS source_note_title
        FROM vault_backlinks bl
        JOIN vault_notes n ON n.id = bl.source_note_id
        WHERE bl.target_note_id = ?
        ORDER BY bl.created_at DESC
        """,
        (target_note_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "source_note_id": row["source_note_id"],
            "source_note_title": row["source_note_title"],
            "target_note_id": row["target_note_id"],
            "context_snippet": row["context_snippet"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


__all__ = [
    "extract_wiki_links",
    "resolve_links",
    "update_backlinks_for_note",
    "get_backlinks_for",
]
