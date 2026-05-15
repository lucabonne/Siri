"""WorldMonitor integration API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from openjarvis.worldmonitor import WorldMonitorService

worldmonitor_router = APIRouter(prefix="/v1/worldmonitor", tags=["worldmonitor"])


class WorldMonitorSyncRequest(BaseModel):
    pass


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


def get_worldmonitor_service(request: Request) -> WorldMonitorService:
    service = getattr(request.app.state, "worldmonitor_service", None)
    if service is None:
        config = getattr(request.app.state, "config", None)
        db_path = None
        if config is not None:
            db_path = getattr(getattr(config, "memory", None), "db_path", None)
        service = WorldMonitorService(
            db_path=db_path,
            memory_service=_structured_memory_service(request),
        )
        request.app.state.worldmonitor_service = service
    return service


@worldmonitor_router.get("/status")
async def worldmonitor_status(request: Request):
    """Return local WorldMonitor detection and cache status."""

    return get_worldmonitor_service(request).status(
        privacy_mode=_privacy_mode(request)
    ).to_dict()


@worldmonitor_router.get("/events")
async def imported_events(
    request: Request,
    category: str | None = Query(default=None),
    map_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Return cached imported WorldMonitor events."""

    events = get_worldmonitor_service(request).imported_events(
        category=category,
        map_only=map_only,
        limit=limit,
    )
    return {
        "events": [event.to_dict() for event in events],
        "privacy_mode": _privacy_mode(request),
        "cached": True,
    }


@worldmonitor_router.get("/briefing-data")
async def imported_briefing_data(
    request: Request,
    limit: int = Query(default=40, ge=1, le=200),
):
    """Return cached WorldMonitor data shaped for Morning Briefing."""

    return get_worldmonitor_service(request).briefing_data(limit=limit).to_dict()


@worldmonitor_router.post("/sync")
async def sync_worldmonitor(_: WorldMonitorSyncRequest, request: Request):
    """Explicitly sync from a local WorldMonitor instance."""

    return get_worldmonitor_service(request).sync(
        privacy_mode=_privacy_mode(request)
    ).to_dict()


@worldmonitor_router.get("/sync-status")
async def sync_status(request: Request):
    """Return latest explicit WorldMonitor sync status."""

    latest = get_worldmonitor_service(request).latest_sync()
    return {
        "sync": latest.to_dict() if latest else None,
        "privacy_mode": _privacy_mode(request),
        "passive_only": True,
        "local_only": True,
    }


__all__ = ["get_worldmonitor_service", "worldmonitor_router"]
