"""Startup service coordinating LaunchAgent and passive scheduler behavior."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from openjarvis.morning_briefing import MorningBriefingService, PrivacyModeError
from openjarvis.startup.launchagent import LaunchAgentManager
from openjarvis.startup.models import MorningBriefingRun, StartupStatus
from openjarvis.startup.scheduler import MORNING_BRIEFING_TASK_ID, StartupScheduler
from openjarvis.startup.state import StartupStateStore


class StartupService:
    """Local-only startup and boot scheduler facade."""

    def __init__(
        self,
        *,
        state_store: StartupStateStore | None = None,
        launch_agent: LaunchAgentManager | None = None,
        scheduler: StartupScheduler | None = None,
        morning_briefing_service: MorningBriefingService | None = None,
    ) -> None:
        self._state_store = state_store or StartupStateStore()
        self._launch_agent = launch_agent or LaunchAgentManager()
        self._scheduler = scheduler or StartupScheduler(self._state_store)
        self._morning_briefing_service = morning_briefing_service
        self._last_first_launch_today = False

    def status(self, *, privacy_mode: bool = False) -> StartupStatus:
        self._sync_latest_briefing_state()
        launch_agent = self._launch_agent.status()
        scheduler = self._scheduler.status(
            first_launch_today=self._last_first_launch_today,
        )
        return StartupStatus(
            launch_at_login=launch_agent.installed and launch_agent.valid,
            launch_agent=launch_agent,
            scheduler=scheduler,
            privacy_mode=privacy_mode,
            local_only=True,
            external_telemetry=False,
        )

    def install_startup(self) -> StartupStatus:
        self._launch_agent.install()
        return self.status()

    def remove_startup(self) -> StartupStatus:
        self._launch_agent.remove()
        return self.status()

    def record_launch(self, *, now: datetime | None = None) -> bool:
        first = self._state_store.record_launch(now=now or datetime.now())
        self._last_first_launch_today = first
        return first

    def run_startup_tasks(
        self,
        *,
        privacy_mode: bool = False,
        now: datetime | None = None,
    ) -> MorningBriefingRun | None:
        """Run due boot tasks once.

        The briefing task only runs automatically when launch-at-login is
        installed and valid. Manual launches still record first-launch state
        but do not unexpectedly fetch external news.
        """

        current = now or datetime.now()
        first_launch = self.record_launch(now=current)
        launch_status = self._launch_agent.status()
        if not first_launch or not (launch_status.installed and launch_status.valid):
            return None
        due_ids = {task.id for task in self._scheduler.due_tasks(now=current)}
        if MORNING_BRIEFING_TASK_ID not in due_ids:
            return None
        return self.trigger_morning_briefing(
            force=False,
            privacy_mode=privacy_mode,
            source="startup",
            now=current,
        )

    def trigger_morning_briefing(
        self,
        *,
        force: bool = False,
        privacy_mode: bool = False,
        source: str = "manual",
        now: datetime | None = None,
        location_name: str = "",
        max_items: int = 12,
        persist_memory: bool = True,
    ) -> MorningBriefingRun:
        current = now or datetime.now()
        last = self._state_store.read_last_briefing()
        today = current.date().isoformat()
        if not force and last.last_briefing_date == today:
            return MorningBriefingRun(
                triggered=False,
                duplicate_prevented=True,
                reason="morning briefing already generated today",
                last_morning_briefing_at=last.last_briefing_at,
                briefing=None,
            )

        briefing_service = self._require_morning_briefing_service()
        try:
            briefing = briefing_service.regenerate_briefing(
                location_name=location_name,
                max_items=max(1, min(max_items, 50)),
                privacy_mode=privacy_mode,
                persist_memory=persist_memory and not privacy_mode,
                now=current,
            )
        except PrivacyModeError:
            if not force:
                raise
            cached = briefing_service.latest_briefing()
            if cached is None:
                raise
            briefing = cached

        stored = self._state_store.write_last_briefing(
            timestamp=briefing.generated_at,
            briefing_date=briefing.briefing_date,
            briefing_id=briefing.id,
            source=source,
        )
        self._record_task_run(MORNING_BRIEFING_TASK_ID, briefing.generated_at)
        return MorningBriefingRun(
            triggered=True,
            duplicate_prevented=False,
            reason="generated",
            last_morning_briefing_at=stored.last_briefing_at,
            briefing=briefing.to_dict(),
        )

    def _record_task_run(self, task_id: str, timestamp: str) -> None:
        scheduler_state = self._state_store.read_scheduler()
        task = scheduler_state.tasks.get(task_id, {})
        task["last_run_at"] = timestamp
        scheduler_state.tasks[task_id] = task
        self._state_store.write_scheduler(scheduler_state)

    def _require_morning_briefing_service(self) -> MorningBriefingService:
        if self._morning_briefing_service is None:
            self._morning_briefing_service = MorningBriefingService()
        return self._morning_briefing_service

    def _sync_latest_briefing_state(self) -> None:
        if self._morning_briefing_service is None:
            return
        try:
            latest = self._morning_briefing_service.latest_briefing()
        except Exception:
            return
        if latest is None:
            return
        current = self._state_store.read_last_briefing()
        if current.last_briefing_at == latest.generated_at:
            return
        self._state_store.write_last_briefing(
            timestamp=latest.generated_at,
            briefing_date=latest.briefing_date,
            briefing_id=latest.id,
            source=str(latest.metadata.get("startup_source") or "morning_briefing"),
        )


def startup_payload(status: StartupStatus) -> dict[str, Any]:
    data = status.to_dict()
    data["privacy"] = {
        "external_startup_telemetry": False,
        "local_only_scheduling": True,
    }
    return data


__all__ = ["StartupService", "startup_payload"]
