"""Controlled workflow runner.

The runner is intentionally conservative: it never starts background agents and
never executes approval-gated operations. It records safe local context steps
and queues shared approvals for anything that crosses the permission boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from openjarvis.agent_workspace import AgentWorkspaceRegistry
from openjarvis.context.layer import ContextLayer
from openjarvis.context.terminal import TerminalContextStore
from openjarvis.modes import ModeRegistry
from openjarvis.security.permissions import (
    PermissionMiddleware,
    PermissionRequest,
)
from openjarvis.workflows.approvals import WorkflowApprovalService
from openjarvis.workflows.memory import WorkflowMemoryRecorder
from openjarvis.workflows.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunRequest,
    WorkflowStep,
    WorkflowStepRun,
    utc_now,
)
from openjarvis.workflows.validation import validate_runtime_request


class WorkflowRunner:
    """Runs one user-triggered workflow through local safety checks."""

    def __init__(
        self,
        *,
        permission_middleware: PermissionMiddleware | None = None,
        approval_service: WorkflowApprovalService | None = None,
        memory_recorder: WorkflowMemoryRecorder | None = None,
        mode_registry: ModeRegistry | None = None,
        agent_workspace_registry: AgentWorkspaceRegistry | None = None,
        terminal_store: TerminalContextStore | None = None,
    ) -> None:
        self._mode_registry = mode_registry or ModeRegistry(persist=False)
        self._agent_registry = agent_workspace_registry or AgentWorkspaceRegistry()
        self._permissions = permission_middleware or PermissionMiddleware(
            mode_registry=self._mode_registry
        )
        self._approvals = approval_service or WorkflowApprovalService()
        self._memory = memory_recorder or WorkflowMemoryRecorder()
        self._terminal_store = terminal_store or TerminalContextStore()

    def run(
        self,
        workflow: WorkflowDefinition,
        request: WorkflowRunRequest,
    ) -> WorkflowRun:
        mode_id = (
            request.mode_id
            or self._mode_registry.get_active_mode().active_mode_id
        )
        mode = self._mode_registry.get_mode(mode_id)
        privacy_mode = mode.id == "privacy"
        agent_id = request.agent_id or self._resolve_agent(workflow)
        cwd = str(Path(request.cwd or os.getcwd()).expanduser())
        validate_runtime_request(
            workflow,
            agent_id=agent_id,
            mode_id=mode_id,
            privacy_mode=privacy_mode,
        )

        now = utc_now()
        run = WorkflowRun(
            id=self._run_id(workflow.id, now, agent_id, mode_id, cwd),
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status="running",
            requested_at=now,
            updated_at=now,
            requested_by=request.requested_by,
            agent_id=agent_id,
            mode_id=mode_id,
            cwd=cwd,
            privacy_mode=privacy_mode,
            local_only=workflow.privacy_local_only,
            external_sync=False,
            context_summary=self._context_summary(cwd, privacy_mode),
        )

        for step in workflow.steps:
            step_run = self._run_step(
                workflow,
                step,
                run=run,
                agent_id=agent_id,
                mode=mode,
                cwd=cwd,
                dry_run=request.dry_run,
            )
            run.steps.append(step_run)
            run.current_step_id = step.id
            run.updated_at = utc_now()
            if step_run.status in {"waiting_approval", "blocked", "failed"}:
                run.status = (
                    "waiting_approval"
                    if step_run.status == "waiting_approval"
                    else step_run.status
                )
                run.failure_reason = (
                    step_run.reason
                    if step_run.status != "waiting_approval"
                    else ""
                )
                break
        else:
            run.status = "completed"
            run.completed_at = utc_now()
            run.updated_at = run.completed_at

        self._memory.record_run(run)
        return run

    def _run_step(
        self,
        workflow: WorkflowDefinition,
        step: WorkflowStep,
        *,
        run: WorkflowRun,
        agent_id: str,
        mode: Any,
        cwd: str,
        dry_run: bool,
    ) -> WorkflowStepRun:
        step_run = WorkflowStepRun(
            step_id=step.id,
            name=step.name,
            tool_name=step.tool_name,
            rollback_hint=step.rollback_hint,
        )
        if step.mode_restrictions and mode.id not in step.mode_restrictions:
            step_run.status = "blocked"
            step_run.reason = f"mode '{mode.id}' cannot run step '{step.id}'"
            return step_run
        if step.allowed_agents and agent_id not in step.allowed_agents:
            step_run.status = "blocked"
            step_run.reason = f"agent '{agent_id}' cannot run step '{step.id}'"
            return step_run

        if not step.passive_only and not step.approval_required:
            allowed, reason = self._agent_registry.validate_tool_request(
                agent_id,
                step.tool_name,
            )
            if not allowed:
                step_run.status = "blocked"
                step_run.reason = reason
                return step_run

        arguments = dict(step.arguments)
        arguments.setdefault("cwd", cwd)
        request = PermissionRequest(
            tool_name=step.tool_name,
            arguments=arguments,
            command=(
                arguments.get("command")
                if isinstance(arguments.get("command"), str)
                else None
            ),
            agent_id=agent_id,
            dry_run=dry_run,
            metadata={
                "source": "workflow",
                "workflow_id": workflow.id,
                "workflow_run_id": run.id,
                "workflow_step_id": step.id,
                "active_mode": mode,
                "active_mode_id": mode.id,
                "local_only": True,
                "external_sync": False,
                "passive_only": step.passive_only,
            },
        )
        self._agent_registry.apply_to_permission_request(request, agent_id=agent_id)
        decision = self._permissions.check(request)
        level = decision.metadata.get("would_level") or decision.level.name
        action = decision.metadata.get("would_action") or decision.action
        step_run.permission_level = str(level)
        step_run.permission_action = str(action)
        step_run.reason = decision.reason

        if decision.denied or action == "deny":
            step_run.status = "blocked"
            return step_run

        if (
            step.approval_required
            or decision.requires_confirmation
            or action == "require_confirmation"
        ):
            approval = self._approvals.enqueue_step(
                workflow,
                step,
                request,
                decision,
                run_id=run.id,
            )
            run.approvals.append(approval.id)
            step_run.status = "waiting_approval"
            step_run.approval_id = approval.id
            return step_run

        step_run.status = "completed"
        step_run.output = self._safe_step_output(
            step,
            cwd=cwd,
            privacy_mode=mode.id == "privacy",
        )
        return step_run

    def _resolve_agent(self, workflow: WorkflowDefinition) -> str:
        active_agent = self._agent_registry.get_active_agent().active_agent_id
        if active_agent in workflow.allowed_agents:
            return active_agent
        for agent_id in self._mode_registry.preferred_agents_for_active_mode():
            if agent_id in workflow.allowed_agents:
                return agent_id
        return workflow.allowed_agents[0]

    def _context_summary(self, cwd: str, privacy_mode: bool) -> dict[str, Any]:
        try:
            context = ContextLayer(cwd=cwd).current_project_context()
            return {
                "cwd": context.cwd,
                "git_repository": context.git_repository,
                "current_branch": context.current_branch,
                "project_type": context.project_type,
                "languages": context.languages[:6],
                "privacy_mode": privacy_mode,
                "local_only": True,
            }
        except Exception:
            return {"cwd": cwd, "privacy_mode": privacy_mode, "local_only": True}

    def _safe_step_output(
        self,
        step: WorkflowStep,
        *,
        cwd: str,
        privacy_mode: bool,
    ) -> dict[str, Any]:
        if step.tool_name in {"terminal_context", "terminal_history"}:
            snapshot = self._terminal_store.current_context(
                cwd=cwd,
                privacy_mode=privacy_mode,
                limit=5,
            )
            return {
                "history_count": len(snapshot.history),
                "cwd": snapshot.cwd,
                "has_error": snapshot.error_summary.has_error,
                "local_only": True,
                "passive_only": True,
            }
        if step.tool_name in {"repo_index_search", "git_status"}:
            context = ContextLayer(cwd=cwd).current_project_context()
            return {
                "git_repository": context.git_repository,
                "current_branch": context.current_branch,
                "project_type": context.project_type,
                "languages": context.languages[:6],
                "local_only": True,
                "passive_only": True,
            }
        return {
            "prepared": True,
            "local_only": True,
            "passive_only": step.passive_only,
        }

    @staticmethod
    def _run_id(
        workflow_id: str,
        requested_at: str,
        agent_id: str,
        mode_id: str,
        cwd: str,
    ) -> str:
        seed = json.dumps(
            {
                "workflow_id": workflow_id,
                "requested_at": requested_at,
                "agent_id": agent_id,
                "mode_id": mode_id,
                "cwd": cwd,
            },
            sort_keys=True,
        )
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


__all__ = ["WorkflowRunner"]
