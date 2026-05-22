import tempfile
from pathlib import Path

import pytest

import openjarvis.personalization.profiles as profiles_module
from openjarvis.personalization.memory_weights import (
    get_weight_for_memory_type,
)
from openjarvis.personalization.models import (
    MemoryWeights,
    Preferences,
    Profile,
    Routines,
)
from openjarvis.personalization.preferences import (
    get_active_preferences,
    get_preferred_workspace,
    get_wake_word_preference,
)


@pytest.fixture
def temp_profile_env(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        temp_dir = Path(d)
        profiles_dir = temp_dir / "profiles"
        active_file = temp_dir / "active_profile.json"

        monkeypatch.setattr(profiles_module, "PROFILES_DIR", profiles_dir)
        monkeypatch.setattr(profiles_module, "ACTIVE_PROFILE_FILE", active_file)

        profiles_module.init_profile_storage()
        yield temp_dir

def test_models_defaults():
    pref = Preferences()
    assert pref.preferred_workspace == "coding"
    assert pref.voice_interaction is False

    routines = Routines()
    assert routines.morning_briefing_enabled is False

    weights = MemoryWeights()
    assert weights.project_context == 1.0

def test_profile_crud(temp_profile_env):
    # Create new profile
    p1 = Profile(id="user1", name="User One")
    profiles_module.save_profile(p1)

    all_profiles = profiles_module.list_profiles()
    assert len(all_profiles) == 1
    assert all_profiles[0].id == "user1"

    # Set active profile
    success = profiles_module.set_active_profile_id("user1")
    assert success is True

    # Get active profile
    active = profiles_module.get_active_profile()
    assert active is not None
    assert active.id == "user1"

    # Save preferences to user1
    active.preferences.preferred_workspace = "coding"
    active.preferences.voice_interaction = False
    profiles_module.save_profile(active)

    # Reload active profile to check preferences
    active_reloaded = profiles_module.get_active_profile()
    assert active_reloaded.preferences.preferred_workspace == "coding"
    assert active_reloaded.preferences.voice_interaction is False

def test_preferences_helpers(temp_profile_env):
    p = Profile(id="test", name="Test Profile")
    p.preferences.preferred_workspace = "engineering"
    p.preferences.wake_word_preference = False
    profiles_module.save_profile(p)
    profiles_module.set_active_profile_id("test")

    assert get_active_preferences().preferred_workspace == "engineering"
    assert get_preferred_workspace() == "engineering"
    assert get_wake_word_preference() is False

def test_memory_weights_helpers(temp_profile_env):
    p = Profile(id="test_weights", name="Test Weights Profile")
    p.memory_weights.project_context = 2.0
    p.memory_weights.user_facts = 3.0
    profiles_module.save_profile(p)
    profiles_module.set_active_profile_id("test_weights")

    assert get_weight_for_memory_type("project_context") == 2.0
    assert get_weight_for_memory_type("user_fact") == 3.0
    assert get_weight_for_memory_type("unknown") == 1.0
