from .models import MissionControlDefaults, Preferences
from .profiles import get_active_profile


def get_active_preferences() -> Preferences:
    """Get preferences for the active profile, or system defaults if none active."""
    profile = get_active_profile()
    if profile:
        return profile.preferences
    return Preferences()


def get_preferred_workspace() -> str:
    """Get preferred workspace for the active profile."""
    return get_active_preferences().preferred_workspace


def get_coding_vs_engineering() -> str:
    """Get preference between coding and engineering tasks."""
    return get_active_preferences().coding_vs_engineering


def get_voice_interaction_enabled() -> bool:
    """Get whether voice interactions are enabled by default."""
    return get_active_preferences().voice_interaction


def get_wake_word_preference() -> bool:
    """Get whether wake word is enabled by default."""
    return get_active_preferences().wake_word_preference


def get_quiet_mode_preference() -> bool:
    """Get whether quiet mode is enabled by default."""
    return get_active_preferences().quiet_mode_preference


def get_mission_control_defaults() -> MissionControlDefaults:
    """Get defaults for Mission Control."""
    return get_active_preferences().mission_control_defaults
