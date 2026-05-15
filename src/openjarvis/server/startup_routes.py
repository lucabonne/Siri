"""Startup and passive scheduler API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from openjarvis.morning_briefing import PrivacyModeError
from openjarvis.server.morning_briefing_routes import (
    _privacy_mode,
)
from openjarvis.server.morning_briefing_routes import (
    _service as morning_briefing_service,
)
from openjarvis.startup import StartupService
from openjarvis.startup.service import startup_payload

startup_router = APIRouter(prefix="/v1/startup", tags=["startup"])


class ManualMorningBriefingRequest(BaseModel):
    force: bool = True
    location_name: str = ""
    max_items: int = 12
    persist_memory: bool = True


def get_startup_service(request: Request) -> StartupService:
    service = getattr(request.app.state, "startup_service", None)
    if service is None:
        service = StartupService(
            morning_briefing_service=morning_briefing_service(request),
        )
        request.app.state.startup_service = service
    elif getattr(service, "_morning_briefing_service", None) is None:
        service._morning_briefing_service = morning_briefing_service(request)
    return service


@startup_router.get("/status")
async def startup_status(request: Request):
    """Return combined startup and scheduler status."""

    privacy = _privacy_mode(request)
    return startup_payload(get_startup_service(request).status(privacy_mode=privacy))


@startup_router.get("/scheduler/status")
async def scheduler_status(request: Request):
    """Return passive scheduler status."""

    service = get_startup_service(request)
    return service.status(privacy_mode=_privacy_mode(request)).scheduler.to_dict()


@startup_router.post("/install")
async def install_startup(request: Request):
    """Install Siri's user LaunchAgent for login startup."""

    return startup_payload(get_startup_service(request).install_startup())


@startup_router.post("/remove")
async def remove_startup(request: Request):
    """Remove Siri's user LaunchAgent."""

    return startup_payload(get_startup_service(request).remove_startup())


@startup_router.post("/morning-briefing")
async def trigger_morning_briefing(
    body: ManualMorningBriefingRequest,
    request: Request,
):
    """Manually trigger a morning briefing through the startup subsystem."""

    privacy = _privacy_mode(request)
    try:
        result = get_startup_service(request).trigger_morning_briefing(
            force=body.force,
            privacy_mode=privacy,
            source="manual",
            location_name=body.location_name,
            max_items=body.max_items,
            persist_memory=body.persist_memory,
        )
    except PrivacyModeError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {
        **result.to_dict(),
        "privacy_mode": privacy,
        "local_only": True,
        "external_startup_telemetry": False,
    }


__all__ = ["get_startup_service", "startup_router"]
