"""Markdown export for the Siri Knowledge Vault.

Exports notes in Obsidian-compatible format:

    ---
    title: My Note
    tags: [python, research]
    created: 2025-01-15T10:30:00Z
    updated: 2025-01-15T10:30:00Z
    type: research
    pinned: false
    sources:
      - title: Some Article
        url: https://example.com
    ---

    Note body content…

Wiki-links (``[[Title]]``) in the body are preserved as-is so Obsidian can
resolve them natively.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _yaml_str(value: str) -> str:
    """Escape a YAML string value (minimal, single-quoted if needed)."""
    if any(c in value for c in (":", "#", "[", "]", "{", "}", ",", "\n", "'")):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return value


def note_to_markdown(note: dict[str, Any]) -> str:
    """Convert a vault note dict to an Obsidian-compatible markdown string."""
    lines: list[str] = ["---"]

    title = note.get("title") or ""
    lines.append(f"title: {_yaml_str(title)}")

    tags: list[str] = note.get("tags") or []
    if tags:
        tag_list = ", ".join(tags)
        lines.append(f"tags: [{tag_list}]")
    else:
        lines.append("tags: []")

    note_type = note.get("note_type") or "note"
    lines.append(f"type: {note_type}")

    if note.get("date"):
        lines.append(f"date: {note['date']}")

    if note.get("pinned"):
        lines.append("pinned: true")
    else:
        lines.append("pinned: false")

    lines.append(f"created: {note.get('created_at', '')}")
    lines.append(f"updated: {note.get('updated_at', '')}")

    source_links: list[dict] = note.get("source_links") or []
    if source_links:
        lines.append("sources:")
        for sl in source_links:
            sl_title = sl.get("title") or sl.get("url") or ""
            sl_url = sl.get("url") or ""
            lines.append(f"  - title: {_yaml_str(sl_title)}")
            lines.append(f"    url: {sl_url}")

    if note.get("project_id"):
        lines.append(f"project: {note['project_id']}")

    lines.append("---")
    lines.append("")

    content: str = note.get("content") or ""
    lines.append(content)

    if not content.endswith("\n"):
        lines.append("")

    return "\n".join(lines)


def safe_filename(title: str, note_id: str) -> str:
    """Derive a safe filesystem filename from a note title."""
    import re

    safe = re.sub(r'[\\/:*?"<>|]', "_", title)
    safe = safe.strip(". ")
    safe = safe[:80] if len(safe) > 80 else safe
    if not safe:
        safe = note_id[:8]
    return f"{safe}.md"


def export_note_to_file(
    note: dict[str, Any],
    output_dir: Path,
) -> Path:
    """Write a single note to *output_dir* and return the file path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fname = safe_filename(note.get("title") or "", note.get("id") or "unknown")
    # For daily notes use the date as filename if available
    if note.get("note_type") == "daily" and note.get("date"):
        fname = f"{note['date']}.md"
    path = output_dir / fname
    path.write_text(note_to_markdown(note), encoding="utf-8")
    return path


def export_vault_notes(
    notes: list[dict[str, Any]],
    output_dir: Path,
) -> list[Path]:
    """Write all *notes* to *output_dir*, returning written file paths."""
    written: list[Path] = []
    for note in notes:
        written.append(export_note_to_file(note, output_dir))
    return written


def export_daily_notes_subdirectory(
    notes: list[dict[str, Any]],
    output_dir: Path,
) -> list[Path]:
    """Write daily notes to ``output_dir/daily/``."""
    daily_dir = output_dir / "daily"
    written: list[Path] = []
    for note in notes:
        written.append(export_note_to_file(note, daily_dir))
    return written


__all__ = [
    "note_to_markdown",
    "safe_filename",
    "export_note_to_file",
    "export_vault_notes",
    "export_daily_notes_subdirectory",
]
