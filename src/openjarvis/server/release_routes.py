"""Release hardening API routes for local Siri release candidates."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from openjarvis.release import ReleaseHardeningService

release_router = APIRouter(prefix="/v1/release", tags=["release"])


class RecoveryRunRequest(BaseModel):
    action: str


def get_release_hardening_service(request: Request) -> ReleaseHardeningService:
    service = getattr(request.app.state, "release_hardening_service", None)
    if service is None:
        service = ReleaseHardeningService(
            packaging_service=getattr(request.app.state, "packaging_service", None)
        )
        request.app.state.release_hardening_service = service
    return service


@release_router.get("/health")
async def release_health(request: Request):
    """Return local release health checks."""

    return {
        "checks": [
            check.to_dict()
            for check in get_release_hardening_service(request).health_checks(
                app_state=request.app.state,
            )
        ],
        "local_only": True,
        "telemetry_enabled": False,
    }


@release_router.get("/diagnostics")
async def release_diagnostics(request: Request):
    """Return startup diagnostics for first local release readiness."""

    return {
        "diagnostics": [
            item.to_dict()
            for item in get_release_hardening_service(request).startup_diagnostics(
                app_state=request.app.state,
            )
        ],
        "local_only": True,
        "telemetry_enabled": False,
    }


@release_router.get("/recovery")
async def release_recovery_actions(request: Request):
    """Return local recovery helpers available to Mission Control."""

    return {
        "actions": [
            action.to_dict()
            for action in get_release_hardening_service(request).recovery_actions()
        ],
        "local_only": True,
        "telemetry_enabled": False,
    }


@release_router.post("/recovery/run")
async def run_release_recovery_action(body: RecoveryRunRequest, request: Request):
    """Run one explicit local recovery helper."""

    return (
        get_release_hardening_service(request)
        .run_recovery_action(body.action)
        .to_dict()
    )


@release_router.get("/report")
async def release_report(request: Request):
    """Return installed components, enabled modules, warnings, and score."""

    return (
        get_release_hardening_service(request)
        .release_report()
        .to_dict()
    )


@release_router.get("/mission-control")
async def release_mission_control(request: Request):
    """Return the complete local release readiness panel payload."""

    return (
        get_release_hardening_service(request)
        .snapshot(app_state=request.app.state)
        .to_dict()
    )


__all__ = ["get_release_hardening_service", "release_router"]
