"""Daily note helpers for the Siri Knowledge Vault.

A daily note is a ``vault_notes`` row with ``note_type='daily'`` and a
``date`` field set to the ISO date string.  Exactly one daily note may
exist per date; ``get_or_create_daily_note`` is idempotent.
"""

from __future__ import annotations

import sqlite3
from datetime import date as _date
from typing import Any


def _today_iso() -> str:
    return _date.today().isoformat()


def get_or_create_daily_note(
    conn: sqlite3.Connection,
    target_date: str | None = None,
    *,
    fts_enabled: bool = True,
    initial_content: str = "",
    initial_tags: list[str] | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Return the daily note for ``target_date``, creating it if missing.

    ``target_date`` must be an ISO date string (YYYY-MM-DD).  Defaults to
    today.
    """
    from openjarvis.knowledge_vault.notes import (  # noqa: PLC0415
        _row_to_dict,
        create_note,
    )

    iso = target_date or _today_iso()

    row = conn.execute(
        "SELECT * FROM vault_notes WHERE note_type = 'daily' AND date = ?",
        (iso,),
    ).fetchone()
    if row is not None:
        return _row_to_dict(row)

    # Derive a friendly title from the date
    try:
        parsed = _date.fromisoformat(iso)
        title = parsed.strftime("%A, %B %-d %Y")
    except ValueError:
        title = iso

    note = create_note(
        conn,
        title=title,
        content=initial_content or f"# {title}\n\n",
        note_type="daily",
        tags=initial_tags or [],
        pinned=False,
        date=iso,
        metadata=metadata or {},
        fts_enabled=fts_enabled,
    )
    conn.commit()
    return note


def get_today_note(
    conn: sqlite3.Connection,
    *,
    fts_enabled: bool = True,
) -> dict[str, Any]:
    """Return today's daily note, creating it if it does not exist."""
    return get_or_create_daily_note(conn, fts_enabled=fts_enabled)


def list_daily_notes(
    conn: sqlite3.Connection,
    *,
    limit: int = 30,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return daily notes ordered by date descending."""
    from openjarvis.knowledge_vault.notes import _row_to_dict  # noqa: PLC0415

    rows = conn.execute(
        """
        SELECT * FROM vault_notes
        WHERE note_type = 'daily'
        ORDER BY date DESC
        LIMIT ? OFFSET ?
        """,
        (max(1, min(limit, 200)), max(0, offset)),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_daily_note_for(
    conn: sqlite3.Connection,
    target_date: str,
) -> dict[str, Any] | None:
    """Return the daily note for a specific date, or None if missing."""
    from openjarvis.knowledge_vault.notes import _row_to_dict  # noqa: PLC0415

    row = conn.execute(
        "SELECT * FROM vault_notes WHERE note_type = 'daily' AND date = ?",
        (target_date,),
    ).fetchone()
    return _row_to_dict(row) if row else None


__all__ = [
    "get_or_create_daily_note",
    "get_today_note",
    "list_daily_notes",
    "get_daily_note_for",
]
