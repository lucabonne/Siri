"""Read-only local context routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from openjarvis.context import ContextLayer
from openjarvis.context.terminal import TerminalContextStore
from openjarvis.context.vision import VisionContextStore
from openjarvis.security.approval_queue import ApprovalQueue
from openjarvis.security.permissions import (
    PermissionDecision,
    PermissionLevel,
    PermissionMiddleware,
    PermissionRequest,
)

context_router = APIRouter(prefix="/v1/context", tags=["context"])


def _privacy_mode(request: Request) -> bool:
    registry = getattr(request.app.state, "mode_registry", None)
    if registry is None:
        return False
    try:
        return registry.get_active_mode().mode.id == "privacy"
    except Exception:
        return False


def _layer(cwd: str | None) -> ContextLayer:
    return ContextLayer(cwd=Path(cwd).expanduser() if cwd else None)


class TerminalCommandCaptureRequest(BaseModel):
    command: str
    output: str = ""
    exit_code: int | None = None
    cwd: str | None = None
    shell_type: str | None = None
    timestamp: str | None = None


class ScreenshotCaptureRequest(BaseModel):
    cwd: str | None = None
    request_approval_on_privacy: bool = True


def _terminal_store(request: Request) -> TerminalContextStore:
    store = getattr(request.app.state, "terminal_context_store", None)
    if store is None:
        store = TerminalContextStore()
        request.app.state.terminal_context_store = store
    return store


def _vision_store(request: Request) -> VisionContextStore:
    store = getattr(request.app.state, "vision_context_store", None)
    if store is None:
        store = VisionContextStore()
        request.app.state.vision_context_store = store
    return store


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


@context_router.get("/desktop")
async def get_desktop_context(request: Request, cwd: str | None = Query(default=None)):
    """Return passive desktop context collected locally."""
    context = _layer(cwd).current_desktop_context(privacy_mode=_privacy_mode(request))
    return context.to_dict()


@context_router.get("/project")
async def get_project_context(cwd: str | None = Query(default=None)):
    """Return passive project context for the current working directory."""
    return _layer(cwd).current_project_context().to_dict()


@context_router.get("/repo")
async def get_repo_context(cwd: str | None = Query(default=None)):
    """Return lightweight repository inventory and summary metadata."""
    return _layer(cwd).repo_index().to_dict()


@context_router.post("/vision/screenshots")
async def capture_screenshot(
    body: ScreenshotCaptureRequest,
    request: Request,
):
    """Capture one local screenshot on explicit request.

    This route never uploads screenshot bytes and does not start a watcher.
    Privacy Mode blocks capture and, by default, queues an approval record
    without taking a screenshot.
    """
    privacy_mode = _privacy_mode(request)
    if privacy_mode:
        approval = None
        if body.request_approval_on_privacy:
            permission_request = PermissionRequest(
                tool_name="vision_screenshot_capture",
                arguments={"cwd": body.cwd or ""},
                dry_run=True,
                metadata={"source": "vision_layer", "passive_only": True},
            )
            decision = PermissionDecision(
                action="require_confirmation",
                level=PermissionLevel.CONFIRMED_EXECUTION,
                reason="privacy mode requires approval before screenshot capture",
                matched_pattern="privacy-vision-screenshot",
                dry_run=True,
                metadata={"would_capture": True, "cloud_uploaded": False},
            )
            approval = ApprovalQueue().enqueue(
                permission_request,
                decision,
                source="vision_layer",
            )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "privacy_mode_blocks_screenshot_capture",
                "approval": approval.to_json() if approval else None,
                "privacy_mode": True,
                "passive_only": True,
                "local_only": True,
                "cloud_uploaded": False,
            },
        )

    middleware = PermissionMiddleware(
        mode_registry=getattr(request.app.state, "mode_registry", None)
    )
    decision = middleware.check(
        PermissionRequest(
            tool_name="vision_screenshot_capture",
            arguments={"cwd": body.cwd or ""},
            metadata={"source": "vision_layer", "passive_only": True},
        )
    )
    if decision.denied:
        raise HTTPException(status_code=403, detail=decision.reason)

    try:
        metadata = _vision_store(request).capture(
            cwd=body.cwd,
            privacy_mode=False,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return {
        "screenshot": metadata.to_dict(),
        "privacy_mode": False,
        "passive_only": True,
        "local_only": True,
        "cloud_uploaded": False,
    }


@context_router.get("/vision/screenshots")
async def list_recent_screenshots(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
):
    """Return recent local screenshot metadata only."""
    privacy_mode = _privacy_mode(request)
    screenshots = _vision_store(request).recent(
        limit=limit,
        privacy_mode=privacy_mode,
    )
    return {
        "screenshots": [screenshot.to_dict() for screenshot in screenshots],
        "privacy_mode": privacy_mode,
        "passive_only": True,
        "local_only": True,
        "cloud_uploaded": False,
    }


@context_router.get("/vision/latest")
async def get_latest_visual_context(request: Request):
    """Return latest local visual context metadata without image bytes."""
    return (
        _vision_store(request)
        .latest_context(privacy_mode=_privacy_mode(request))
        .to_dict()
    )


@context_router.post("/terminal/commands")
async def capture_terminal_command(
    body: TerminalCommandCaptureRequest,
    request: Request,
):
    """Record a passive completed terminal command snapshot.

    This endpoint only accepts terminal telemetry supplied by a local shell
    integration. It does not execute commands.
    """
    if not body.command.strip():
        raise HTTPException(status_code=400, detail="command cannot be empty")

    store = _terminal_store(request)
    record = store.record(
        command=body.command,
        output=body.output,
        exit_code=body.exit_code,
        cwd=body.cwd,
        shell_type=body.shell_type,
        timestamp=body.timestamp,
    )

    memory = None
    if not _privacy_mode(request):
        service = _structured_memory_service(request)
        if service is not None:
            try:
                memory = service.record_command_history(
                    command=record.command,
                    cwd=record.cwd,
                    exit_code=record.exit_code,
                    output_preview=record.output_preview,
                    metadata={
                        "source": "terminal_copilot",
                        "shell_type": record.shell_type,
                        "repo_context": record.repo_context,
                        "passive_only": True,
                    },
                    created_at=record.timestamp,
                )
            except Exception:
                memory = None

    return {
        "record": record.to_dict(),
        "analysis": store.error_summary(privacy_mode=_privacy_mode(request)).to_dict(),
        "memory_recorded": memory is not None,
        "passive_only": True,
    }


@context_router.get("/terminal/current")
async def get_terminal_context(
    request: Request,
    cwd: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Return current passive terminal context and recent local analysis."""
    return (
        _terminal_store(request)
        .current_context(
            cwd=cwd,
            privacy_mode=_privacy_mode(request),
            limit=limit,
        )
        .to_dict()
    )


@context_router.get("/terminal/history")
async def get_terminal_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
):
    """Return recent passive terminal command history."""
    records = _terminal_store(request).recent_history(
        limit=limit,
        privacy_mode=_privacy_mode(request),
    )
    return {"history": [record.to_dict() for record in records], "passive_only": True}


@context_router.get("/terminal/error-summary")
async def get_terminal_error_summary(request: Request):
    """Return a local-only error summary for the last captured terminal command."""
    return (
        _terminal_store(request)
        .error_summary(privacy_mode=_privacy_mode(request))
        .to_dict()
    )


@context_router.get("/terminal/suggested-fixes")
async def get_terminal_suggested_fixes(request: Request):
    """Return possible fixes and approval-gated suggested commands."""
    return _terminal_store(request).suggested_fixes(privacy_mode=_privacy_mode(request))


@context_router.post("/terminal/suggested-commands/{command_id}/approval")
async def request_terminal_command_approval(command_id: str, request: Request):
    """Queue an approval for a suggested command without executing it."""
    command = _terminal_store(request).find_suggested_command(command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="Suggested command not found")

    permission_request = PermissionRequest(
        tool_name="shell_exec",
        arguments={"command": command.command},
        command=command.command,
        dry_run=True,
        metadata={
            "source": "terminal_copilot",
            "suggested_command_id": command.id,
            "passive_only": True,
        },
    )
    level = PermissionLevel[command.permission_level]
    decision = PermissionDecision(
        action="require_confirmation",
        level=level,
        reason=(
            "terminal copilot suggested command requires approval: "
            f"{command.reason}"
        ),
        matched_pattern=command.matched_pattern,
        dry_run=True,
        metadata={
            "would_action": command.permission_action,
            "would_level": command.permission_level,
            "dry_run_preview": command.dry_run_preview,
            "dangerous": command.dangerous,
        },
    )
    record = ApprovalQueue().enqueue(
        permission_request,
        decision,
        source="terminal_copilot",
    )
    return {
        "approval": record.to_json(),
        "suggested_command": command.to_dict(),
        "executed": False,
        "passive_only": True,
    }
