"""Tests for local wake word detection."""

import pytest

from openjarvis.voice.permissions import VoicePermissionError
from openjarvis.voice.wake_word import WakeWordService


class MockMode:
    def __init__(self, mode_id: str):
        self.id = mode_id


class MockActiveMode:
    def __init__(self, mode_id: str):
        self.mode = MockMode(mode_id)


class MockModeRegistry:
    def __init__(self, mode_id: str = "default"):
        self.active = MockActiveMode(mode_id)

    def get_active_mode(self):
        return self.active


class MockVoiceService:
    def __init__(self):
        self.started = False
        self.explicit_approval = False

    def start_recording(self, explicit_approval: bool = False):
        self.started = True
        self.explicit_approval = explicit_approval
        return type(
            "MockSession",
            (),
            {"to_dict": lambda self: {"id": "mock_session", "status": "recording"}},
        )()


def test_wake_word_disabled_by_default():
    service = WakeWordService()
    assert not service.status()["enabled"]
    assert not service.status()["cloud_audio"]
    assert service.status()["local_only"]


def test_wake_word_enable_requires_explicit_approval():
    service = WakeWordService()
    with pytest.raises(VoicePermissionError):
        service.enable(explicit_approval=False)


def test_wake_word_enable():
    service = WakeWordService()
    service.enable(explicit_approval=True)
    assert service.status()["enabled"]


def test_wake_word_disabled_in_privacy_mode():
    registry = MockModeRegistry("privacy")
    service = WakeWordService(mode_registry=registry)
    assert service.status()["privacy_mode"]

    with pytest.raises(VoicePermissionError):
        service.enable(explicit_approval=True)


def test_wake_word_test_trigger_starts_recording():
    voice = MockVoiceService()
    service = WakeWordService(voice_service=voice)
    service.enable(explicit_approval=True)

    res = service.test_trigger(explicit_approval=True)
    assert res["status"] == "triggered"
    assert voice.started
    assert voice.explicit_approval


def test_wake_word_test_trigger_fails_if_disabled():
    voice = MockVoiceService()
    service = WakeWordService(voice_service=voice)

    with pytest.raises(VoicePermissionError):
        service.test_trigger(explicit_approval=True)
