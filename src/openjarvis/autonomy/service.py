"""Autonomy service coordinating goals, plans, and execution."""

from typing import Optional

from openjarvis.autonomy.approvals import ApprovalRequest, approval_manager
from openjarvis.autonomy.execution import execution_engine
from openjarvis.autonomy.goals import goal_manager
from openjarvis.autonomy.memory import autonomy_memory
from openjarvis.autonomy.models import ExecutionState, Goal, Plan
from openjarvis.autonomy.planner import planner


class AutonomyService:
    def create_goal(self, title: str, description: str) -> Goal:
        goal = goal_manager.create_goal(title, description)
        autonomy_memory.record_goal_creation(goal.id, title)
        return goal

    def generate_plan(self, goal_id: str) -> Optional[Plan]:
        goal = goal_manager.get_goal(goal_id)
        if not goal:
            return None
        return planner.create_plan_for_goal(goal)

    def start_plan(self, plan_id: str) -> Optional[ExecutionState]:
        plan = planner.get_plan(plan_id)
        if not plan:
            return None
        goal_manager.update_goal_status(plan.goal_id, "in_progress")
        return execution_engine.start_execution(plan)

    def pause_plan(self, plan_id: str) -> Optional[ExecutionState]:
        state = execution_engine.pause_execution(plan_id)
        if state:
            goal_manager.update_goal_status(state.goal_id, "paused")
        return state

    def resume_plan(self, plan_id: str) -> Optional[ExecutionState]:
        state = execution_engine.resume_execution(plan_id)
        if state:
            goal_manager.update_goal_status(state.goal_id, "in_progress")
        return state

    def stop_plan(self, plan_id: str) -> Optional[ExecutionState]:
        state = execution_engine.stop_execution(plan_id)
        if state:
            goal_manager.update_goal_status(state.goal_id, "cancelled")
        return state

    def request_step_approval(
        self, plan_id: str, step_id: str, reason: str
    ) -> ApprovalRequest:
        return approval_manager.request_approval(plan_id, step_id, reason)

autonomy_service = AutonomyService()
