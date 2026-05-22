from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.core.config import JarvisConfig  # noqa: E402
from openjarvis.server.api_routes import voice_router  # noqa: E402
from openjarvis.voice.models import TranscriptionUnavailableError  # noqa: E402
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
    assert resp.json()["detail"]["status"] == "blocked"


def test_voice_start_stop_transcribe_latest(client: TestClient) -> None:
    start = client.post("/v1/voice/ptt/start", json={"approved": True})
    assert start.status_code == 200
    assert start.json()["status"]["recording"] is True
    assert start.json()["session"]["status"] == "recording"

    stop = client.post("/v1/voice/ptt/stop")
    assert stop.status_code == 200
    assert stop.json()["status"]["recording"] is False
    assert stop.json()["session"]["status"] == "recorded"

    transcript = client.post("/v1/voice/ptt/transcribe-latest", json={})
    assert transcript.status_code == 200
    data = transcript.json()
    assert data["text"] == "phase one transcript"
    assert data["intent_preview"]["interpreted_intent"] == "dictation"
    assert data["session"]["status"] == "preview_ready"
    assert data["dispatched_to_agent"] is False


def test_voice_dispatch_no_agent_returns_not_dispatched(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/dispatch",
        json={"transcript": "open the notes app"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["dispatched"] is False
    assert "agent" in data["reason"]


def test_voice_dispatch_empty_transcript_is_422(client: TestClient) -> None:
    resp = client.post("/v1/voice/ptt/dispatch", json={"transcript": "  "})
    assert resp.status_code == 422


def test_voice_transcription_unavailable_response(tmp_path: Path) -> None:
    app = FastAPI()
    service = VoicePushToTalkService(
        config=JarvisConfig(),
        transcriber=FakeUnavailableTranscriber(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.include_router(voice_router)
    client = TestClient(app)

    client.post("/v1/voice/ptt/start", json={"approved": True})
    client.post("/v1/voice/ptt/stop")
    response = client.post("/v1/voice/ptt/transcribe-latest", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "transcription_backend_unavailable"
    assert "faster-whisper" in data["reason"]
