from __future__ import annotations

from pathlib import Path

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.hotkeys import (
    GlobalVoiceHotkeyService,
    HotkeyBinding,
    HotkeyPermissionError,
    NullHotkeyListener,
)
from openjarvis.modes import ModeRegistry
from openjarvis.security.permissions import PermissionMiddleware


class FakeVoiceService:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.recording = False

    def start_recording(self, **kwargs):
        assert kwargs["explicit_approval"] is True
        self.started += 1
        self.recording = True
        return {"status": "recording"}

    def stop_recording(self):
        self.stopped += 1
        self.recording = False
        return {"status": "recorded"}

    def status(self):
        return {
            "recording": self.recording,
            "active_agent_id": "coding",
            "wake_word_enabled": False,
            "passive_listening": False,
        }


class FakeTTSService:
    def status(self):
        return {"speaking": False, "autonomous_speech": False}


def make_service(tmp_path: Path, *, mode: str = "focus"):
    mode_registry = ModeRegistry(
        state_path=tmp_path / "current_mode.json",
        persist=False,
    )
    mode_registry.switch_mode(mode)
    voice = FakeVoiceService()
    service = GlobalVoiceHotkeyService(
        config=JarvisConfig(),
        voice_service=voice,
        tts_service=FakeTTSService(),
        permission_middleware=PermissionMiddleware(
            audit_log_path=tmp_path / "permissions.log",
            mode_registry=mode_registry,
        ),
        mode_registry=mode_registry,
        listener=NullHotkeyListener(),
    )
    return service, voice


def test_enable_exposes_safe_status(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)

    status = service.enable(explicit_approval=True)

    assert status["enabled"] is True
    assert status["effective_enabled"] is True
    assert status["listener_running"] is True
    assert status["wake_word_enabled"] is False
    assert status["background_transcription"] is False
    assert status["always_listening"] is False
    assert status["binding"]["display_name"] == "Fn"
    assert status["binding"]["fallback_display_name"] == "Ctrl+Space"


def test_enable_requires_explicit_approval(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)

    with pytest.raises(HotkeyPermissionError):
        service.enable(explicit_approval=False)


def test_press_release_controls_voice_capture(tmp_path: Path) -> None:
    service, voice = make_service(tmp_path)
    service.enable(explicit_approval=True)

    service.handle_press("Fn")
    assert voice.started == 1
    assert service.status()["active"] is True

    service.handle_release("Fn")
    assert voice.stopped == 1
    assert service.status()["active"] is False
    assert service.status()["last_trigger"]["phase"] == "release"


def test_privacy_mode_disables_listener(tmp_path: Path) -> None:
    service, voice = make_service(tmp_path, mode="privacy")

    with pytest.raises(HotkeyPermissionError):
        service.enable(explicit_approval=True)

    status = service.status()
    assert status["privacy_mode"] is True
    assert status["effective_enabled"] is False
    service.handle_press("Fn")
    assert voice.started == 0


def test_test_trigger_does_not_open_microphone(tmp_path: Path) -> None:
    service, voice = make_service(tmp_path)

    result = service.test_trigger(explicit_approval=True)

    assert result["trigger"]["test"] is True
    assert result["trigger"]["phase"] == "tested"
    assert voice.started == 0


def test_current_binding_can_be_configured(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    binding = HotkeyBinding(
        kind="hotkey_hold",
        keys=["cmd", "space"],
        fallback_keys=["ctrl", "space"],
        display_name="Cmd+Space",
        fallback_display_name="Ctrl+Space",
    )

    service.enable(binding=binding, explicit_approval=True)

    assert service.current_binding()["display_name"] == "Cmd+Space"
