from __future__ import annotations

from pathlib import Path

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.modes import ModeRegistry
from openjarvis.voice.models import VoiceSession
from openjarvis.voice.ptt import (
    RecordingHandle,
    TranscriptionUnavailableError,
    VoicePermissionError,
    VoicePushToTalkService,
)


class FakeRecorder:
    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path / "recording.wav"
        self.started = False
        self.stopped = False

    def start(self, recording_id: str) -> RecordingHandle:
        self.started = True
        self.path.write_bytes(b"fake wav")
        return RecordingHandle(recording_id=recording_id, path=self.path, format="wav")

    def stop(self, handle: RecordingHandle) -> None:
        self.stopped = True
        handle.path.write_bytes(b"fake wav bytes")


class FakeBackend:
    backend_id = "faster-whisper"

    def health(self) -> bool:
        return True

    def supported_formats(self):
        return ["wav"]

    def transcribe(self, audio: bytes, *, format: str = "wav", language=None):
        assert audio == b"fake wav bytes"
        return type(
            "Result",
            (),
            {
                "text": "hello siri",
                "language": "en",
                "confidence": 0.9,
                "duration_seconds": 1.0,
                "segments": [],
            },
        )


class FakeDecision:
    action = "require_confirmation"
    level = type("Level", (), {"name": "CONFIRMED_EXECUTION"})()
    denied = False
    requires_confirmation = True
    reason = "tool requires confirmation"
    matched_pattern = None


class FakePermissionMiddleware:
    def check(self, request):
        return FakeDecision()


class FakeUnavailableTranscriber:
    def available(self) -> bool:
        return False

    def transcribe(self, *args, **kwargs):
        raise TranscriptionUnavailableError("transcription backend unavailable")


def test_ptt_requires_explicit_approval_by_default(tmp_path: Path) -> None:
    service = VoicePushToTalkService(
        config=JarvisConfig(),
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )

    with pytest.raises(VoicePermissionError):
        service.start_recording()


def test_start_stop_recording_state(tmp_path: Path) -> None:
    config = JarvisConfig()
    service = VoicePushToTalkService(
        config=config,
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )

    started = service.start_recording(explicit_approval=True, agent_id="coding")
    assert started.status == "recording"
    assert service.status()["wake_word_enabled"] is False
    assert service.status()["passive_listening"] is False
    assert service.status()["recording"] is True

    stopped = service.stop_recording()
    assert stopped.status == "recorded"
    assert stopped.byte_size > 0
    assert service.status()["recording"] is False


def test_ptt_transcribe_is_passive_and_deletes_audio(tmp_path: Path) -> None:
    config = JarvisConfig()
    service = VoicePushToTalkService(
        config=config,
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )

    service.start_recording(explicit_approval=True, agent_id="coding")
    service.stop_recording()
    result = service.transcribe_latest()
    assert result["text"] == "hello siri"
    assert result["intent_preview"]["interpreted_intent"] == "dictation"
    assert result["dispatched_to_agent"] is False
    assert result["session"]["raw_audio_available"] is False
    assert not (tmp_path / "recording.wav").exists()


def test_privacy_mode_blocks_voice_start_without_approval(tmp_path: Path) -> None:
    mode_registry = ModeRegistry(
        state_path=tmp_path / "current_mode.json",
        persist=False,
    )
    mode_registry.switch_mode("privacy")
    config = JarvisConfig()
    config.speech.voice_capture_enabled = True
    service = VoicePushToTalkService(
        config=config,
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
        mode_registry=mode_registry,
    )

    with pytest.raises(VoicePermissionError):
        service.start_recording()


def test_transcription_fallback_returns_unavailable_status(tmp_path: Path) -> None:
    service = VoicePushToTalkService(
        config=JarvisConfig(),
        transcriber=FakeUnavailableTranscriber(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )
    service.start_recording(explicit_approval=True)
    service.stop_recording()

    result = service.transcribe_latest()

    assert result["status"] == "transcription_backend_unavailable"
    assert "faster-whisper" in result["reason"]
    assert result["dispatched_to_agent"] is False


def test_voice_session_model() -> None:
    session = VoiceSession(
        id="voice-1",
        started_at=10.0,
        stopped_at=12.5,
        duration=2.5,
        audio_path="/tmp/raw.wav",
        transcript="hello",
        active_agent="coding",
        active_mode="focus",
        permission_decisions=[{"action": "allow"}],
        invoked_tools=[],
        status="preview_ready",
    )

    data = session.to_dict()
    assert data["id"] == "voice-1"
    assert data["duration"] == 2.5
    assert data["duration_seconds"] == 2.5
    assert data["audio_path"] == ""
    assert data["active_agent"] == "coding"
