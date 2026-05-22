
from openjarvis.autonomy import autonomy_service
from openjarvis.autonomy.approvals import approval_manager
from openjarvis.autonomy.goals import goal_manager
from openjarvis.autonomy.planner import planner


def test_autonomy_execution_approval():
    goal_manager._goals.clear()
    planner._plans.clear()
    approval_manager._approvals.clear()

    goal = autonomy_service.create_goal("Test Approval", "Desc")
    plan = autonomy_service.generate_plan(goal.id)

    state = autonomy_service.start_plan(plan.id)
    assert state is not None

    if len(plan.steps) > 0:
        approval = autonomy_service.request_step_approval(
            plan.id, plan.steps[0].id, "Requires explicit approval"
        )
        assert approval is not None
        pending = approval_manager.list_pending_approvals()
        assert len(pending) > 0

        approval_manager.resolve_approval(approval.id, approved=True)
        pending_after = approval_manager.list_pending_approvals()
        assert len(pending_after) == 0
