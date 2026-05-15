"""Passive boot scheduler for local startup tasks."""

from __future__ import annotations

from datetime import datetime
from datetime import time as dt_time

from openjarvis.startup.models import ScheduledTask, SchedulerStatus
from openjarvis.startup.state import StartupStateStore

MORNING_BRIEFING_TASK_ID = "morning_briefing"


def default_tasks() -> list[ScheduledTask]:
    return [
        ScheduledTask(
            id=MORNING_BRIEFING_TASK_ID,
            task_type="morning_briefing",
            local_time="07:30",
            once_per_day=True,
            metadata={
                "notifications": False,
                "autonomous_loop": False,
                "local_only": True,
            },
        )
    ]


class StartupScheduler:
    """Evaluate due startup tasks without polling or background execution."""

    def __init__(self, state_store: StartupStateStore | None = None) -> None:
        self._state_store = state_store or StartupStateStore()

    def tasks(self) -> list[ScheduledTask]:
        state = self._state_store.read_scheduler()
        configured = state.tasks
        tasks: list[ScheduledTask] = []
        for task in default_tasks():
            saved = configured.get(task.id, {})
            tasks.append(
                ScheduledTask(
                    id=task.id,
                    task_type=str(saved.get("task_type", task.task_type)),
                    enabled=bool(saved.get("enabled", task.enabled)),
                    local_time=str(saved.get("local_time", task.local_time)),
                    once_per_day=bool(saved.get("once_per_day", task.once_per_day)),
                    last_run_at=str(saved.get("last_run_at", task.last_run_at)),
                    metadata={
                        **task.metadata,
                        **(
                            saved.get("metadata", {})
                            if isinstance(saved.get("metadata", {}), dict)
                            else {}
                        ),
                    },
                )
            )
        return tasks

    def due_tasks(self, *, now: datetime | None = None) -> list[ScheduledTask]:
        current = now or datetime.now()
        scheduler_state = self._state_store.read_scheduler()
        if not scheduler_state.enabled:
            return []

        last_briefing = self._state_store.read_last_briefing()
        due: list[ScheduledTask] = []
        for task in self.tasks():
            if not task.enabled:
                continue
            if task.id == MORNING_BRIEFING_TASK_ID:
                if task.once_per_day and (
                    last_briefing.last_briefing_date == current.date().isoformat()
                ):
                    continue
                if current.time() >= _parse_local_time(task.local_time):
                    due.append(task)
        return due

    def status(
        self,
        *,
        now: datetime | None = None,
        first_launch_today: bool = False,
    ) -> SchedulerStatus:
        current = now or datetime.now()
        scheduler_state = self._state_store.read_scheduler()
        last_briefing = self._state_store.read_last_briefing()
        due = self.due_tasks(now=current)
        task_dicts = []
        for task in self.tasks():
            data = task.to_dict()
            if task.id == MORNING_BRIEFING_TASK_ID:
                data["due"] = any(item.id == task.id for item in due)
            task_dicts.append(data)
        return SchedulerStatus(
            enabled=scheduler_state.enabled,
            passive_only=True,
            background_loop=False,
            local_only=True,
            telemetry_enabled=False,
            first_launch_today=first_launch_today,
            last_launch_date=scheduler_state.last_launch_date,
            last_morning_briefing_at=last_briefing.last_briefing_at,
            last_morning_briefing_date=last_briefing.last_briefing_date,
            due_tasks=[task.id for task in due],
            tasks=task_dicts,
        )


def _parse_local_time(value: str) -> dt_time:
    try:
        hour, minute = [int(part) for part in value.split(":", 1)]
        return dt_time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        return dt_time(hour=7, minute=30)


__all__ = ["MORNING_BRIEFING_TASK_ID", "StartupScheduler", "default_tasks"]
