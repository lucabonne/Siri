"""Local packaging and app bundle API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from openjarvis.packaging import PackagingService

packaging_router = APIRouter(prefix="/v1/packaging", tags=["packaging"])


class PackageBuildRequest(BaseModel):
    output_dir: str = ""


class PackageInstallRequest(BaseModel):
    destination: str = "user"
    install_launch_agent: bool = True
    output_dir: str = ""


class PackageUninstallRequest(BaseModel):
    remove_launch_agent: bool = True
    destinations: list[str] | None = None


def get_packaging_service(request: Request) -> PackagingService:
    service = getattr(request.app.state, "packaging_service", None)
    if service is None:
        service = PackagingService()
        request.app.state.packaging_service = service
    return service


@packaging_router.get("/status")
async def packaging_status(request: Request):
    """Return Siri package status and install readiness for Mission Control."""

    return get_packaging_service(request).status(
        integrations=_integration_snapshot(request),
    ).to_dict()


@packaging_router.get("/diagnostics")
async def packaging_diagnostics(request: Request):
    """Return local app bundle and launcher diagnostics."""

    return get_packaging_service(request).diagnostics(
        launcher_state=_desktop_launcher_state(request),
        integrations=_integration_snapshot(request),
    )


@packaging_router.get("/release-diagnostics")
async def packaging_release_diagnostics(request: Request):
    """Return local installer and release diagnostics."""

    return get_packaging_service(request).release_diagnostics()


@packaging_router.get("/launcher/state")
async def packaging_launcher_state(request: Request):
    """Return local packaging launcher state."""

    return get_packaging_service(request).launcher_state(
        desktop_launcher_state=_desktop_launcher_state(request),
    )


@packaging_router.post("/build")
async def build_app_bundle(body: PackageBuildRequest, request: Request):
    """Generate the lightweight local macOS .app bundle."""

    return get_packaging_service(request).build_app_bundle(
        output_dir=body.output_dir or None,
    )


@packaging_router.post("/install")
async def install_app_bundle(body: PackageInstallRequest, request: Request):
    """Install or update the local macOS Siri.app bundle."""

    return get_packaging_service(request).install_app_bundle(
        destination=body.destination,
        install_launch_agent=body.install_launch_agent,
        output_dir=body.output_dir or None,
    )


@packaging_router.post("/uninstall")
async def uninstall_app_bundle(body: PackageUninstallRequest, request: Request):
    """Remove local Siri.app bundle installs and optionally the LaunchAgent."""

    return get_packaging_service(request).uninstall_app_bundle(
        remove_launch_agent=body.remove_launch_agent,
        destinations=body.destinations,
    )


def _desktop_launcher_state(request: Request) -> dict[str, Any]:
    service = getattr(request.app.state, "desktop_service", None)
    if service is None:
        return {}
    try:
        return service.launcher_status().to_dict()
    except Exception:
        return {}


def _integration_snapshot(request: Request) -> dict[str, Any]:
    desktop = getattr(request.app.state, "desktop_service", None)
    startup = getattr(request.app.state, "startup_service", None)
    notifications = getattr(request.app.state, "notification_service", None)
    integrations: dict[str, Any] = {
        "desktop_wrapper": {
            "available": desktop is not None,
            "local_only": True,
            "telemetry_enabled": False,
        },
        "tray": {
            "available": False,
            "local_only": True,
            "telemetry_enabled": False,
        },
        "startup_scheduler": {
            "available": startup is not None,
            "local_only": True,
            "telemetry_enabled": False,
        },
        "notifications": {
            "available": notifications is not None,
            "local_only": True,
            "telemetry_enabled": False,
        },
    }
    if desktop is not None:
        try:
            integrations["tray"] = desktop.tray_state().to_dict()
        except Exception:
            pass
    if startup is not None:
        try:
            status = startup.status()
            integrations["startup_scheduler"] = {
                "available": True,
                "launch_at_login": status.launch_at_login,
                "scheduler": status.scheduler.to_dict(),
                "local_only": True,
                "telemetry_enabled": False,
            }
        except Exception:
            pass
    if notifications is not None:
        try:
            integrations["notifications"] = notifications.queue_status()
        except Exception:
            pass
    return integrations


__all__ = ["get_packaging_service", "packaging_router"]
