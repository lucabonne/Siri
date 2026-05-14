from __future__ import annotations

import pytest

from openjarvis.agent_workspace import AgentWorkspaceRegistry
from openjarvis.security.permissions import PermissionLevel, PermissionRequest


def test_default_registry_contains_required_agents() -> None:
    registry = AgentWorkspaceRegistry()

    agent_ids = {agent.id for agent in registry.list_agents()}

    assert agent_ids == {
        "CAD",
        "coding",
        "engineering",
        "privacy",
        "research",
        "scheduler",
        "terminal",
        "vision",
    }


def test_agent_config_includes_routing_memory_and_permission_metadata() -> None:
    registry = AgentWorkspaceRegistry()
    privacy = registry.get_agent("privacy")

    assert privacy.permission_ceiling is PermissionLevel.READ_ONLY
    assert "project" in privacy.memory_scope
    assert privacy.routing.recommended_agent == "privacy"
    assert privacy.routing.fallback_agent == "engineering"
    assert "coding" in privacy.routing.multi_agent_compatibility


def test_switch_active_agent() -> None:
    registry = AgentWorkspaceRegistry()

    state = registry.switch_active_agent("terminal")

    assert state.active_agent_id == "terminal"
    assert registry.get_active_agent().agent.id == "terminal"


def test_unknown_agent_raises() -> None:
    registry = AgentWorkspaceRegistry()

    with pytest.raises(KeyError):
        registry.get_agent("unknown")


def test_registry_applies_permission_ceiling_to_request() -> None:
    registry = AgentWorkspaceRegistry()
    request = PermissionRequest(tool_name="file_read")

    updated = registry.apply_to_permission_request(request, agent_id="privacy")

    assert updated.agent_id == "privacy"
    assert updated.permission_ceiling is PermissionLevel.READ_ONLY
    assert updated.metadata["agent_memory_scope"] == [
        "project",
        "sources",
        "agent_runs",
    ]


def test_tool_allowlist_validation() -> None:
    registry = AgentWorkspaceRegistry()

    allowed, _ = registry.validate_tool_request("privacy", "file_read")
    denied, reason = registry.validate_tool_request("privacy", "shell_exec")

    assert allowed is True
    assert denied is False
    assert "not allowed" in reason
