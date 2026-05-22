
from openjarvis.autonomy import autonomy_service
from openjarvis.autonomy.goals import goal_manager
from openjarvis.autonomy.planner import planner


def test_autonomy_lifecycle():
    goal_manager._goals.clear()
    planner._plans.clear()

    # 1. Create a goal
    goal = autonomy_service.create_goal("Test Goal", "Description of test goal")
    assert goal.title == "Test Goal"

    # 2. Generate a plan
    plan = autonomy_service.generate_plan(goal.id)
    assert plan is not None
    assert plan.goal_id == goal.id

    # 3. Start execution
    state = autonomy_service.start_plan(plan.id)
    assert state.plan_id == plan.id

    # Pause
    state = autonomy_service.pause_plan(plan.id)
    assert state.status == "paused"

    # Resume
    state = autonomy_service.resume_plan(plan.id)
    assert state.status in ("in_progress", "running", "idle")

    # Stop
    state = autonomy_service.stop_plan(plan.id)
    assert state is not None
