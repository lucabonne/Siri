"""FastAPI routes for global Siri operating modes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from openjarvis.modes import ModeRegistry

logger = logging.getLogger(__name__)

mode_router = APIRouter(prefix="/v1/modes", tags=["modes"])


class SwitchModeRequest(BaseModel):
    mode_id: str


def get_mode_registry(request: Request) -> ModeRegistry:
    """Return the app-level mode registry, creating one lazily."""
    registry = getattr(request.app.state, "mode_registry", None)
    if registry is None:
        registry = ModeRegistry()
        request.app.state.mode_registry = registry
    return registry


@mode_router.get("")
async def list_modes(request: Request):
    """List configured Siri operating modes."""
    registry = get_mode_registry(request)
    active_id = registry.get_active_mode().active_mode_id
    return {
        "modes": [mode.to_dict() for mode in registry.list_modes()],
        "active_mode_id": active_id,
    }


@mode_router.get("/active")
async def get_active_mode(request: Request):
    """Return the current active operating mode."""
    registry = get_mode_registry(request)
    return registry.get_active_mode().to_dict()


@mode_router.post("/active")
async def switch_active_mode(req: SwitchModeRequest, request: Request):
    """Switch the active operating mode and persist it locally."""
    registry = get_mode_registry(request)
    try:
        state = registry.switch_mode(req.mode_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    workspace_registry = getattr(request.app.state, "agent_workspace_registry", None)
    if workspace_registry is not None:
        request.app.state.active_mode_preferred_agents = (
            state.mode.preferred_agents
        )

    return state.to_dict()


__all__ = ["get_mode_registry", "mode_router"]
