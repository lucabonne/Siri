"""Local JSON state for startup and boot scheduling."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def default_state_dir() -> Path:
    return Path.home() / ".openjarvis" / "state"


def last_morning_briefing_path(state_dir: Path | None = None) -> Path:
    return (state_dir or default_state_dir()) / "last_morning_briefing.json"


def scheduler_state_path(state_dir: Path | None = None) -> Path:
    return (state_dir or default_state_dir()) / "scheduler_state.json"


@dataclass(slots=True)
class LastMorningBriefingState:
    last_briefing_at: str = ""
    last_briefing_date: str = ""
    briefing_id: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SchedulerState:
    enabled: bool = True
    last_launch_at: str = ""
    last_launch_date: str = ""
    launch_count: int = 0
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StartupStateStore:
    """Read and write startup scheduler state under ``~/.openjarvis/state``."""

    def __init__(self, state_dir: str | Path | None = None) -> None:
        self.state_dir = (
            Path(state_dir).expanduser() if state_dir else default_state_dir()
        )
        self.last_briefing_file = last_morning_briefing_path(self.state_dir)
        self.scheduler_file = scheduler_state_path(self.state_dir)

    def read_last_briefing(self) -> LastMorningBriefingState:
        data = self._read_json(self.last_briefing_file)
        return LastMorningBriefingState(
            last_briefing_at=str(data.get("last_briefing_at", "")),
            last_briefing_date=str(data.get("last_briefing_date", "")),
            briefing_id=str(data.get("briefing_id", "")),
            source=str(data.get("source", "")),
        )

    def write_last_briefing(
        self,
        *,
        timestamp: str,
        briefing_date: str,
        briefing_id: str = "",
        source: str = "",
    ) -> LastMorningBriefingState:
        state = LastMorningBriefingState(
            last_briefing_at=timestamp,
            last_briefing_date=briefing_date,
            briefing_id=briefing_id,
            source=source,
        )
        self._write_json(self.last_briefing_file, state.to_dict())
        return state

    def read_scheduler(self) -> SchedulerState:
        data = self._read_json(self.scheduler_file)
        tasks = data.get("tasks", {})
        return SchedulerState(
            enabled=bool(data.get("enabled", True)),
            last_launch_at=str(data.get("last_launch_at", "")),
            last_launch_date=str(data.get("last_launch_date", "")),
            launch_count=int(data.get("launch_count", 0) or 0),
            tasks=tasks if isinstance(tasks, dict) else {},
        )

    def write_scheduler(self, state: SchedulerState) -> SchedulerState:
        self._write_json(self.scheduler_file, state.to_dict())
        return state

    def record_launch(self, *, now: datetime) -> bool:
        """Record a process launch and return whether it is today's first one."""

        current = self.read_scheduler()
        today = now.date().isoformat()
        first_launch = current.last_launch_date != today
        current.last_launch_at = _isoformat_utc(now)
        current.last_launch_date = today
        current.launch_count += 1
        self.write_scheduler(current)
        return first_launch

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)


def _isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        return value.isoformat(timespec="seconds")
    return value.astimezone().isoformat(timespec="seconds")


__all__ = [
    "LastMorningBriefingState",
    "SchedulerState",
    "StartupStateStore",
    "default_state_dir",
    "last_morning_briefing_path",
    "scheduler_state_path",
]
