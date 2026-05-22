"""Validation helpers for controlled automation workflows."""

from __future__ import annotations

from openjarvis.workflows.models import WorkflowDefinition


class WorkflowValidationError(ValueError):
    """Raised when a workflow is unsafe or malformed."""


def validate_workflow_definition(workflow: WorkflowDefinition) -> None:
    """Validate static workflow shape and safety invariants."""
    if not workflow.id.strip():
        raise WorkflowValidationError("workflow id is required")
    if not workflow.name.strip():
        raise WorkflowValidationError(f"workflow {workflow.id} name is required")
    if workflow.external_sync:
        raise WorkflowValidationError(
            f"workflow {workflow.id} cannot enable external sync in Phase 1"
        )
    if not workflow.steps:
        raise WorkflowValidationError(f"workflow {workflow.id} requires steps")
    if not workflow.allowed_agents:
        raise WorkflowValidationError(
            f"workflow {workflow.id} requires allowed agents"
        )

    seen: set[str] = set()
    for step in workflow.steps:
        if step.id in seen:
            raise WorkflowValidationError(
                f"workflow {workflow.id} has duplicate step id {step.id}"
            )
        seen.add(step.id)
        if not step.tool_name.strip():
            raise WorkflowValidationError(
                f"workflow {workflow.id} step {step.id} requires a tool"
            )
        if not step.local_only:
            raise WorkflowValidationError(
                f"workflow {workflow.id} step {step.id} must be local-only"
            )


def validate_workflows(workflows: list[WorkflowDefinition]) -> None:
    seen: set[str] = set()
    for workflow in workflows:
        if workflow.id in seen:
            raise WorkflowValidationError(f"duplicate workflow id: {workflow.id}")
        seen.add(workflow.id)
        validate_workflow_definition(workflow)


def validate_runtime_request(
    workflow: WorkflowDefinition,
    *,
    agent_id: str,
    mode_id: str,
    privacy_mode: bool,
) -> None:
    if agent_id and agent_id not in workflow.allowed_agents:
        raise WorkflowValidationError(
            f"agent '{agent_id}' is not allowed for workflow '{workflow.id}'"
        )
    if (
        mode_id
        and workflow.mode_restrictions
        and mode_id not in workflow.mode_restrictions
    ):
        raise WorkflowValidationError(
            f"mode '{mode_id}' cannot run workflow '{workflow.id}'"
        )
    if privacy_mode and (workflow.external_sync or not workflow.privacy_local_only):
        raise WorkflowValidationError(
            "Privacy Mode only allows local-only workflows with no external sync"
        )


__all__ = [
    "WorkflowValidationError",
    "validate_runtime_request",
    "validate_workflow_definition",
    "validate_workflows",
]
