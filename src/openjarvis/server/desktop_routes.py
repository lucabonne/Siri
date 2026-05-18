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
        mode_registry=mode_registry,
        coding_assistant=coding,
    )
    request.app.state.desktop_service = service
    return service


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
