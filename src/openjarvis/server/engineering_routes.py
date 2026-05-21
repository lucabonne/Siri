"""Engineering / CAD Workspace Phase 1 API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from openjarvis.engineering import EngineeringService

engineering_router = APIRouter(prefix="/v1/engineering", tags=["engineering"])


class OpenEngineeringProjectRequest(BaseModel):
    path: str
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


def get_engineering_service(request: Request) -> EngineeringService:
    """Return the app-level engineering service, creating one lazily."""

    service = getattr(request.app.state, "engineering_service", None)
    if service is not None:
        _attach_runtime_integrations(service, request)
        return service

    memory_service = _structured_memory_service(request)
    service = EngineeringService(
        memory_service=memory_service,
        context_layer=getattr(request.app.state, "context_layer", None),
        agent_workspace_registry=getattr(
            request.app.state,
            "agent_workspace_registry",
            None,
        ),
        research_service=getattr(request.app.state, "research_service", None),
        workflow_service=getattr(request.app.state, "workflow_service", None),
    )
    request.app.state.engineering_service = service
    return service


def _attach_runtime_integrations(service: EngineeringService, request: Request) -> None:
    if getattr(service, "memory_service", None) is None:
        service.memory_service = _structured_memory_service(request)
    service.agent_workspace_registry = getattr(
        request.app.state,
        "agent_workspace_registry",
        None,
    )
    service.research_service = getattr(request.app.state, "research_service", None)
    service.workflow_service = getattr(request.app.state, "workflow_service", None)


@engineering_router.get("/status")
async def engineering_status(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return passive Engineering Workspace status for Mission Control."""

    return (
        get_engineering_service(request)
        .status(
            cwd=Path(cwd).expanduser() if cwd else None,
            privacy_mode=_privacy_mode(request),
        )
        .to_dict()
    )


@engineering_router.get("/projects")
async def engineering_projects(
    request: Request,
    root: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
):
    """List detected local engineering projects."""

    projects = get_engineering_service(request).list_projects(
        root=Path(root).expanduser() if root else None,
        limit=limit,
    )
    return {
        "projects": [item.to_dict() for item in projects],
        "privacy_mode": _privacy_mode(request),
        "local_only": True,
        "passive_only": True,
        "cloud_uploads_enabled": False,
        "autonomous_editing": False,
        "cad_modifications_enabled": False,
    }


@engineering_router.get("/project-summary")
async def engineering_project_summary(
    request: Request,
    path: str = Query(...),
):
    """Return a passive summary of one engineering project path."""

    target = Path(path).expanduser()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Engineering project not found")
    return {
        "summary": get_engineering_service(request)
        .project_summary(target, privacy_mode=_privacy_mode(request))
        .to_dict()
    }


@engineering_router.post("/open-project")
async def open_engineering_project(
    body: OpenEngineeringProjectRequest,
    request: Request,
):
    """Select an active engineering workspace without editing CAD files."""

    try:
        project = get_engineering_service(request).open_project(
            body.path,
            requested_by=body.requested_by,
            privacy_mode=_privacy_mode(request),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Engineering project not found",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "project": project.to_dict(),
        "workspace_state": get_engineering_service(
            request,
        ).session_store.load().to_dict(),
        "privacy_mode": _privacy_mode(request),
        "local_only": True,
        "passive_only": True,
        "cloud_uploads_enabled": False,
        "autonomous_editing": False,
        "cad_modifications_enabled": False,
    }


@engineering_router.get("/recent-files")
async def recent_engineering_files(
    request: Request,
    root: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=100),
):
    """Return recent local engineering files."""

    files = get_engineering_service(request).recent_files(
        root=Path(root).expanduser() if root else None,
        limit=limit,
    )
    return {
        "files": [item.to_dict() for item in files],
        "privacy_mode": _privacy_mode(request),
        "local_only": True,
        "passive_only": True,
        "cloud_uploads_enabled": False,
    }


__all__ = ["engineering_router", "get_engineering_service"]
