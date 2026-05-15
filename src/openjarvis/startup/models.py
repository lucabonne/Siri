"""Typed models for local startup and passive boot scheduling."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class LaunchAgentConfig:
    """Configuration used to generate Siri's macOS LaunchAgent plist."""

    label: str = "com.openjarvis.siri"
    program_arguments: list[str] = field(default_factory=list)
    run_at_load: bool = True
    keep_alive: bool = False
    standard_out_path: str = "/tmp/openjarvis.siri.stdout.log"
    standard_error_path: str = "/tmp/openjarvis.siri.stderr.log"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LaunchAgentStatus:
    """Current LaunchAgent installation state."""

    supported: bool
    installed: bool
    valid: bool
    label: str
    plist_path: str
    expected_program_arguments: list[str]
    installed_program_arguments: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScheduledTask:
    """A passive scheduled task descriptor.

    Phase 1 evaluates these descriptors on process start or explicit API calls.
    It does not start a polling loop.
    """

    id: str
    task_type: str
    enabled: bool = True
    local_time: str = "07:30"
    once_per_day: bool = True
    last_run_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SchedulerStatus:
    """Status for the lightweight passive startup scheduler."""

    enabled: bool
    passive_only: bool
    background_loop: bool
    local_only: bool
    telemetry_enabled: bool
    first_launch_today: bool
    last_launch_date: str
    last_morning_briefing_at: str
    last_morning_briefing_date: str
    due_tasks: list[str]
    tasks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MorningBriefingRun:
    """Result of a startup/manual morning briefing trigger."""

    triggered: bool
    duplicate_prevented: bool
    reason: str
    last_morning_briefing_at: str
    briefing: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StartupStatus:
    """Combined startup, scheduler, and privacy status for Mission Control."""

    launch_at_login: bool
    launch_agent: LaunchAgentStatus
    scheduler: SchedulerStatus
    privacy_mode: bool
    local_only: bool = True
    external_telemetry: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["launch_agent"] = self.launch_agent.to_dict()
        data["scheduler"] = self.scheduler.to_dict()
        return data


__all__ = [
    "LaunchAgentConfig",
    "LaunchAgentStatus",
    "MorningBriefingRun",
    "ScheduledTask",
    "SchedulerStatus",
    "StartupStatus",
]
