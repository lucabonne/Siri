"""FastAPI routes for controlled automation workflows."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from openjarvis.server.notification_routes import get_notification_service
from openjarvis.workflows import WorkflowService
from openjarvis.workflows.validation import WorkflowValidationError

logger = logging.getLogger(__name__)

workflow_router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


class RunWorkflowRequest(BaseModel):
    agent_id: str = ""
    mode_id: str = ""
    cwd: str = ""
    requested_by: str = "user"
    dry_run: bool = False


def get_workflow_service(request: Request) -> WorkflowService:
    """Return the app-level workflow service, creating one lazily."""
    service = getattr(request.app.state, "workflow_service", None)
    if service is not None:
        return service

    from openjarvis.agent_workspace import AgentWorkspaceRegistry
    from openjarvis.modes import ModeRegistry
    from openjarvis.security.approval_queue import ApprovalQueue
    from openjarvis.security.permissions import PermissionMiddleware

    mode_registry = getattr(request.app.state, "mode_registry", None)
    if mode_registry is None:
        mode_registry = ModeRegistry()
        request.app.state.mode_registry = mode_registry

    agent_registry = getattr(request.app.state, "agent_workspace_registry", None)
    if agent_registry is None:
        agent_registry = AgentWorkspaceRegistry()
        request.app.state.agent_workspace_registry = agent_registry

    approval_queue = getattr(request.app.state, "approval_queue", None)
    if approval_queue is None:
        approval_queue = ApprovalQueue()
        request.app.state.approval_queue = approval_queue

    permission_middleware = getattr(request.app.state, "permission_middleware", None)
    if permission_middleware is None:
        permission_middleware = PermissionMiddleware(mode_registry=mode_registry)
        request.app.state.permission_middleware = permission_middleware

    service = WorkflowService(
        approval_queue=approval_queue,
        permission_middleware=permission_middleware,
        mode_registry=mode_registry,
        agent_workspace_registry=agent_registry,
        memory_service=getattr(request.app.state, "structured_memory_service", None),
        terminal_store=getattr(request.app.state, "terminal_context_store", None),
    )
    request.app.state.workflow_service = service
    return service


@workflow_router.get("")
async def list_workflows(request: Request):
    """List available controlled workflows."""
    service = get_workflow_service(request)
    return {
        "workflows": [workflow.to_dict() for workflow in service.list_workflows()],
        "privacy": {"local_only": True, "external_sync": False},
    }


@workflow_router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    body: RunWorkflowRequest,
    request: Request,
):
    """Run a user-triggered workflow through approval gates."""
    service = get_workflow_service(request)
    try:
        run = service.run_workflow(
            workflow_id,
            agent_id=body.agent_id,
            mode_id=body.mode_id,
            cwd=Path(body.cwd).expanduser() if body.cwd else None,
            requested_by=body.requested_by,
            dry_run=body.dry_run,
        )
        if not body.dry_run:
            try:
                get_notification_service(request).notify_workflow_completed(run)
            except Exception:
                pass
        return {"run": run.to_dict()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Workflow run failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@workflow_router.get("/status/{run_id}")
async def workflow_status(run_id: str, request: Request):
    """Return one workflow run status."""
    service = get_workflow_service(request)
    try:
        return {"run": service.get_status(run_id).to_dict()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Workflow run not found") from exc


@workflow_router.get("/history")
async def workflow_history(request: Request, limit: int = 50):
    """Return recent workflow run history."""
    service = get_workflow_service(request)
    return {
        "history": [
            run.to_dict() for run in service.history(limit=min(max(limit, 0), 200))
        ]
    }


@workflow_router.get("/approvals")
async def workflow_approvals(
    request: Request,
    workflow_id: str | None = None,
    status: str = "pending",
    limit: int = 50,
):
    """Return workflow approval queue items."""
    if status not in {"pending", "approved", "denied", "all"}:
        raise HTTPException(status_code=400, detail="Invalid approval status")
    service = get_workflow_service(request)
    return {
        "approvals": service.approvals(
            workflow_id=workflow_id,
            status=status,
            limit=min(max(limit, 0), 200),
        )
    }


@workflow_router.get("/mission-control")
async def workflow_mission_control(request: Request):
    """Return workflow panel data for Mission Control."""
    service = get_workflow_service(request)
    return service.mission_control_snapshot()


__all__ = ["get_workflow_service", "workflow_router"]
