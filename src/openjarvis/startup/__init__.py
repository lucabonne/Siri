"""Startup and passive boot scheduling for OpenJarvis/Siri."""

from openjarvis.startup.launchagent import LaunchAgentManager
from openjarvis.startup.models import (
    LaunchAgentConfig,
    LaunchAgentStatus,
    MorningBriefingRun,
    ScheduledTask,
    SchedulerStatus,
    StartupStatus,
)


def __getattr__(name: str):
    if name == "StartupScheduler":
        from openjarvis.startup.scheduler import StartupScheduler

        return StartupScheduler
    if name == "StartupService":
        from openjarvis.startup.service import StartupService

        return StartupService
    if name == "StartupStateStore":
        from openjarvis.startup.state import StartupStateStore

        return StartupStateStore
    raise AttributeError(name)

__all__ = [
    "LaunchAgentConfig",
    "LaunchAgentManager",
    "LaunchAgentStatus",
    "MorningBriefingRun",
    "ScheduledTask",
    "SchedulerStatus",
    "StartupScheduler",
    "StartupService",
    "StartupStateStore",
    "StartupStatus",
]
