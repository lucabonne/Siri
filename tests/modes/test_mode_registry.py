from __future__ import annotations

import json

import pytest

from openjarvis.modes import ModeRegistry


def test_default_registry_contains_required_modes(tmp_path) -> None:
    registry = ModeRegistry(state_path=tmp_path / "current_mode.json", persist=False)

    mode_ids = {mode.id for mode in registry.list_modes()}

    assert mode_ids == {
        "coding",
        "creative",
        "engineering",
        "focus",
        "privacy",
        "quiet",
        "research",
    }


def test_mode_config_includes_behavior_policy_and_ui_metadata(tmp_path) -> None:
    registry = ModeRegistry(state_path=tmp_path / "current_mode.json", persist=False)
    privacy = registry.get_mode("privacy")

    assert privacy.verbosity_level == "balanced"
    assert privacy.proactive_level == "off"
    assert privacy.remote_mcp_disabled is True
    assert privacy.cloud_apis_disabled is True
    assert privacy.localhost_only_network is True
    assert "privacy" in privacy.preferred_agents
    assert privacy.memory_behavior["write"] == "local_only"
    assert privacy.ui_theme_metadata["icon"] == "shield"
    assert privacy.notification_behavior["level"] == "security_only"
    assert privacy.voice_capture_behavior["activation"] == "push_to_talk_only"
    assert privacy.voice_capture_behavior["requires_explicit_approval"] is True
    assert privacy.voice_requires_explicit_approval is True


def test_switch_mode_persists_current_mode(tmp_path) -> None:
    state_path = tmp_path / "current_mode.json"
    registry = ModeRegistry(state_path=state_path)

    state = registry.switch_mode("coding")

    assert state.active_mode_id == "coding"
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["active_mode_id"] == "coding"

    restored = ModeRegistry(state_path=state_path)
    assert restored.get_active_mode().active_mode_id == "coding"


def test_unknown_mode_raises(tmp_path) -> None:
    registry = ModeRegistry(state_path=tmp_path / "current_mode.json", persist=False)

    with pytest.raises(KeyError):
        registry.get_mode("unknown")
