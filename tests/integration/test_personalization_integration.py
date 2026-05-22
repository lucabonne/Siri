from unittest.mock import MagicMock, patch

from openjarvis.desktop.focus import FocusResolver
from openjarvis.desktop.service import DesktopService
from openjarvis.desktop.sessions import DesktopSessionStore
from openjarvis.memory.service import MemoryService
from openjarvis.personalization.models import Preferences, Profile
from openjarvis.release.service import ReleaseHardeningService
from openjarvis.voice.wake_word import WakeWordService


def test_wake_word_respects_quiet_mode():
    with patch(
        "openjarvis.personalization.preferences.get_quiet_mode_preference",
        return_value=True
    ):
        service = WakeWordService()
        service._enabled = True
        status = service.status()
        assert status["enabled"] is False
        assert status["quiet_mode"] is True

def test_memory_weights_workspace_bias():
    with patch(
        "openjarvis.personalization.preferences.get_preferred_workspace",
        return_value="coding"
    ):
        with patch(
            "openjarvis.personalization.preferences.get_coding_vs_engineering",
            return_value="coding"
        ):
            service = MemoryService(db_path=":memory:")
            items = [{"score": 1.0, "tags": ["coding"], "memory_type": "note"}]
            service._apply_memory_weights(items)
            assert items[0]["score"] > 1.0  # Boosted by workspace bias

def test_agent_workspace_fallback():
    from openjarvis.agent_workspace.registry import AgentWorkspaceRegistry
    registry = AgentWorkspaceRegistry()
    mock_agent = MagicMock()
    mock_agent.id = "engineering"
    registry._agents = {"engineering": mock_agent}

    with patch(
        "openjarvis.personalization.preferences.get_preferred_workspace",
        return_value="unknown"
    ):
        with patch(
            "openjarvis.personalization.preferences.get_coding_vs_engineering",
            return_value="engineering"
        ):
            state = registry.get_active_agent()
            assert state.active_agent_id == "engineering"

def test_desktop_service_personalization_snapshot():
    service = DesktopService(
        focus_resolver=FocusResolver(),
        session_store=DesktopSessionStore()
    )
    with patch(
        "openjarvis.personalization.profiles.get_active_profile",
        return_value=Profile(id="test", name="Test", preferences=Preferences())
    ):
        snapshot = service._integration_snapshot(
            FocusResolver().focused_workspace(),
            privacy_mode=False
        )
        assert "personalization" in snapshot
        assert snapshot["personalization"]["available"] is True
        assert snapshot["personalization"]["active_profile_id"] == "test"

def test_release_service_includes_profile():
    service = ReleaseHardeningService()
    app_state = MagicMock()
    app_state.wake_word_service = WakeWordService()

    desktop_service = MagicMock()
    desktop_service.launcher_status.return_value.to_dict.return_value = {
        "backend_status": "ok",
        "frontend_status": "ok",
        "last_action": "test"
    }
    app_state.desktop_service = desktop_service

    with patch(
        "openjarvis.personalization.profiles.get_active_profile",
        return_value=Profile(id="prod", name="Prod", preferences=Preferences())
    ):
        snapshot = service.snapshot(app_state=app_state)
        assert snapshot.active_profile_summary.get("id") == "prod"
        assert "enabled" in snapshot.wake_status
