from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.agent_workspace import AgentWorkspaceRegistry
from openjarvis.modes import ModeRegistry
from openjarvis.security.approval_queue import ApprovalQueue
from openjarvis.security.permissions import PermissionMiddleware
from openjarvis.server.workflow_routes import workflow_router
from openjarvis.workflows import WorkflowService, builtin_workflows
from openjarvis.workflows.history import WorkflowHistoryStore


def _service(tmp_path) -> WorkflowService:
    mode_registry = ModeRegistry(
        state_path=tmp_path / "current_mode.json",
        persist=False,
    )
    approval_queue = ApprovalQueue(tmp_path / "approvals")
    return WorkflowService(
        history_store=WorkflowHistoryStore(tmp_path / "workflow_history.jsonl"),
        approval_queue=approval_queue,
        permission_middleware=PermissionMiddleware(
            audit_log_path=tmp_path / "permissions.log",
            mode_registry=mode_registry,
        ),
        mode_registry=mode_registry,
        agent_workspace_registry=AgentWorkspaceRegistry(),
    )


def test_builtin_workflows_cover_phase_one_examples() -> None:
    workflow_ids = {workflow.id for workflow in builtin_workflows()}

    assert workflow_ids >= {
        "open_project_environment",
        "run_tests",
        "summarize_repo",
        "prepare_research_session",
        "collect_logs",
        "backup_notes",
        "launch_coding_workspace",
        "start_morning_workflow",
    }
    assert all(workflow.privacy_local_only for workflow in builtin_workflows())
    assert not any(workflow.external_sync for workflow in builtin_workflows())


def test_safe_workflow_completes_without_approval(tmp_path) -> None:
    service = _service(tmp_path)

    run = service.run_workflow(
        "open_project_environment",
        agent_id="coding",
        mode_id="focus",
        cwd=tmp_path,
    )

    assert run.status == "completed"
    assert run.approvals == []
    assert all(step.status == "completed" for step in run.steps)
    assert service.get_status(run.id).workflow_id == "open_project_environment"


def test_gated_workflow_queues_approval_and_does_not_execute(tmp_path) -> None:
    service = _service(tmp_path)

    run = service.run_workflow(
        "run_tests",
        agent_id="terminal",
        mode_id="coding",
        cwd=tmp_path,
    )

    assert run.status == "waiting_approval"
    assert len(run.approvals) == 1
    assert run.steps[-1].tool_name == "shell_exec"
    assert run.steps[-1].approval_id == run.approvals[0]
    approvals = service.approvals(workflow_id="run_tests")
    assert approvals[0]["command_preview"] == "python -m pytest -q"


@pytest.mark.parametrize(
    ("workflow_id", "agent_id", "mode_id", "expected_status"),
    [
        ("summarize_repo", "coding", "coding", "waiting_approval"),
        ("prepare_research_session", "research", "research", "completed"),
        ("collect_logs", "terminal", "focus", "completed"),
        ("backup_notes", "terminal", "focus", "waiting_approval"),
        ("launch_coding_workspace", "coding", "coding", "completed"),
        ("start_morning_workflow", "scheduler", "focus", "completed"),
    ],
)
def test_builtin_workflows_are_runnable_or_gated(
    tmp_path,
    workflow_id,
    agent_id,
    mode_id,
    expected_status,
) -> None:
    service = _service(tmp_path)

    run = service.run_workflow(
        workflow_id,
        agent_id=agent_id,
        mode_id=mode_id,
        cwd=tmp_path,
    )

    assert run.status == expected_status
    assert run.status != "blocked"


def test_privacy_mode_rejects_disallowed_workflow(tmp_path) -> None:
    service = _service(tmp_path)

    with pytest.raises(ValueError, match="mode 'privacy'"):
        service.run_workflow(
            "run_tests",
            agent_id="terminal",
            mode_id="privacy",
            cwd=tmp_path,
        )


def test_workflow_routes_expose_panel_and_run(tmp_path) -> None:
    app = FastAPI()
    app.state.workflow_service = _service(tmp_path)
    app.include_router(workflow_router)
    client = TestClient(app)

    listed = client.get("/v1/workflows")
    assert listed.status_code == 200
    assert listed.json()["privacy"] == {"local_only": True, "external_sync": False}

    run = client.post(
        "/v1/workflows/run_tests/run",
        json={"agent_id": "terminal", "mode_id": "coding", "cwd": str(tmp_path)},
    )
    assert run.status_code == 200
    body = run.json()["run"]
    assert body["status"] == "waiting_approval"

    panel = client.get("/v1/workflows/mission-control")
    assert panel.status_code == 200
    assert panel.json()["running_workflows"][0]["id"] == body["id"]
