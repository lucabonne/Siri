"""Pydantic models for the Siri Knowledge Vault.

These models are the public contract between the vault service layer and
callers (API routes, tests, frontend).  The vault never modifies the
existing ``memories`` table; it has its own schema.
"""

from __future__ import annotations

import uuid
from datetime import date as _date
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class NoteType(str, Enum):
    """Supported note categories."""

    note = "note"
    daily = "daily"
    project = "project"
    research = "research"


class SourceLink(BaseModel):
    """A URL with an optional human-readable title."""

    title: str = ""
    url: str


class BacklinkRecord(BaseModel):
    """A directed link from one vault note to another."""

    source_note_id: str
    source_note_title: str
    target_note_id: str
    context_snippet: str = ""
    created_at: str = ""


class KnowledgeNote(BaseModel):
    """Full representation of a vault note."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str = ""
    note_type: NoteType = NoteType.note
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    source_links: list[SourceLink] = Field(default_factory=list)
    backlinks: list[BacklinkRecord] = Field(default_factory=list)
    project_id: Optional[str] = None
    # ISO date string (YYYY-MM-DD) used by daily notes
    date: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class NoteListItem(BaseModel):
    """Compact note summary for list views."""

    id: str
    title: str
    note_type: NoteType
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    date: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class VaultTag(BaseModel):
    """A tag with its occurrence count across the vault."""

    name: str
    count: int


# ---- Request models ----


class CreateNoteRequest(BaseModel):
    title: str
    content: str = ""
    note_type: NoteType = NoteType.note
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    source_links: list[SourceLink] = Field(default_factory=list)
    project_id: Optional[str] = None
    date: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    pinned: Optional[bool] = None
    source_links: Optional[list[SourceLink]] = None
    project_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class PinNoteRequest(BaseModel):
    pinned: bool


class CreateDailyNoteRequest(BaseModel):
    date: str = Field(
        default_factory=lambda: _date.today().isoformat(),
        description="ISO date string YYYY-MM-DD",
    )
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExportResult(BaseModel):
    """Result of a vault markdown export."""

    exported_count: int
    output_directory: str
    files: list[str] = Field(default_factory=list)
    local_only: bool = True


__all__ = [
    "NoteType",
    "SourceLink",
    "BacklinkRecord",
    "KnowledgeNote",
    "NoteListItem",
    "VaultTag",
    "CreateNoteRequest",
    "UpdateNoteRequest",
    "PinNoteRequest",
    "CreateDailyNoteRequest",
    "ExportResult",
]
