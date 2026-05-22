"""FastAPI routes for the Siri Knowledge Vault.

All endpoints are local-only. The vault service is lazily initialised on
``app.state`` so it can be shared across requests without re-opening the DB.

Prefix: /v1/knowledge-vault
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

knowledge_vault_router = APIRouter(
    prefix="/v1/knowledge-vault",
    tags=["knowledge-vault"],
)


# ---------------------------------------------------------------------------
# Service accessor
# ---------------------------------------------------------------------------

def _get_vault(request: Request):
    """Return or lazily create the shared KnowledgeVaultService."""
    svc = getattr(request.app.state, "knowledge_vault_service", None)
    if svc is None:
        try:
            from openjarvis.knowledge_vault import KnowledgeVaultService

            svc = KnowledgeVaultService()
            request.app.state.knowledge_vault_service = svc
        except Exception as exc:
            logger.warning("Failed to initialise KnowledgeVaultService: %s", exc)
            raise HTTPException(
                status_code=503, detail="Knowledge Vault service unavailable"
            ) from exc
    return svc


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateNoteBody(BaseModel):
    title: str
    content: str = ""
    note_type: str = "note"
    tags: list[str] = []
    pinned: bool = False
    source_links: list[dict[str, Any]] = []
    project_id: Optional[str] = None
    date: Optional[str] = None
    metadata: dict[str, Any] = {}


class UpdateNoteBody(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    pinned: Optional[bool] = None
    source_links: Optional[list[dict[str, Any]]] = None
    project_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class PinBody(BaseModel):
    pinned: bool


class CreateDailyNoteBody(BaseModel):
    date: Optional[str] = None
    content: str = ""
    tags: list[str] = []
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Note endpoints
# ---------------------------------------------------------------------------

@knowledge_vault_router.get("/notes")
async def list_notes(
    request: Request,
    note_type: Optional[str] = None,
    tag: Optional[str] = Query(default=None),
    pinned: Optional[bool] = None,
    project_id: Optional[str] = None,
    date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List vault notes with optional filters."""
    svc = _get_vault(request)
    try:
        tags_filter = [tag] if tag else None
        notes = svc.list_notes(
            note_type=note_type,
            tags=tags_filter,
            pinned=pinned,
            project_id=project_id,
            date=date,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        return {"notes": notes, "count": len(notes)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@knowledge_vault_router.post("/notes")
async def create_note(body: CreateNoteBody, request: Request):
    """Create a new vault note."""
    svc = _get_vault(request)
    try:
        note = svc.create_note(
            body.title,
            content=body.content,
            note_type=body.note_type,
            tags=body.tags,
            pinned=body.pinned,
            source_links=body.source_links,
            project_id=body.project_id,
            date=body.date,
            metadata=body.metadata,
        )
        return {"note": note}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@knowledge_vault_router.get("/notes/{note_id}")
async def get_note(note_id: str, request: Request):
    """Get a vault note by ID (includes backlinks)."""
    svc = _get_vault(request)
    try:
        return {"note": svc.get_note(note_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Note not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@knowledge_vault_router.patch("/notes/{note_id}")
async def update_note(note_id: str, body: UpdateNoteBody, request: Request):
    """Update a vault note (partial update)."""
    svc = _get_vault(request)
    try:
        note = svc.update_note(
            note_id,
            title=body.title,
            content=body.content,
            tags=body.tags,
            pinned=body.pinned,
            source_links=body.source_links,
            project_id=body.project_id,
            metadata=body.metadata,
        )
        return {"note": note}
    except KeyError:
        raise HTTPException(status_code=404, detail="Note not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@knowledge_vault_router.delete("/notes/{note_id}")
async def delete_note(note_id: str, request: Request):
    """Delete a vault note."""
    svc = _get_vault(request)
    try:
        deleted = svc.delete_note(note_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"status": "deleted", "id": note_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@knowledge_vault_router.post("/notes/{note_id}/pin")
async def pin_note(note_id: str, body: PinBody, request: Request):
    """Pin or unpin a vault note."""
    svc = _get_vault(request)
    try:
        note = svc.pin_note(note_id, body.pinned)
        return {"note": note}
    except KeyError:
        raise HTTPException(status_code=404, detail="Note not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Backlinks
# ---------------------------------------------------------------------------

@knowledge_vault_router.get("/notes/{note_id}/backlinks")
async def get_backlinks(note_id: str, request: Request):
    """Return all notes that link to this note."""
    svc = _get_vault(request)
    try:
        return {"backlinks": svc.get_backlinks(note_id), "note_id": note_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------

@knowledge_vault_router.get("/notes/{note_id}/export")
async def export_note_markdown(note_id: str, request: Request):
    """Return the Obsidian-compatible markdown for a single note."""
    svc = _get_vault(request)
    try:
        md = svc.export_note_markdown(note_id)
        return {"markdown": md, "note_id": note_id}
    except KeyError:
        raise HTTPException(status_code=404, detail="Note not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@knowledge_vault_router.get("/export")
async def export_vault(
    request: Request,
    note_type: Optional[str] = None,
    output_dir: Optional[str] = None,
):
    """Export all vault notes to the local filesystem as Obsidian markdown.

    Returns the export summary (count, output directory, file list).
    This is a local-only operation — no files leave the machine.
    """
    svc = _get_vault(request)
    try:
        result = svc.export_vault(output_dir=output_dir, note_type=note_type)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@knowledge_vault_router.get("/search")
async def search_notes(
    request: Request,
    q: str = Query(..., description="Search query"),
    limit: int = 20,
):
    """Full-text search across vault notes."""
    svc = _get_vault(request)
    try:
        results = svc.search_notes(q, limit=limit)
        return {"results": results, "query": q}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@knowledge_vault_router.get("/tags")
async def list_tags(request: Request):
    """List all tags with occurrence counts."""
    svc = _get_vault(request)
    try:
        return {"tags": svc.all_tags()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Daily note
# ---------------------------------------------------------------------------

@knowledge_vault_router.get("/daily")
async def get_daily_note(
    request: Request,
    date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
):
    """Return today's (or the given date's) daily note, creating it if absent."""
    svc = _get_vault(request)
    try:
        note = svc.get_daily_note(date)
        return {"note": note}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@knowledge_vault_router.post("/daily")
async def create_daily_note(body: CreateDailyNoteBody, request: Request):
    """Explicitly create or return a daily note for a specific date."""
    svc = _get_vault(request)
    try:
        note = svc.get_daily_note(body.date)
        if body.content:
            note = svc.update_note(note["id"], content=body.content, tags=body.tags)
        return {"note": note}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Status / health
# ---------------------------------------------------------------------------

@knowledge_vault_router.get("/status")
async def vault_status(request: Request):
    """Return Knowledge Vault health and note count."""
    svc = _get_vault(request)
    try:
        return {
            "status": "ok",
            "note_count": svc.count(),
            "db_path": str(svc.db_path),
            "local_only": True,
            "cloud_sync": False,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


__all__ = ["knowledge_vault_router"]
