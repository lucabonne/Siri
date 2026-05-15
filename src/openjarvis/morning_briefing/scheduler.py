"""Simple scheduler abstraction for morning briefings.

Phase 1 deliberately avoids LaunchAgent, notifications, and background work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from datetime import time as dt_time


@dataclass(slots=True)
class BriefingSchedule:
    enabled: bool = True
    local_time: str = "07:30"
    timezone: str = "local"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class MorningBriefingScheduler:
    """Policy object that decides whether a briefing is due."""

    def __init__(self, schedule: BriefingSchedule | None = None) -> None:
        self.schedule = schedule or BriefingSchedule()

    def is_due(
        self,
        *,
        latest_briefing_date: str = "",
        now: datetime | None = None,
    ) -> bool:
        if not self.schedule.enabled:
            return False
        current = now or datetime.now()
        if latest_briefing_date == current.date().isoformat():
            return False
        try:
            hour, minute = [
                int(part) for part in self.schedule.local_time.split(":", 1)
            ]
            scheduled = dt_time(hour=hour, minute=minute)
        except (TypeError, ValueError):
            scheduled = dt_time(hour=7, minute=30)
        return current.time() >= scheduled

    def status(self, *, latest_briefing_date: str = "") -> dict[str, object]:
        data = self.schedule.to_dict()
        data["latest_briefing_date"] = latest_briefing_date
        data["phase"] = "abstraction_only"
        data["background_notifications"] = False
        data["launch_agent_installed"] = False
        data["due"] = self.is_due(latest_briefing_date=latest_briefing_date)
        return data


__all__ = ["BriefingSchedule", "MorningBriefingScheduler"]
