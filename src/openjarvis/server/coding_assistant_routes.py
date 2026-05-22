"""Coding assistant API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from openjarvis.coding_assistant import CodingAssistantService
from openjarvis.context.terminal import TerminalContextStore
from openjarvis.repo_index import RepoIndexService
from openjarvis.security.permissions import PermissionMiddleware
from openjarvis.server.notification_routes import get_notification_service

coding_assistant_router = APIRouter(prefix="/v1/coding", tags=["coding-assistant"])


class BuildAnalysisRequest(BaseModel):
    cwd: str | None = None
    command: str = ""
    output: str = ""
    exit_code: int | None = None


class SafeFixRequest(BaseModel):
    cwd: str | None = None
    command: str = ""
    output: str = ""
    exit_code: int | None = None


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


def _service(request: Request) -> CodingAssistantService:
    service = getattr(request.app.state, "coding_assistant_service", None)
    if service is None:
        memory = _structured_memory_service(request)
        repo_service = getattr(request.app.state, "repo_index_service", None)
        if repo_service is None:
            repo_service = RepoIndexService(memory_service=memory)
            request.app.state.repo_index_service = repo_service
        terminal_store = getattr(request.app.state, "terminal_context_store", None)
        if terminal_store is None:
            terminal_store = TerminalContextStore()
            request.app.state.terminal_context_store = terminal_store
        permission = getattr(request.app.state, "_permission_middleware", None)
        if permission is None:
            permission = PermissionMiddleware(
                mode_registry=getattr(request.app.state, "mode_registry", None)
            )
            request.app.state._permission_middleware = permission
        service = CodingAssistantService(
            repo_index_service=repo_service,
            terminal_store=terminal_store,
            memory_service=memory,
            permission_middleware=permission,
            agent_workspace_registry=getattr(
                request.app.state,
                "agent_workspace_registry",
                None,
            ),
        )
        request.app.state.coding_assistant_service = service
    return service


@coding_assistant_router.post("/analyze-build")
async def analyze_build(body: BuildAnalysisRequest, request: Request):
    """Analyze build output locally and return passive fix guidance."""
    privacy = _privacy_mode(request)
    analysis = (
        _service(request)
        .analyze_build(
            body.cwd,
            command=body.command,
            output=body.output,
            exit_code=body.exit_code,
            privacy_mode=privacy,
        )
    )
    if body.exit_code is not None:
        try:
            get_notification_service(request).notify_build_completed(
                status="failed" if body.exit_code else "succeeded",
                cwd=body.cwd or "",
                privacy_mode=privacy,
            )
        except Exception:
            pass
    return analysis.to_dict()


@coding_assistant_router.get("/architecture")
async def explain_architecture(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return a repo-aware architecture explanation."""
    return (
        _service(request)
        .explain_architecture(
            cwd,
            privacy_mode=_privacy_mode(request),
        )
        .to_dict()
    )


@coding_assistant_router.get("/debugging-summary")
async def repo_debugging_summary(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return repo and terminal aware debugging guidance."""
    return (
        _service(request)
        .repo_debugging_summary(
            cwd,
            privacy_mode=_privacy_mode(request),
        )
        .to_dict()
    )


@coding_assistant_router.post("/safe-fixes")
async def safe_fix_suggestions(body: SafeFixRequest, request: Request):
    """Return passive, approval-gated fix suggestions."""
    fixes = _service(request).safe_fix_suggestions(
        body.cwd,
        command=body.command,
        output=body.output,
        exit_code=body.exit_code,
        privacy_mode=_privacy_mode(request),
    )
    return {
        "suggested_fixes": [item.to_dict() for item in fixes],
        "local_only": True,
        "passive_only": True,
        "privacy_mode": _privacy_mode(request),
    }


@coding_assistant_router.get("/health")
async def project_health_summary(
    request: Request,
    cwd: str | None = Query(default=None),
    persist_memory: bool = Query(default=False),
):
    """Return a passive project health summary."""
    privacy = _privacy_mode(request)
    return (
        _service(request)
        .project_health_summary(
            cwd,
            privacy_mode=privacy,
            persist_memory=persist_memory and not privacy,
        )
        .to_dict()
    )


@coding_assistant_router.get("/panel")
async def coding_panel(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return Mission Control coding panel data."""
    return (
        _service(request)
        .coding_panel(
            cwd,
            privacy_mode=_privacy_mode(request),
        )
        .to_dict()
    )


__all__ = ["coding_assistant_router"]
