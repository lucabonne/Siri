"""Read-only local context routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, Request

from openjarvis.context import ContextLayer

context_router = APIRouter(prefix="/v1/context", tags=["context"])


def _privacy_mode(request: Request) -> bool:
    registry = getattr(request.app.state, "mode_registry", None)
    if registry is None:
        return False
    try:
        return registry.get_active_mode().mode.id == "privacy"
    except Exception:
        return False


def _layer(cwd: str | None) -> ContextLayer:
    return ContextLayer(cwd=Path(cwd).expanduser() if cwd else None)


@context_router.get("/desktop")
async def get_desktop_context(request: Request, cwd: str | None = Query(default=None)):
    """Return passive desktop context collected locally."""
    context = _layer(cwd).current_desktop_context(
        privacy_mode=_privacy_mode(request)
    )
    return context.to_dict()


@context_router.get("/project")
async def get_project_context(cwd: str | None = Query(default=None)):
    """Return passive project context for the current working directory."""
    return _layer(cwd).current_project_context().to_dict()


@context_router.get("/repo")
async def get_repo_context(cwd: str | None = Query(default=None)):
    """Return lightweight repository inventory and summary metadata."""
    return _layer(cwd).repo_index().to_dict()
