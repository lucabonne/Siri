"""Workflow approval integration."""

from __future__ import annotations

from typing import Any

from openjarvis.security.approval_queue import ApprovalQueue, ApprovalRecord
from openjarvis.security.permissions import PermissionDecision, PermissionRequest
from openjarvis.workflows.models import WorkflowDefinition, WorkflowStep


class WorkflowApprovalService:
    """Queues workflow step approvals using the shared approval queue."""

    def __init__(self, approval_queue: ApprovalQueue | None = None) -> None:
        self._queue = approval_queue or ApprovalQueue()

    @property
    def queue(self) -> ApprovalQueue:
        return self._queue

    def enqueue_step(
        self,
        workflow: WorkflowDefinition,
        step: WorkflowStep,
        request: PermissionRequest,
        decision: PermissionDecision,
        *,
        run_id: str,
    ) -> ApprovalRecord:
        metadata: dict[str, Any] = {
            **request.metadata,
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "workflow_run_id": run_id,
            "workflow_step_id": step.id,
            "rollback_hint": step.rollback_hint,
            "source": "workflow",
        }
        request.metadata.clear()
        request.metadata.update(metadata)
        return self._queue.enqueue(
            request,
            decision,
            source=f"workflow:{workflow.id}:{step.id}",
        )

    def list_for_workflow(
        self,
        *,
        workflow_id: str | None = None,
        status: str = "pending",
        limit: int = 50,
    ) -> list[ApprovalRecord]:
        records = self._queue.list(status=status, limit=limit)
        if not workflow_id:
            return [
                record
                for record in records
                if record.source.startswith("workflow:")
            ]
        prefix = f"workflow:{workflow_id}:"
        return [record for record in records if record.source.startswith(prefix)]


__all__ = ["WorkflowApprovalService"]
