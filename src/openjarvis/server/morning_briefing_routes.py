"""Morning briefing API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from openjarvis.morning_briefing import MorningBriefingService, PrivacyModeError
from openjarvis.server.worldmonitor_routes import get_worldmonitor_service

morning_briefing_router = APIRouter(
    prefix="/v1/morning-briefing",
    tags=["morning-briefing"],
)


class RegenerateBriefingRequest(BaseModel):
    location_name: str = ""
    max_items: int = 12
    persist_memory: bool = True


def _privacy_mode(request: Request) -> bool:
    registry = getattr(request.app.state, "mode_registry", None)
    if registry is None:
        return False
    try:
        return registry.get_active_mode().mode.id == "privacy"
    except Exception:
        return False


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


def _service(request: Request) -> MorningBriefingService:
    service = getattr(request.app.state, "morning_briefing_service", None)
    if service is None:
        config = getattr(request.app.state, "config", None)
        db_path = None
        if config is not None:
            db_path = getattr(getattr(config, "memory", None), "db_path", None)
        service = MorningBriefingService(
            db_path=db_path,
            memory_service=_structured_memory_service(request),
            worldmonitor_service=get_worldmonitor_service(request),
        )
        request.app.state.morning_briefing_service = service
    return service


@morning_briefing_router.get("/latest")
async def latest_briefing(request: Request):
    """Return the latest cached briefing."""

    briefing = _service(request).latest_briefing()
    return {
        "briefing": briefing.to_dict() if briefing else None,
        "privacy_mode": _privacy_mode(request),
        "cached_only": _privacy_mode(request),
    }


@morning_briefing_router.get("")
async def list_briefings(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List cached daily briefings."""

    briefings = _service(request).list_briefings(limit=limit, offset=offset)
    return {
        "briefings": [briefing.to_dict() for briefing in briefings],
        "privacy_mode": _privacy_mode(request),
    }


@morning_briefing_router.get("/world-events")
async def world_events(
    request: Request,
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=250),
):
    """Return geolocated events for Mission Control's world map."""

    events = _service(request).events(
        category=category,
        world_map_only=True,
        limit=limit,
    )
    return {
        "events": [event.to_dict() for event in events],
        "privacy_mode": _privacy_mode(request),
        "cached_only": _privacy_mode(request),
    }


@morning_briefing_router.get("/events")
async def morning_events(
    request: Request,
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=250),
):
    """Return categorized cached events."""

    events = _service(request).events(category=category, limit=limit)
    return {
        "events": [event.to_dict() for event in events],
        "privacy_mode": _privacy_mode(request),
    }


@morning_briefing_router.post("/regenerate")
async def regenerate_briefing(body: RegenerateBriefingRequest, request: Request):
    """Generate a fresh briefing, unless Privacy Mode restricts to cache."""

    privacy = _privacy_mode(request)
    try:
        briefing = _service(request).regenerate_briefing(
            location_name=body.location_name,
            max_items=max(1, min(body.max_items, 50)),
            privacy_mode=privacy,
            persist_memory=body.persist_memory and not privacy,
        )
    except PrivacyModeError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {
        "briefing": briefing.to_dict(),
        "privacy_mode": privacy,
        "cached_only": privacy,
    }


@morning_briefing_router.get("/status")
async def briefing_status(request: Request):
    """Return Morning Briefing subsystem status."""

    privacy = _privacy_mode(request)
    return _service(request).status(privacy_mode=privacy).to_dict()


__all__ = ["morning_briefing_router"]
