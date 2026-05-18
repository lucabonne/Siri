"""Autonomous Research Mode Phase 1 API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from openjarvis.research import ResearchService
from openjarvis.server.morning_briefing_routes import _service as morning_service
from openjarvis.server.worldmonitor_routes import get_worldmonitor_service

research_router = APIRouter(prefix="/v1/research", tags=["research"])


class StartResearchRequest(BaseModel):
    question: str
    sources: list[dict[str, Any]] = []
    allow_external_search: bool = False
    max_sources: int = 8


def _privacy_mode(request: Request) -> bool:
    registry = getattr(request.app.state, "mode_registry", None)
    if registry is None:
        return False
    try:
        return registry.get_active_mode().mode.id == "privacy"
    except Exception:
        return False


def _active_mode_id(request: Request) -> str:
    registry = getattr(request.app.state, "mode_registry", None)
    if registry is None:
        return ""
    try:
        return registry.get_active_mode().active_mode_id
    except Exception:
        return ""


def _workspace_agent_id(request: Request) -> str:
    value = getattr(request.app.state, "active_workspace_agent_id", "")
    if value:
        return str(value)
    registry = getattr(request.app.state, "agent_workspace_registry", None)
    if registry is None:
        return ""
    try:
        return registry.get_active_agent().active_agent_id
    except Exception:
        return ""


def _structured_memory_service(request: Request) -> Any:
    service = getattr(request.app.state, "structured_memory_service", None)
    if service is not None:
        return service
    try:
        from openjarvis.memory import MemoryService

        config = getattr(request.app.state, "config", None)
        db_path = None
        if config is not None:
            db_path = getattr(getattr(config, "memory", None), "db_path", None)
        service = MemoryService(db_path=db_path)
        request.app.state.structured_memory_service = service
        return service
    except Exception:
        return None


def get_research_service(request: Request) -> ResearchService:
    service = getattr(request.app.state, "research_service", None)
    if service is None:
        config = getattr(request.app.state, "config", None)
        db_path = None
        if config is not None:
            db_path = getattr(getattr(config, "memory", None), "db_path", None)
        service = ResearchService(
            db_path=db_path,
            memory_service=_structured_memory_service(request),
            worldmonitor_service=get_worldmonitor_service(request),
            morning_briefing_service=morning_service(request),
        )
        request.app.state.research_service = service
    return service


@research_router.post("/start")
async def start_research(req: StartResearchRequest, request: Request):
    """Run a synchronous local-first research workflow."""

    privacy = _privacy_mode(request)
    try:
        session = get_research_service(request).start_research(
            req.question,
            seed_sources=req.sources,
            allow_external_search=bool(req.allow_external_search and not privacy),
            privacy_mode=privacy,
            active_mode_id=_active_mode_id(request),
            workspace_agent_id=_workspace_agent_id(request),
            max_sources=req.max_sources,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"research": session.to_dict()}


@research_router.get("")
async def list_research(request: Request, limit: int = Query(default=20, ge=1, le=100)):
    """List recent research sessions."""

    sessions = get_research_service(request).list_sessions(limit=limit)
    return {
        "research": [session.to_dict() for session in sessions],
        "privacy_mode": _privacy_mode(request),
        "passive_only": True,
        "local_only": True,
    }


@research_router.get("/{research_id}/status")
async def research_status(research_id: str, request: Request):
    """Return research session status."""

    try:
        return get_research_service(request).status(research_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Research not found") from exc


@research_router.get("/{research_id}/report")
async def research_report(research_id: str, request: Request):
    """Return the generated report."""

    try:
        session = get_research_service(request).get_session(research_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Research not found") from exc
    return {
        "report": session.report.to_dict() if session.report else None,
        "privacy_mode": session.privacy_mode,
        "local_only": session.local_only,
        "passive_only": session.passive_only,
    }


@research_router.get("/{research_id}/citations")
async def research_citations(research_id: str, request: Request):
    """Return citations for a research report."""

    try:
        session = get_research_service(request).get_session(research_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Research not found") from exc
    citations = session.report.citations if session.report else []
    return {
        "citations": [citation.to_dict() for citation in citations],
        "sources": [source.to_dict() for source in session.sources],
        "privacy_mode": session.privacy_mode,
    }


@research_router.get("/{research_id}/memory")
async def research_memory_entries(research_id: str, request: Request):
    """Return structured memory entries written by a research run."""

    try:
        entries = get_research_service(request).memory_entries(research_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Research not found") from exc
    return {"memories": entries, "privacy_mode": _privacy_mode(request)}


__all__ = ["get_research_service", "research_router"]
