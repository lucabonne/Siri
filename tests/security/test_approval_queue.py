"""Tests for permission approval queue persistence."""

from __future__ import annotations

from openjarvis.security.approval_queue import ApprovalQueue
from openjarvis.security.permissions import (
    PermissionDecision,
    PermissionLevel,
    PermissionRequest,
)


def test_approval_queue_enqueue_and_decide(tmp_path) -> None:
    queue = ApprovalQueue(tmp_path / "approvals")
    record = queue.enqueue(
        PermissionRequest(
            tool_name="shell_exec",
            arguments={"command": "echo hello", "secret": "hidden"},
            agent_id="agent-1",
            metadata={"source": "server_streaming"},
        ),
        PermissionDecision(
            action="require_confirmation",
            level=PermissionLevel.CONFIRMED_EXECUTION,
            reason="shell command requires confirmation",
        ),
    )

    assert record.status == "pending"
    assert record.tool == "shell_exec"
    assert record.argument_keys == ["command", "secret"]
    assert record.command_preview == "echo hello"

    pending = queue.list()
    assert [item.id for item in pending] == [record.id]

    approved = queue.decide(record.id, "approved", note="looks fine")
    assert approved.status == "approved"
    assert approved.decision_note == "looks fine"
    assert queue.list() == []
    assert queue.list(status="approved")[0].id == record.id
