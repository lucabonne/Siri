from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.core.config import JarvisConfig  # noqa: E402
from openjarvis.server.api_routes import voice_router  # noqa: E402
from openjarvis.voice.ptt import RecordingHandle, VoicePushToTalkService  # noqa: E402


class FakeRecorder:
    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path / "recording.wav"

    def start(self, recording_id: str) -> RecordingHandle:
        self.path.write_bytes(b"recording")
        return RecordingHandle(recording_id=recording_id, path=self.path, format="wav")

    def stop(self, handle: RecordingHandle) -> None:
        handle.path.write_bytes(b"recording stopped")


class FakeBackend:
    backend_id = "faster-whisper"

    def health(self) -> bool:
        return True

    def supported_formats(self):
        return ["wav"]

    def transcribe(self, audio: bytes, *, format: str = "wav", language=None):
        return type(
            "Result",
            (),
            {
                "text": "phase one transcript",
                "language": "en",
                "confidence": None,
                "duration_seconds": 0.0,
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


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    config = JarvisConfig()
    service = VoicePushToTalkService(
        config=config,
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.include_router(voice_router)
    return TestClient(app)


def test_voice_status_is_push_to_talk_only(client: TestClient) -> None:
    resp = client.get("/v1/voice/ptt/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["push_to_talk_only"] is True
    assert data["wake_word_enabled"] is False
    assert data["passive_listening"] is False


def test_voice_start_requires_approval(client: TestClient) -> None:
    resp = client.post("/v1/voice/ptt/start", json={})

    assert resp.status_code == 403


def test_voice_start_stop_transcribe_latest(client: TestClient) -> None:
    start = client.post("/v1/voice/ptt/start", json={"approved": True})
    assert start.status_code == 200
    assert start.json()["status"]["recording"] is True

    stop = client.post("/v1/voice/ptt/stop")
    assert stop.status_code == 200
    assert stop.json()["status"]["recording"] is False

    transcript = client.post("/v1/voice/ptt/transcribe-latest", json={})
    assert transcript.status_code == 200
    data = transcript.json()
    assert data["text"] == "phase one transcript"
    assert data["dispatched_to_agent"] is False
