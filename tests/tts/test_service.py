from __future__ import annotations

from pathlib import Path

import pytest

from openjarvis.modes import ModeRegistry
from openjarvis.tts import LocalTTSService, TTSPermissionError
from openjarvis.tts.models import TTSVoice


class FakeHandle:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self):
        return None if not self.terminated else 0

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout=None) -> None:
        return None


class FakeEngine:
    engine_id = "fake_local"

    def __init__(self) -> None:
        self.spoken: list[tuple[str, str]] = []
        self.handle = FakeHandle()

    def available(self) -> bool:
        return True

    def voices(self) -> list[TTSVoice]:
        return [
            TTSVoice(
                id="voice-a",
                name="Voice A",
                engine=self.engine_id,
                locale="en_US",
            )
        ]

    def speak(self, text: str, *, voice_id: str = "", speed: float = 1.0):
        self.spoken.append((text, voice_id))
        return self.handle

    def stop(self, handle) -> None:
        handle.terminate()


class FakeDecision:
    action = "allow"
    level = type("Level", (), {"name": "SAFE_ACTION"})()
    denied = False
    requires_confirmation = False
    reason = "safe action tool"
    matched_pattern = None


class FakePermissionMiddleware:
    def __init__(self) -> None:
        self.requests = []

    def check(self, request):
        self.requests.append(request)
        return FakeDecision()


def test_tts_speaks_with_local_engine_and_stops() -> None:
    engine = FakeEngine()
    permissions = FakePermissionMiddleware()
    service = LocalTTSService(
        engines=[engine],
        permission_middleware=permissions,
    )

    speech = service.speak("Hello from local Siri.", voice_id="voice-a")

    assert speech.status == "speaking"
    assert speech.local_only is True
    assert speech.autonomous_speech is False
    assert engine.spoken == [("Hello from local Siri.", "voice-a")]
    assert permissions.requests[0].arguments["local_only"] is True
    assert service.status()["speaking"] is True

    stopped = service.stop()

    assert stopped is not None
    assert stopped.status == "stopped"
    assert service.status()["speaking"] is False


def test_tts_blocks_autonomous_speech() -> None:
    service = LocalTTSService(
        engines=[FakeEngine()],
        permission_middleware=FakePermissionMiddleware(),
    )

    with pytest.raises(TTSPermissionError):
        service.speak("Do not speak on your own.", user_triggered=False)


def test_quiet_mode_disables_speech_by_default(tmp_path: Path) -> None:
    mode_registry = ModeRegistry(
        state_path=tmp_path / "current_mode.json",
        persist=False,
    )
    mode_registry.switch_mode("quiet")
    service = LocalTTSService(
        engines=[FakeEngine()],
        permission_middleware=FakePermissionMiddleware(),
        mode_registry=mode_registry,
    )

    with pytest.raises(TTSPermissionError):
        service.speak("Quiet mode should block this.")

    speech = service.speak("Explicit test phrase.", allow_quiet=True)
    assert speech.status == "speaking"
    assert service.status()["muted"] is True


def test_focus_mode_truncates_long_output(tmp_path: Path) -> None:
    mode_registry = ModeRegistry(
        state_path=tmp_path / "current_mode.json",
        persist=False,
    )
    mode_registry.switch_mode("focus")
    engine = FakeEngine()
    service = LocalTTSService(
        engines=[engine],
        permission_middleware=FakePermissionMiddleware(),
        mode_registry=mode_registry,
    )

    speech = service.speak("x" * 400)

    assert speech.truncated is True
    assert len(speech.spoken_text) <= 260
    assert engine.spoken[0][0].endswith("...")


def test_research_mode_allows_longer_output(tmp_path: Path) -> None:
    mode_registry = ModeRegistry(
        state_path=tmp_path / "current_mode.json",
        persist=False,
    )
    mode_registry.switch_mode("research")
    service = LocalTTSService(
        engines=[FakeEngine()],
        permission_middleware=FakePermissionMiddleware(),
        mode_registry=mode_registry,
    )

    speech = service.speak("x" * 900)

    assert speech.truncated is False
    assert service.status()["response_style"] == "long_summary"
