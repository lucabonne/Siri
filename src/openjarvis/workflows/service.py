"""Public service for controlled automation workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openjarvis.agent_workspace import AgentWorkspaceRegistry
from openjarvis.modes import ModeRegistry
from openjarvis.security.approval_queue import ApprovalQueue
from openjarvis.security.permissions import PermissionMiddleware
from openjarvis.workflows.approvals import WorkflowApprovalService
from openjarvis.workflows.definitions import builtin_workflows
from openjarvis.workflows.history import WorkflowHistoryStore
from openjarvis.workflows.memory import WorkflowMemoryRecorder
from openjarvis.workflows.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunRequest,
)
from openjarvis.workflows.runner import WorkflowRunner
from openjarvis.workflows.validation import WorkflowValidationError, validate_workflows


class WorkflowService:
    """Facade for listing, running, and inspecting workflow state."""

    def __init__(
        self,
        workflows: list[WorkflowDefinition] | None = None,
        *,
        history_store: WorkflowHistoryStore | None = None,
        approval_queue: ApprovalQueue | None = None,
        permission_middleware: PermissionMiddleware | None = None,
        mode_registry: ModeRegistry | None = None,
        agent_workspace_registry: AgentWorkspaceRegistry | None = None,
        memory_service: Any = None,
        terminal_store: Any = None,
    ) -> None:
        self._workflows = workflows or builtin_workflows()
        validate_workflows(self._workflows)
        self._workflow_map = {workflow.id: workflow for workflow in self._workflows}
        self._history = history_store or WorkflowHistoryStore()
        self._approval_queue = approval_queue or ApprovalQueue()
        self._mode_registry = mode_registry or ModeRegistry(persist=False)
        self._agent_registry = agent_workspace_registry or AgentWorkspaceRegistry()
        self._permission_middleware = permission_middleware or PermissionMiddleware(
            mode_registry=self._mode_registry
        )
        self._memory_recorder = WorkflowMemoryRecorder(memory_service)
        self._terminal_store = terminal_store

    @property
    def history_store(self) -> WorkflowHistoryStore:
        return self._history

    def list_workflows(self) -> list[WorkflowDefinition]:
        return sorted(self._workflows, key=lambda workflow: workflow.name.lower())

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition:
        try:
            return self._workflow_map[workflow_id]
        except KeyError as exc:
            raise KeyError(f"unknown workflow: {workflow_id}") from exc

    def run_workflow(
        self,
        workflow_id: str,
        *,
        agent_id: str = "",
        mode_id: str = "",
        cwd: str | Path | None = None,
        requested_by: str = "user",
        dry_run: bool = False,
    ) -> WorkflowRun:
        workflow = self.get_workflow(workflow_id)
        runner = WorkflowRunner(
            permission_middleware=self._permission_middleware,
            approval_service=WorkflowApprovalService(self._approval_queue),
            memory_recorder=self._memory_recorder,
            mode_registry=self._mode_registry,
            agent_workspace_registry=self._agent_registry,
            terminal_store=self._terminal_store,
        )
        run = runner.run(
            workflow,
            WorkflowRunRequest(
                workflow_id=workflow_id,
                agent_id=agent_id,
                mode_id=mode_id,
                cwd=str(cwd or ""),
                requested_by=requested_by,
                dry_run=dry_run,
            ),
        )
        self._history.append(run)
        return run

    def get_status(self, run_id: str) -> WorkflowRun:
        return self._history.get(run_id)

    def history(self, *, limit: int = 50) -> list[WorkflowRun]:
        return self._history.latest(limit=limit)

    def approvals(
        self,
        *,
        workflow_id: str | None = None,
        status: str = "pending",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        service = WorkflowApprovalService(self._approval_queue)
        return [
            record.to_json()
            for record in service.list_for_workflow(
                workflow_id=workflow_id,
                status=status,
                limit=limit,
            )
        ]

    def mission_control_snapshot(self) -> dict[str, Any]:
        runs = self.history(limit=50)
        running = [
            run.to_dict()
            for run in runs
            if run.status in {"running", "waiting_approval"}
        ]
        failures = [
            run.to_dict()
            for run in runs
            if run.status in {"blocked", "failed"}
        ][:10]
        return {
            "available_workflows": [
                workflow.to_dict() for workflow in self.list_workflows()
            ],
            "running_workflows": running,
            "history": [run.to_dict() for run in runs[:20]],
            "approvals": self.approvals(status="pending", limit=50),
            "failures": failures,
            "privacy": {
                "local_only": True,
                "external_sync": False,
            },
        }


__all__ = ["WorkflowService", "WorkflowValidationError"]
