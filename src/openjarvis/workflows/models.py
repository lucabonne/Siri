"""Typed models for controlled automation workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """One declarative, permission-checked workflow step."""

    id: str
    name: str
    tool_name: str
    description: str
    arguments: dict[str, Any] = field(default_factory=dict)
    required_permission: str = "READ_ONLY"
    approval_required: bool = False
    rollback_hint: str = ""
    allowed_agents: list[str] = field(default_factory=list)
    mode_restrictions: list[str] = field(default_factory=list)
    local_only: bool = True
    passive_only: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkflowStep":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            tool_name=str(data["tool_name"]),
            description=str(data.get("description", "")),
            arguments=dict(data.get("arguments", {})),
            required_permission=str(data.get("required_permission", "READ_ONLY")),
            approval_required=bool(data.get("approval_required", False)),
            rollback_hint=str(data.get("rollback_hint", "")),
            allowed_agents=[str(item) for item in data.get("allowed_agents", [])],
            mode_restrictions=[
                str(item) for item in data.get("mode_restrictions", [])
            ],
            local_only=bool(data.get("local_only", True)),
            passive_only=bool(data.get("passive_only", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """Declarative workflow metadata exposed through Mission Control."""

    id: str
    name: str
    description: str
    steps: list[WorkflowStep]
    required_permissions: list[str]
    approval_requirements: list[str]
    rollback_hints: list[str]
    allowed_agents: list[str]
    mode_restrictions: list[str] = field(default_factory=list)
    privacy_local_only: bool = True
    external_sync: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkflowDefinition":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            steps=[
                (
                    item
                    if isinstance(item, WorkflowStep)
                    else WorkflowStep.from_mapping(item)
                )
                for item in data.get("steps", [])
            ],
            required_permissions=[
                str(item) for item in data.get("required_permissions", [])
            ],
            approval_requirements=[
                str(item) for item in data.get("approval_requirements", [])
            ],
            rollback_hints=[str(item) for item in data.get("rollback_hints", [])],
            allowed_agents=[str(item) for item in data.get("allowed_agents", [])],
            mode_restrictions=[
                str(item) for item in data.get("mode_restrictions", [])
            ],
            privacy_local_only=bool(data.get("privacy_local_only", True)),
            external_sync=bool(data.get("external_sync", False)),
        )

    @property
    def requires_approval(self) -> bool:
        return bool(self.approval_requirements) or any(
            step.approval_required for step in self.steps
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["requires_approval"] = self.requires_approval
        return data


@dataclass(slots=True)
class WorkflowStepRun:
    """Runtime state for a workflow step."""

    step_id: str
    name: str
    tool_name: str
    status: str = "pending"
    permission_action: str = ""
    permission_level: str = ""
    reason: str = ""
    approval_id: str = ""
    rollback_hint: str = ""
    output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkflowRun:
    """Persisted workflow run status."""

    id: str
    workflow_id: str
    workflow_name: str
    status: str
    requested_at: str
    updated_at: str
    completed_at: str | None = None
    requested_by: str = "user"
    agent_id: str = ""
    mode_id: str = ""
    cwd: str = ""
    privacy_mode: bool = False
    local_only: bool = True
    external_sync: bool = False
    current_step_id: str = ""
    failure_reason: str = ""
    approvals: list[str] = field(default_factory=list)
    context_summary: dict[str, Any] = field(default_factory=dict)
    steps: list[WorkflowStepRun] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkflowRun":
        return cls(
            id=str(data["id"]),
            workflow_id=str(data["workflow_id"]),
            workflow_name=str(data.get("workflow_name", "")),
            status=str(data.get("status", "pending")),
            requested_at=str(data.get("requested_at", "")),
            updated_at=str(data.get("updated_at", "")),
            completed_at=data.get("completed_at"),
            requested_by=str(data.get("requested_by", "user")),
            agent_id=str(data.get("agent_id", "")),
            mode_id=str(data.get("mode_id", "")),
            cwd=str(data.get("cwd", "")),
            privacy_mode=bool(data.get("privacy_mode", False)),
            local_only=bool(data.get("local_only", True)),
            external_sync=bool(data.get("external_sync", False)),
            current_step_id=str(data.get("current_step_id", "")),
            failure_reason=str(data.get("failure_reason", "")),
            approvals=[str(item) for item in data.get("approvals", [])],
            context_summary=dict(data.get("context_summary", {})),
            steps=[
                WorkflowStepRun(**dict(item)) for item in data.get("steps", [])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        return data


@dataclass(frozen=True, slots=True)
class WorkflowRunRequest:
    """User-triggered request to run a workflow."""

    workflow_id: str
    agent_id: str = ""
    mode_id: str = ""
    cwd: str = ""
    requested_by: str = "user"
    dry_run: bool = False


__all__ = [
    "WorkflowDefinition",
    "WorkflowRun",
    "WorkflowRunRequest",
    "WorkflowStep",
    "WorkflowStepRun",
    "utc_now",
]
