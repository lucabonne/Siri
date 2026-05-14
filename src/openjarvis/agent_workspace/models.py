"""Typed models for the Siri multi-agent workspace."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from openjarvis.security.permissions import PermissionLevel


def parse_permission_level(value: PermissionLevel | str | int) -> PermissionLevel:
    """Normalize a permission ceiling from config input."""
    if isinstance(value, PermissionLevel):
        return value
    if isinstance(value, int):
        return PermissionLevel(value)
    normalized = str(value).strip().upper()
    if normalized.isdigit():
        return PermissionLevel(int(normalized))
    return PermissionLevel[normalized]


@dataclass(frozen=True, slots=True)
class AgentRoutingMetadata:
    """Orchestrator routing hints for a workspace agent."""

    task_classification: list[str]
    recommended_agent: str
    fallback_agent: str
    multi_agent_compatibility: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AgentRoutingMetadata":
        return cls(
            task_classification=list(data.get("task_classification", [])),
            recommended_agent=str(data.get("recommended_agent", "")),
            fallback_agent=str(data.get("fallback_agent", "")),
            multi_agent_compatibility=list(
                data.get("multi_agent_compatibility", [])
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Configuration for one Siri workspace agent."""

    id: str
    display_name: str
    description: str
    allowed_tools: list[str]
    memory_scope: list[str]
    permission_ceiling: PermissionLevel
    preferred_model: str
    personality_mode: str
    output_style: str
    routing: AgentRoutingMetadata

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AgentConfig":
        routing = data.get("routing", {})
        return cls(
            id=str(data["id"]),
            display_name=str(data["display_name"]),
            description=str(data["description"]),
            allowed_tools=list(data.get("allowed_tools", [])),
            memory_scope=list(data.get("memory_scope", [])),
            permission_ceiling=parse_permission_level(
                data.get("permission_ceiling", "READ_ONLY")
            ),
            preferred_model=str(data.get("preferred_model", "")),
            personality_mode=str(data.get("personality_mode", "")),
            output_style=str(data.get("output_style", "")),
            routing=AgentRoutingMetadata.from_mapping(routing),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["permission_ceiling"] = self.permission_ceiling.name
        return data


@dataclass(frozen=True, slots=True)
class ActiveAgentState:
    """Current active workspace agent response payload."""

    active_agent_id: str
    agent: AgentConfig

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_agent_id": self.active_agent_id,
            "agent": self.agent.to_dict(),
        }


__all__ = [
    "ActiveAgentState",
    "AgentConfig",
    "AgentRoutingMetadata",
    "parse_permission_level",
]
