from typing import List, Optional

from .models import Routines
from .profiles import get_active_profile


def get_active_routines() -> Routines:
    """Get routines for the active profile, or system defaults if none active."""
    profile = get_active_profile()
    if profile:
        return profile.routines
    return Routines()


def get_morning_briefing_enabled() -> bool:
    """Check if morning briefing is enabled."""
    return get_active_routines().morning_briefing_enabled


def get_morning_briefing_time() -> Optional[str]:
    """Get preferred time for morning briefing."""
    return get_active_routines().morning_briefing_time


def get_auto_start_workflows() -> List[str]:
    """Get list of workflows to auto-start."""
    return get_active_routines().auto_start_workflows
