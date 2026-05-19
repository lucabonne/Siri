"""FastAPI routes for local desktop integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from openjarvis.desktop import DesktopService

desktop_router = APIRouter(prefix="/v1/desktop", tags=["desktop"])


class LaunchAppRequest(BaseModel):
    app_name: str
    requested_by: str = "user"


class LaunchWorkspaceRequest(BaseModel):
    path: str
    app_name: str = ""
    coding_environment: str = ""
    requested_by: str = "user"


class TrayActionRequest(BaseModel):
    requested_by: str = "user"
    cwd: str = ""


class DesktopNotificationRequest(BaseModel):
    kind: str
    title: str
    body: str = ""
    user_triggered: bool = True
    delivered: bool = False


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


def get_desktop_service(request: Request) -> DesktopService:
    """Return the app-level desktop service, creating one lazily."""
    service = getattr(request.app.state, "desktop_service", None)
    if service is not None:
        _attach_runtime_integrations(service, request)
        return service

    from openjarvis.coding_assistant import CodingAssistantService
    from openjarvis.context.terminal import TerminalContextStore
    from openjarvis.modes import ModeRegistry
    from openjarvis.repo_index import RepoIndexService
    from openjarvis.security.permissions import PermissionMiddleware
    from openjarvis.server.workflow_routes import get_workflow_service

    mode_registry = getattr(request.app.state, "mode_registry", None)
    if mode_registry is None:
        mode_registry = ModeRegistry()
        request.app.state.mode_registry = mode_registry

    memory_service = _structured_memory_service(request)
    repo_service = getattr(request.app.state, "repo_index_service", None)
    if repo_service is None:
        repo_service = RepoIndexService(memory_service=memory_service)
        request.app.state.repo_index_service = repo_service

    terminal_store = getattr(request.app.state, "terminal_context_store", None)
    if terminal_store is None:
        terminal_store = TerminalContextStore()
        request.app.state.terminal_context_store = terminal_store

    permission = getattr(request.app.state, "_permission_middleware", None)
    if permission is None:
        permission = PermissionMiddleware(mode_registry=mode_registry)
        request.app.state._permission_middleware = permission

    coding = getattr(request.app.state, "coding_assistant_service", None)
    if coding is None:
        coding = CodingAssistantService(
            repo_index_service=repo_service,
            terminal_store=terminal_store,
            memory_service=memory_service,
            permission_middleware=permission,
            agent_workspace_registry=getattr(
                request.app.state,
                "agent_workspace_registry",
                None,
            ),
        )
        request.app.state.coding_assistant_service = coding

    workflow_service = getattr(request.app.state, "workflow_service", None)
    if workflow_service is None:
        try:
            workflow_service = get_workflow_service(request)
        except Exception:
            workflow_service = None

    service = DesktopService(
        memory_service=memory_service,
        workflow_service=workflow_service,
        startup_service=_startup_service(request),
        voice_trigger_service=getattr(request.app.state, "hotkey_service", None),
        tts_service=getattr(request.app.state, "tts_service", None),
        permission_middleware=permission,
        mcp_server=getattr(request.app.state, "mcp_server", None),
        mcp_clients=getattr(request.app.state, "_mcp_clients", []),
        mcp_tools_cache=getattr(request.app.state, "_mcp_tools_cache", None),
        mode_registry=mode_registry,
        coding_assistant=coding,
    )
    request.app.state.desktop_service = service
    return service


def _startup_service(request: Request) -> Any:
    try:
        from openjarvis.server.startup_routes import get_startup_service

        return get_startup_service(request)
    except Exception:
        return getattr(request.app.state, "startup_service", None)


def _attach_runtime_integrations(service: DesktopService, request: Request) -> None:
    if getattr(service, "startup_service", None) is None:
        service.startup_service = _startup_service(request)
    if getattr(service, "workflow_service", None) is None:
        service.workflow_service = getattr(request.app.state, "workflow_service", None)
    if getattr(service, "voice_trigger_service", None) is None:
        service.voice_trigger_service = getattr(
            request.app.state,
            "hotkey_service",
            None,
        )
    if getattr(service, "tts_service", None) is None:
        service.tts_service = getattr(request.app.state, "tts_service", None)
    if getattr(service, "permission_middleware", None) is None:
        service.permission_middleware = getattr(
            request.app.state,
            "permission_middleware",
            getattr(request.app.state, "_permission_middleware", None),
        )
    service.mcp_server = getattr(request.app.state, "mcp_server", None)
    service.mcp_clients = list(getattr(request.app.state, "_mcp_clients", []))
    service.mcp_tools_cache = getattr(request.app.state, "_mcp_tools_cache", None)


@desktop_router.get("/status")
async def desktop_status(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return passive local desktop status for Mission Control."""
    return (
        get_desktop_service(request)
        .status(
            cwd=Path(cwd).expanduser() if cwd else None,
            privacy_mode=_privacy_mode(request),
        )
        .to_dict()
    )


@desktop_router.get("/active-app")
async def active_app(request: Request):
    """Return the current foreground app and window metadata."""
    return get_desktop_service(request).active_app(privacy_mode=_privacy_mode(request))


@desktop_router.get("/open-apps")
async def open_apps(request: Request):
    """Return currently open local applications."""
    return get_desktop_service(request).open_apps(privacy_mode=_privacy_mode(request))


@desktop_router.get("/tray")
async def tray_status(request: Request):
    """Return passive menu bar state for a native shell."""

    return get_desktop_service(request).tray_state().to_dict()


@desktop_router.post("/tray/{action_id}")
async def run_tray_action(
    action_id: str,
    body: TrayActionRequest,
    request: Request,
):
    """Run one explicit user-triggered menu bar action."""

    return get_desktop_service(request).handle_tray_action(
        action_id,
        cwd=Path(body.cwd).expanduser() if body.cwd else None,
        requested_by=body.requested_by,
        privacy_mode=_privacy_mode(request),
    )


@desktop_router.get("/notifications")
async def notification_status(request: Request):
    """Return lightweight local notification state."""

    return get_desktop_service(request).notification_center.state().to_dict()


@desktop_router.post("/notifications")
async def create_notification(body: DesktopNotificationRequest, request: Request):
    """Record a user-triggered local desktop notification."""

    notification = get_desktop_service(request).notify(
        body.kind,
        body.title,
        body.body,
        user_triggered=body.user_triggered,
        delivered=body.delivered,
    )
    return {"notification": notification.to_dict()}


@desktop_router.get("/launcher/status")
async def launcher_status(
    request: Request,
    health: bool = Query(default=False),
    diagnostics: bool = Query(default=False),
):
    """Return local backend/frontend launcher status."""

    return get_desktop_service(request).launcher_status(
        run_health_checks=health,
        run_startup_diagnostics=diagnostics,
    ).to_dict()


@desktop_router.post("/launcher/start-backend")
async def start_backend(request: Request):
    """Start the local backend from an explicit launcher request."""

    return get_desktop_service(request).start_backend().to_dict()


@desktop_router.post("/launcher/start-frontend")
async def start_frontend(request: Request):
    """Start the local frontend from an explicit launcher request."""

    return get_desktop_service(request).start_frontend().to_dict()


@desktop_router.post("/launcher/restart")
async def restart_launcher(request: Request):
    """Restart local backend and frontend helper processes."""

    return get_desktop_service(request).restart_launcher().to_dict()


@desktop_router.post("/launcher/restart-backend")
async def restart_backend(request: Request):
    """Restart the local backend helper process."""

    return get_desktop_service(request).restart_backend().to_dict()


@desktop_router.post("/launcher/restart-frontend")
async def restart_frontend(request: Request):
    """Restart the local frontend helper process."""

    return get_desktop_service(request).restart_frontend().to_dict()


@desktop_router.post("/launch-app")
async def launch_app(body: LaunchAppRequest, request: Request):
    """Open a local desktop app on explicit user request."""
    result = get_desktop_service(request).launch_app(
        body.app_name,
        requested_by=body.requested_by,
        privacy_mode=_privacy_mode(request),
    )
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.to_dict())
    return {"launch": result.to_dict()}


@desktop_router.post("/launch-workspace")
async def launch_workspace(body: LaunchWorkspaceRequest, request: Request):
    """Open a local project workspace on explicit user request."""
    result = get_desktop_service(request).launch_workspace(
        body.path,
        app_name=body.app_name,
        requested_by=body.requested_by,
        privacy_mode=_privacy_mode(request),
    )
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.to_dict())
    return {"launch": result.to_dict()}


@desktop_router.post("/launch-repo")
async def launch_repo(body: LaunchWorkspaceRequest, request: Request):
    """Open a local repository on explicit user request."""
    result = get_desktop_service(request).launch_repo(
        body.path,
        requested_by=body.requested_by,
        privacy_mode=_privacy_mode(request),
    )
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.to_dict())
    return {"launch": result.to_dict()}


@desktop_router.post("/launch-coding-environment")
async def launch_coding_environment(body: LaunchWorkspaceRequest, request: Request):
    """Launch a coding environment for a local workspace."""
    result = get_desktop_service(request).launch_coding_environment(
        body.path,
        coding_environment=body.coding_environment,
        requested_by=body.requested_by,
        privacy_mode=_privacy_mode(request),
    )
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.to_dict())
    return {"launch": result.to_dict()}


__all__ = ["desktop_router", "get_desktop_service"]
