"""Knowledge Vault Service — the main coordination layer.

This service owns its own SQLite database (``~/.openjarvis/knowledge_vault.db``
by default) and NEVER modifies the existing ``siri_memory.db`` or the
``memories`` table.  It provides a clean public API used by API routes,
tests, and integration hooks.

Integration hooks:
  - ``from_memory(memory_id, memory_service)`` — import a MemoryService record
    as a vault note without writing back to the memory DB.
  - ``link_to_research(note_id, summary)`` — attach a research summary string
    to an existing note's metadata.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from openjarvis.knowledge_vault import backlinks as _bl
from openjarvis.knowledge_vault import daily_notes as _dn
from openjarvis.knowledge_vault import notes as _notes
from openjarvis.knowledge_vault import tags as _tags
from openjarvis.knowledge_vault.markdown_export import (
    export_vault_notes,
    note_to_markdown,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".openjarvis" / "knowledge_vault.db"


class KnowledgeVaultService:
    """Local-first knowledge vault backed by a dedicated SQLite database."""

    def __init__(
        self,
        db_path: str | Path | None = None,
    ) -> None:
        if db_path is None:
            db_path = _DEFAULT_DB
        self.db_path = Path(db_path).expanduser()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._fts_enabled = _notes.ensure_schema(self._conn)
        logger.debug(
            "KnowledgeVaultService ready — db=%s fts=%s",
            self.db_path,
            self._fts_enabled,
        )

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Notes CRUD
    # ------------------------------------------------------------------

    def create_note(
        self,
        title: str,
        *,
        content: str = "",
        note_type: str = "note",
        tags: list[str] | None = None,
        pinned: bool = False,
        source_links: list[dict] | None = None,
        project_id: str | None = None,
        date: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        if not title.strip():
            raise ValueError("note title cannot be empty")
        # Merge inline #tags from content
        inline = _tags.extract_inline_tags(content)
        merged_tags = _tags.merge_tags(tags or [], inline)
        note = _notes.create_note(
            self._conn,
            title=title.strip(),
            content=content,
            note_type=note_type,
            tags=merged_tags,
            pinned=pinned,
            source_links=source_links,
            project_id=project_id,
            date=date,
            metadata=metadata,
            fts_enabled=self._fts_enabled,
        )
        # Compute backlinks from new content
        title_index = _notes.get_all_notes_index(self._conn)
        _bl.update_backlinks_for_note(
            self._conn, note["id"], content, title_index
        )
        self._conn.commit()
        return note

    def get_note(self, note_id: str) -> dict[str, Any]:
        note = _notes.get_note(self._conn, note_id)
        note["backlinks"] = _bl.get_backlinks_for(self._conn, note_id)
        return note

    def update_note(
        self,
        note_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        pinned: bool | None = None,
        source_links: list[dict] | None = None,
        project_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        # Recalculate inline tags if content changed
        if content is not None:
            inline = _tags.extract_inline_tags(content)
            tags = _tags.merge_tags(tags or [], inline)
        note = _notes.update_note(
            self._conn,
            note_id,
            title=title,
            content=content,
            tags=tags,
            pinned=pinned,
            source_links=source_links,
            project_id=project_id,
            metadata=metadata,
            fts_enabled=self._fts_enabled,
        )
        if content is not None:
            title_index = _notes.get_all_notes_index(self._conn)
            _bl.update_backlinks_for_note(
                self._conn, note_id, content, title_index
            )
        self._conn.commit()
        note["backlinks"] = _bl.get_backlinks_for(self._conn, note_id)
        return note

    def delete_note(self, note_id: str) -> bool:
        deleted = _notes.delete_note(
            self._conn, note_id, fts_enabled=self._fts_enabled
        )
        self._conn.commit()
        return deleted

    def pin_note(self, note_id: str, pinned: bool) -> dict[str, Any]:
        note = _notes.pin_note(self._conn, note_id, pinned)
        self._conn.commit()
        return note

    # ------------------------------------------------------------------
    # Listing & search
    # ------------------------------------------------------------------

    def list_notes(
        self,
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
        return _notes.list_notes(
            self._conn,
            note_type=note_type,
            tags=tags,
            pinned=pinned,
            project_id=project_id,
            date=date,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    def search_notes(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return self.list_notes(limit=limit)
        return _notes.search_notes_fts(
            self._conn,
            query,
            limit=limit,
            fts_enabled=self._fts_enabled,
        )

    def count(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM vault_notes"
        ).fetchone()
        return int(row["cnt"])

    # ------------------------------------------------------------------
    # Daily notes
    # ------------------------------------------------------------------

    def get_daily_note(self, date: str | None = None) -> dict[str, Any]:
        """Return today's (or *date*'s) daily note, creating it if absent."""
        note = _dn.get_or_create_daily_note(
            self._conn, date, fts_enabled=self._fts_enabled
        )
        note["backlinks"] = _bl.get_backlinks_for(self._conn, note["id"])
        return note

    def list_daily_notes(self, *, limit: int = 30) -> list[dict[str, Any]]:
        return _dn.list_daily_notes(self._conn, limit=limit)

    # ------------------------------------------------------------------
    # Backlinks
    # ------------------------------------------------------------------

    def get_backlinks(self, note_id: str) -> list[dict[str, Any]]:
        return _bl.get_backlinks_for(self._conn, note_id)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def all_tags(self) -> list[dict[str, Any]]:
        return _tags.list_all_tags(self._conn)

    def notes_by_tag(self, tag: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return _tags.get_notes_by_tag(self._conn, tag, limit=limit)

    # ------------------------------------------------------------------
    # Markdown export
    # ------------------------------------------------------------------

    def export_note_markdown(self, note_id: str) -> str:
        """Return the markdown string for a single note."""
        note = self.get_note(note_id)
        return note_to_markdown(note)

    def export_vault(
        self,
        output_dir: str | Path | None = None,
        *,
        note_type: str | None = None,
    ) -> dict[str, Any]:
        """Export vault notes to *output_dir* as Obsidian-compatible .md files.

        Returns a summary dict with ``exported_count``, ``output_directory``,
        and ``files``.
        """
        if output_dir is None:
            output_dir = Path.home() / ".openjarvis" / "vault_export"
        out = Path(output_dir).expanduser()
        notes = self.list_notes(note_type=note_type, limit=1000)
        written = export_vault_notes(notes, out)
        return {
            "exported_count": len(written),
            "output_directory": str(out),
            "files": [str(p) for p in written],
            "local_only": True,
        }

    # ------------------------------------------------------------------
    # Integration hooks
    # ------------------------------------------------------------------

    def from_memory(
        self,
        memory_id: str,
        memory_service: Any,
    ) -> dict[str, Any]:
        """Import a MemoryService record as a vault note.

        Does **not** modify the memory DB — it only reads from it.
        """
        try:
            mem = memory_service.get_memory(memory_id)
        except KeyError as exc:
            raise KeyError(f"memory {memory_id} not found") from exc

        title = (
            mem.get("metadata", {}).get("title")
            or mem["content"][:60].split("\n")[0].strip()
            or "Imported memory"
        )
        source_links = []
        src = mem.get("source")
        if src and src.get("url"):
            source_links.append(
                {"title": src.get("title") or src["url"], "url": src["url"]}
            )
        return self.create_note(
            title=title,
            content=mem["content"],
            note_type=mem.get("memory_type") or "note",
            tags=mem.get("tags") or [],
            pinned=bool(mem.get("pinned")),
            source_links=source_links,
            metadata={"imported_from_memory": memory_id},
        )

    def link_to_research(
        self,
        note_id: str,
        research_summary: str,
    ) -> dict[str, Any]:
        """Append *research_summary* to an existing note's metadata and content."""
        note = self.get_note(note_id)
        new_content = (
            note["content"].rstrip("\n")
            + "\n\n## Research\n\n"
            + research_summary
        )
        meta = dict(note.get("metadata") or {})
        meta["has_research"] = True
        return self.update_note(note_id, content=new_content, metadata=meta)


__all__ = ["KnowledgeVaultService"]
