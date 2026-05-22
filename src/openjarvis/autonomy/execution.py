"""Execution engine for the autonomy layer."""

from typing import Optional

from openjarvis.autonomy.models import ExecutionState, Plan, utc_now


class ExecutionEngine:
    def __init__(self):
        self._states: dict[str, ExecutionState] = {}

    def start_execution(self, plan: Plan) -> ExecutionState:
        state = ExecutionState(
            plan_id=plan.id,
            goal_id=plan.goal_id,
            status="running",
            current_step_id=plan.steps[0].id if plan.steps else None
        )
        self._states[plan.id] = state
        return state

    def get_state(self, plan_id: str) -> Optional[ExecutionState]:
        return self._states.get(plan_id)

    def pause_execution(self, plan_id: str) -> Optional[ExecutionState]:
        state = self._states.get(plan_id)
        if state and state.status == "running":
            updated = ExecutionState(
                plan_id=state.plan_id,
                goal_id=state.goal_id,
                status="paused",
                current_step_id=state.current_step_id,
                updated_at=utc_now()
            )
            self._states[plan_id] = updated
            return updated
        return state

    def resume_execution(self, plan_id: str) -> Optional[ExecutionState]:
        state = self._states.get(plan_id)
        if state and state.status == "paused":
            updated = ExecutionState(
                plan_id=state.plan_id,
                goal_id=state.goal_id,
                status="running",
                current_step_id=state.current_step_id,
                updated_at=utc_now()
            )
            self._states[plan_id] = updated
            return updated
        return state

    def stop_execution(self, plan_id: str) -> Optional[ExecutionState]:
        state = self._states.get(plan_id)
        if state and state.status in ("running", "paused"):
            updated = ExecutionState(
                plan_id=state.plan_id,
                goal_id=state.goal_id,
                status="stopped",
                current_step_id=state.current_step_id,
                updated_at=utc_now()
            )
            self._states[plan_id] = updated
            return updated
        return state

execution_engine = ExecutionEngine()
