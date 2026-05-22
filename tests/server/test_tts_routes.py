from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.server.api_routes import tts_router  # noqa: E402
from openjarvis.tts import LocalTTSService  # noqa: E402
from openjarvis.tts.models import TTSVoice  # noqa: E402


class FakeHandle:
    def poll(self):
        return None

    def terminate(self) -> None:
        return None

    def wait(self, timeout=None) -> None:
        return None


class FakeEngine:
    engine_id = "fake_local"

    def available(self) -> bool:
        return True

    def voices(self) -> list[TTSVoice]:
        return [TTSVoice(id="voice-a", name="Voice A", engine=self.engine_id)]

    def speak(self, text: str, *, voice_id: str = "", speed: float = 1.0):
        return FakeHandle()

    def stop(self, handle) -> None:
        return None


class FakeDecision:
    action = "allow"
    level = type("Level", (), {"name": "SAFE_ACTION"})()
    denied = False
    requires_confirmation = False
    reason = "safe action tool"
    matched_pattern = None


class FakePermissionMiddleware:
    def check(self, request):
        return FakeDecision()


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.state.tts_service = LocalTTSService(
        engines=[FakeEngine()],
        permission_middleware=FakePermissionMiddleware(),
    )
    app.include_router(tts_router)
    return TestClient(app)


def test_tts_status_is_local_only(client: TestClient) -> None:
    resp = client.get("/v1/tts/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["local_only"] is True
    assert data["cloud_tts_enabled"] is False
    assert data["autonomous_speech"] is False
    assert data["passive_only"] is True


def test_tts_voices(client: TestClient) -> None:
    resp = client.get("/v1/tts/voices")

    assert resp.status_code == 200
    data = resp.json()
    assert data["local_only"] is True
    assert data["voices"][0]["id"] == "voice-a"


def test_tts_speak_and_stop(client: TestClient) -> None:
    speak = client.post(
        "/v1/tts/speak",
        json={"text": "Local test phrase", "voice_id": "voice-a"},
    )

    assert speak.status_code == 200
    data = speak.json()
    assert data["status"]["speaking"] is True
    assert data["speech"]["voice_id"] == "voice-a"
    assert data["speech"]["local_only"] is True

    stop = client.post("/v1/tts/stop")

    assert stop.status_code == 200
    assert stop.json()["status"]["speaking"] is False


def test_tts_speak_requires_user_trigger(client: TestClient) -> None:
    resp = client.post(
        "/v1/tts/speak",
        json={"text": "No autonomous speech", "user_triggered": False},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"]["status"] == "blocked"
