"""Central registry for Siri workspace agent configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from openjarvis.agent_workspace.defaults import (
    DEFAULT_ACTIVE_AGENT_ID,
    DEFAULT_AGENT_CONFIGS,
)
from openjarvis.agent_workspace.models import (
    ActiveAgentState,
    AgentConfig,
    parse_permission_level,
)
from openjarvis.security.permissions import PermissionLevel, PermissionRequest

try:  # pragma: no cover - Python 3.11+ path
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


class AgentWorkspaceRegistry:
    """Configuration-backed registry for Siri workspace agents."""

    def __init__(
        self,
        configs: Iterable[dict[str, Any] | AgentConfig] | None = None,
        *,
        active_agent_id: str = DEFAULT_ACTIVE_AGENT_ID,
    ) -> None:
        source = configs if configs is not None else DEFAULT_AGENT_CONFIGS
        agents: dict[str, AgentConfig] = {}
        for item in source:
            config = (
                item
                if isinstance(item, AgentConfig)
                else AgentConfig.from_mapping(item)
            )
            if config.id in agents:
                raise ValueError(f"duplicate workspace agent id: {config.id}")
            agents[config.id] = config
        if not agents:
            raise ValueError("agent workspace registry requires at least one agent")
        self._agents = agents
        self._active_agent_id = (
            active_agent_id if active_agent_id in agents else next(iter(agents))
        )

    @classmethod
    def from_toml(cls, path: str | Path) -> "AgentWorkspaceRegistry":
        """Load a registry from a TOML file with ``[[agents]]`` entries."""
        data = tomllib.loads(Path(path).expanduser().read_text(encoding="utf-8"))
        return cls(
            data.get("agents", []),
            active_agent_id=data.get("active_agent_id", DEFAULT_ACTIVE_AGENT_ID),
        )

    def list_agents(self) -> list[AgentConfig]:
        return sorted(self._agents.values(), key=lambda agent: agent.id.lower())

    def get_agent(self, agent_id: str) -> AgentConfig:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"unknown workspace agent: {agent_id}") from exc

    def get_active_agent(self) -> ActiveAgentState:
        agent_id = self._active_agent_id
        if agent_id == DEFAULT_ACTIVE_AGENT_ID:
            try:
                from openjarvis.personalization.preferences import get_preferred_workspace
                pref = get_preferred_workspace()
                if pref in self._agents:
                    agent_id = pref
            except ImportError:
                pass
        agent = self.get_agent(agent_id)
        return ActiveAgentState(active_agent_id=agent.id, agent=agent)

    def switch_active_agent(self, agent_id: str) -> ActiveAgentState:
        agent = self.get_agent(agent_id)
        self._active_agent_id = agent.id
        return self.get_active_agent()

    def allowed_tools_for(self, agent_id: str) -> list[str]:
        return list(self.get_agent(agent_id).allowed_tools)

    def memory_scopes_for(self, agent_id: str) -> list[str]:
        return list(self.get_agent(agent_id).memory_scope)

    def permission_ceiling_for(self, agent_id: str) -> PermissionLevel:
        return self.get_agent(agent_id).permission_ceiling

    def tool_is_allowed(self, agent_id: str, tool_name: str) -> bool:
        tools = set(self.allowed_tools_for(agent_id))
        return "*" in tools or tool_name in tools

    def apply_to_permission_request(
        self,
        request: PermissionRequest,
        *,
        agent_id: str | None = None,
    ) -> PermissionRequest:
        """Return a request annotated with the agent permission ceiling."""
        resolved_agent_id = agent_id or request.agent_id or self._active_agent_id
        agent = self.get_agent(resolved_agent_id)
        request.agent_id = agent.id
        request.permission_ceiling = agent.permission_ceiling
        request.metadata.setdefault("agent_memory_scope", list(agent.memory_scope))
        request.metadata.setdefault("agent_allowed_tools", list(agent.allowed_tools))
        return request

    def validate_tool_request(self, agent_id: str, tool_name: str) -> tuple[bool, str]:
        """Check registry-level tool allow-list before permission classification."""
        if self.tool_is_allowed(agent_id, tool_name):
            return True, "tool allowed for agent"
        return False, f"tool '{tool_name}' is not allowed for agent '{agent_id}'"


def permission_ceiling_from_value(
    value: PermissionLevel | str | int,
) -> PermissionLevel:
    """Public helper for callers that need to parse config values."""
    return parse_permission_level(value)


__all__ = ["AgentWorkspaceRegistry", "permission_ceiling_from_value"]
