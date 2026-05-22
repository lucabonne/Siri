"""Tag helpers for the Siri Knowledge Vault.

Tags are stored as JSON arrays in ``vault_notes.tags``.  This module also
supports extracting inline ``#hashtag`` syntax from note content and
aggregating tag counts across the vault.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

# Inline hashtag pattern — #word, #multi-word is NOT supported (Obsidian style)
_INLINE_TAG_RE = re.compile(r"(?:^|(?<=\s))#([\w][\w-]*)(?=\s|$)", re.MULTILINE)


def extract_inline_tags(content: str) -> list[str]:
    """Return a deduplicated list of ``#tag`` values found in *content*.

    The leading ``#`` is stripped from the returned values so callers can
    compare against stored tag arrays directly.
    """
    seen: set[str] = set()
    result: list[str] = []
    for m in _INLINE_TAG_RE.finditer(content):
        tag = m.group(1).lower()
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def merge_tags(explicit: list[str], inline: list[str]) -> list[str]:
    """Return the union of *explicit* (user-provided) and *inline* tags."""
    seen: set[str] = set()
    merged: list[str] = []
    for tag in explicit + inline:
        t = tag.lower().strip().lstrip("#")
        if t and t not in seen:
            seen.add(t)
            merged.append(t)
    return merged


def list_all_tags(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return ``[{name, count}]`` sorted by count descending."""
    rows = conn.execute(
        "SELECT tags FROM vault_notes WHERE tags IS NOT NULL AND tags != '[]'"
    ).fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        try:
            tags: list[str] = json.loads(row["tags"])
        except (json.JSONDecodeError, TypeError):
            continue
        for tag in tags:
            t = str(tag).strip()
            if t:
                counts[t] = counts.get(t, 0) + 1
    return sorted(
        [{"name": k, "count": v} for k, v in counts.items()],
        key=lambda x: (-x["count"], x["name"]),
    )


def get_notes_by_tag(
    conn: sqlite3.Connection,
    tag: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return notes that contain *tag* in their tags array.

    Uses a SQLite LIKE search over the JSON-encoded tags column.
    """
    from openjarvis.knowledge_vault.notes import _row_to_dict  # noqa: PLC0415

    like = f'%"{tag}"%'
    rows = conn.execute(
        """
        SELECT * FROM vault_notes
        WHERE tags LIKE ?
        ORDER BY pinned DESC, created_at DESC
        LIMIT ?
        """,
        (like, max(1, min(limit, 200))),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


__all__ = [
    "extract_inline_tags",
    "merge_tags",
    "list_all_tags",
    "get_notes_by_tag",
]
