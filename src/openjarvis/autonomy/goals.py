"""Goal management for the autonomy layer."""

import uuid
from typing import Optional

from openjarvis.autonomy.models import Goal, utc_now


class GoalManager:
    def __init__(self):
        # In-memory store for Phase 1. Real integration uses sqlite/memory.py.
        self._goals: dict[str, Goal] = {}

    def create_goal(self, title: str, description: str) -> Goal:
        goal_id = str(uuid.uuid4())
        goal = Goal(id=goal_id, title=title, description=description)
        self._goals[goal_id] = goal
        return goal

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self._goals.get(goal_id)

    def list_goals(self) -> list[Goal]:
        return list(self._goals.values())

    def update_goal_status(self, goal_id: str, status: str) -> Optional[Goal]:
        goal = self._goals.get(goal_id)
        if not goal:
            return None

        updates = {"status": status, "updated_at": utc_now()}
        if status in ("completed", "failed", "cancelled"):
            updates["completed_at"] = utc_now()

        updated_goal = Goal(
            id=goal.id,
            title=goal.title,
            description=goal.description,
            created_at=goal.created_at,
            **updates
        )
        self._goals[goal_id] = updated_goal
        return updated_goal

goal_manager = GoalManager()
