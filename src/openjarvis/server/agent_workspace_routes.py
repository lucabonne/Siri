"""FastAPI routes for the Siri agent workspace registry."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from openjarvis.agent_workspace import AgentWorkspaceRegistry

logger = logging.getLogger(__name__)

agent_workspace_router = APIRouter(
    prefix="/v1/agent-workspace",
    tags=["agent-workspace"],
)


class SwitchActiveAgentRequest(BaseModel):
    agent_id: str


def get_agent_workspace_registry(request: Request) -> AgentWorkspaceRegistry:
    """Return the app-level workspace registry, creating one lazily."""
    registry = getattr(request.app.state, "agent_workspace_registry", None)
    if registry is None:
        registry = AgentWorkspaceRegistry()
        active_id = getattr(request.app.state, "active_workspace_agent_id", None)
        if active_id:
            try:
                registry.switch_active_agent(active_id)
            except KeyError:
                logger.debug("Ignoring unknown active workspace agent: %s", active_id)
        request.app.state.agent_workspace_registry = registry
    return registry


@agent_workspace_router.get("/agents")
async def list_workspace_agents(request: Request):
    """List configured Siri workspace agents."""
    registry = get_agent_workspace_registry(request)
    active_id = registry.get_active_agent().active_agent_id
    return {
        "agents": [agent.to_dict() for agent in registry.list_agents()],
        "active_agent_id": active_id,
    }


@agent_workspace_router.get("/agents/{agent_id}")
async def get_workspace_agent(agent_id: str, request: Request):
    """Return one workspace agent config."""
    registry = get_agent_workspace_registry(request)
    try:
        return {"agent": registry.get_agent(agent_id).to_dict()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@agent_workspace_router.get("/active-agent")
async def get_active_workspace_agent(request: Request):
    """Return the current active workspace agent."""
    registry = get_agent_workspace_registry(request)
    return registry.get_active_agent().to_dict()


@agent_workspace_router.post("/active-agent")
async def switch_active_workspace_agent(
    req: SwitchActiveAgentRequest,
    request: Request,
):
    """Switch the active workspace agent."""
    registry = get_agent_workspace_registry(request)
    try:
        state = registry.switch_active_agent(req.agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    request.app.state.active_workspace_agent_id = state.active_agent_id
    return state.to_dict()


__all__ = ["agent_workspace_router", "get_agent_workspace_registry"]
