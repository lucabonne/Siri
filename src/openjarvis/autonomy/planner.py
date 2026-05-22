"""Planning logic for the autonomy layer."""

import uuid
from typing import Optional

from openjarvis.autonomy.models import Goal, Plan, PlanStep


class Planner:
    def __init__(self):
        self._plans: dict[str, Plan] = {}

    def create_plan_for_goal(self, goal: Goal) -> Plan:
        # Mock logic: generate a generic multi-step plan for the goal
        plan_id = str(uuid.uuid4())
        steps = [
            PlanStep(
                id=str(uuid.uuid4()),
                title="Analyze Goal",
                action_type="analysis",
                description=f"Analyze the goal: {goal.title}",
                requires_approval=False,
            ),
            PlanStep(
                id=str(uuid.uuid4()),
                title="Execute actions",
                action_type="execution",
                description="Execute the required actions",
                requires_approval=True,
            ),
            PlanStep(
                id=str(uuid.uuid4()),
                title="Verify results",
                action_type="verification",
                description="Verify the outcome of the goal",
                requires_approval=False,
            ),
        ]
        plan = Plan(id=plan_id, goal_id=goal.id, steps=steps)
        self._plans[plan_id] = plan
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self._plans.get(plan_id)

    def get_plan_by_goal(self, goal_id: str) -> Optional[Plan]:
        for plan in self._plans.values():
            if plan.goal_id == goal_id:
                return plan
        return None

planner = Planner()
