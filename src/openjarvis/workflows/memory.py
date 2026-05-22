"""Workflow memory integration."""

from __future__ import annotations

from typing import Any

from openjarvis.workflows.models import WorkflowRun


class WorkflowMemoryRecorder:
    """Records workflow run summaries in the structured memory service."""

    def __init__(self, memory_service: Any = None) -> None:
        self._memory = memory_service

    def record_run(self, run: WorkflowRun) -> dict[str, Any] | None:
        if self._memory is None:
            return None
        create_memory = getattr(self._memory, "create_memory", None)
        if create_memory is None:
            return None

        content = (
            f"Workflow '{run.workflow_name}' finished with status {run.status}."
        )
        try:
            return create_memory(
                content,
                memory_type="workflow_run",
                metadata={
                    "workflow_id": run.workflow_id,
                    "workflow_run_id": run.id,
                    "status": run.status,
                    "approvals": run.approvals,
                    "local_only": run.local_only,
                    "privacy_mode": run.privacy_mode,
                },
                tags=["workflow", run.workflow_id],
            )
        except Exception:
            return None


__all__ = ["WorkflowMemoryRecorder"]
