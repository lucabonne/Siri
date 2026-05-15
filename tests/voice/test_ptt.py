from __future__ import annotations

from pathlib import Path

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.voice.ptt import (
    RecordingHandle,
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
    denied = False
    requires_confirmation = True
    reason = "tool requires confirmation"


class FakePermissionMiddleware:
    def check(self, request):
        return FakeDecision()


def test_ptt_requires_explicit_approval_by_default(tmp_path: Path) -> None:
    service = VoicePushToTalkService(
        config=JarvisConfig(),
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )

    with pytest.raises(VoicePermissionError):
        service.start_recording()


def test_ptt_start_stop_transcribe_is_passive_and_deletes_audio(tmp_path: Path) -> None:
    config = JarvisConfig()
    service = VoicePushToTalkService(
        config=config,
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )

    started = service.start_recording(explicit_approval=True, agent_id="coding")
    assert started.activation == "push_to_talk"
    assert service.status()["wake_word_enabled"] is False
    assert service.status()["passive_listening"] is False

    stopped = service.stop_recording()
    assert stopped.byte_size > 0

    result = service.transcribe_latest()
    assert result["text"] == "hello siri"
    assert result["dispatched_to_agent"] is False
    assert result["metadata"]["raw_audio_available"] is False
    assert not (tmp_path / "recording.wav").exists()
