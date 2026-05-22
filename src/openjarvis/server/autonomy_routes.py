"""API routes for the autonomy layer."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openjarvis.autonomy import autonomy_service

autonomy_router = APIRouter(prefix="/v1/autonomy", tags=["autonomy"])

class CreateGoalRequest(BaseModel):
    title: str
    description: str

class ResolveApprovalRequest(BaseModel):
    approved: bool

@autonomy_router.post("/goals")
async def create_goal(req: CreateGoalRequest):
    goal = autonomy_service.create_goal(req.title, req.description)
    return goal.to_dict()

@autonomy_router.post("/goals/{goal_id}/plan")
async def generate_plan(goal_id: str):
    plan = autonomy_service.generate_plan(goal_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Goal not found")
    return plan.to_dict()

@autonomy_router.post("/plans/{plan_id}/start")
async def start_plan(plan_id: str):
    state = autonomy_service.start_plan(plan_id)
    if not state:
        raise HTTPException(status_code=404, detail="Plan not found")
    return state.to_dict()

@autonomy_router.post("/plans/{plan_id}/pause")
async def pause_plan(plan_id: str):
    state = autonomy_service.pause_plan(plan_id)
    if not state:
        raise HTTPException(status_code=404, detail="Plan not found")
    return state.to_dict()

@autonomy_router.post("/plans/{plan_id}/resume")
async def resume_plan(plan_id: str):
    state = autonomy_service.resume_plan(plan_id)
    if not state:
        raise HTTPException(status_code=404, detail="Plan not found")
    return state.to_dict()

@autonomy_router.post("/plans/{plan_id}/stop")
async def stop_plan(plan_id: str):
    state = autonomy_service.stop_plan(plan_id)
    if not state:
        raise HTTPException(status_code=404, detail="Plan not found")
    return state.to_dict()

@autonomy_router.get("/approvals")
async def list_approvals():
    from openjarvis.autonomy.approvals import approval_manager
    return [a.to_dict() for a in approval_manager.list_pending_approvals()]

@autonomy_router.post("/approvals/{approval_id}/resolve")
async def resolve_approval(approval_id: str, req: ResolveApprovalRequest):
    from openjarvis.autonomy.approvals import approval_manager
    res = approval_manager.resolve_approval(approval_id, req.approved)
    if not res:
        raise HTTPException(
            status_code=404, detail="Approval not found or already resolved"
        )
    return res.to_dict()
