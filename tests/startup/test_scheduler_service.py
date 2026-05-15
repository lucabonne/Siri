from __future__ import annotations

from datetime import datetime

from openjarvis.morning_briefing import MorningBriefingService, NewsItem
from openjarvis.startup.launchagent import LaunchAgentManager
from openjarvis.startup.models import LaunchAgentConfig
from openjarvis.startup.scheduler import StartupScheduler
from openjarvis.startup.service import StartupService
from openjarvis.startup.state import StartupStateStore


class FakeFetcher:
    def fetch(self, *, max_items: int = 12) -> list[NewsItem]:
        return [
            NewsItem(
                title="Local briefing item",
                summary="A compact item for startup tests.",
                source_url="https://example.test/startup",
                source_name="Example",
            )
        ]


def _service(tmp_path) -> StartupService:
    state = StartupStateStore(tmp_path / "state")
    briefing = MorningBriefingService(
        db_path=tmp_path / "briefing.db",
        news_fetcher=FakeFetcher(),
    )
    launch_agent = LaunchAgentManager(
        config=LaunchAgentConfig(
            label="com.openjarvis.test",
            program_arguments=["/bin/echo", "jarvis"],
        ),
        launch_agents_dir=tmp_path / "LaunchAgents",
    )
    return StartupService(
        state_store=state,
        launch_agent=launch_agent,
        scheduler=StartupScheduler(state),
        morning_briefing_service=briefing,
    )


def test_manual_trigger_stores_timestamp_and_prevents_duplicates(tmp_path) -> None:
    service = _service(tmp_path)
    now = datetime(2026, 5, 15, 8, 0, 0)

    first = service.trigger_morning_briefing(force=False, now=now)
    second = service.trigger_morning_briefing(force=False, now=now)
    status = service.status()

    assert first.triggered is True
    assert second.triggered is False
    assert second.duplicate_prevented is True
    assert status.scheduler.last_morning_briefing_date == "2026-05-15"
    assert status.scheduler.background_loop is False
    assert status.scheduler.telemetry_enabled is False


def test_startup_tasks_only_run_when_launchagent_is_installed(tmp_path) -> None:
    service = _service(tmp_path)
    now = datetime(2026, 5, 15, 8, 0, 0)

    assert service.run_startup_tasks(now=now) is None

    service.install_startup()
    result = service.run_startup_tasks(now=datetime(2026, 5, 16, 8, 0, 0))

    assert result is not None
    assert result.triggered is True
    assert service.status().launch_at_login is True
