"""Typed models for controlled autonomy Phase 1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True, slots=True)
class Goal:
    """User-created goal driving controlled autonomy."""
    id: str
    title: str
    description: str
    status: str = "pending"  # pending, in_progress, paused, completed, etc.
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Goal":
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            description=str(data.get("description", "")),
            status=str(data.get("status", "pending")),
            created_at=str(data.get("created_at", utc_now())),
            updated_at=str(data.get("updated_at", utc_now())),
            completed_at=data.get("completed_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True, slots=True)
class PlanStep:
    """A single step in an execution plan."""
    id: str
    title: str
    action_type: str
    description: str = ""
    status: str = "pending"  # pending, running, waiting_approval, completed, failed
    requires_approval: bool = False
    dependencies: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PlanStep":
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            action_type=str(data["action_type"]),
            description=str(data.get("description", "")),
            status=str(data.get("status", "pending")),
            requires_approval=bool(data.get("requires_approval", False)),
            dependencies=[str(d) for d in data.get("dependencies", [])],
            output=dict(data.get("output", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True, slots=True)
class Plan:
    """A multi-step plan to achieve a goal."""
    id: str
    goal_id: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Plan":
        return cls(
            id=str(data["id"]),
            goal_id=str(data["goal_id"]),
            steps=[PlanStep.from_mapping(s) for s in data.get("steps", [])],
            created_at=str(data.get("created_at", utc_now())),
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        return d

@dataclass(frozen=True, slots=True)
class ExecutionState:
    """The current execution state for a plan."""
    plan_id: str
    goal_id: str
    status: str = "idle" # idle, running, paused, stopped, completed
    current_step_id: str | None = None
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ExecutionState":
        return cls(
            plan_id=str(data["plan_id"]),
            goal_id=str(data["goal_id"]),
            status=str(data.get("status", "idle")),
            current_step_id=data.get("current_step_id"),
            updated_at=str(data.get("updated_at", utc_now())),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
