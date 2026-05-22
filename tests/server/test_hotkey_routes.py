from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.core.config import JarvisConfig  # noqa: E402
from openjarvis.hotkeys import (  # noqa: E402
    GlobalVoiceHotkeyService,
    NullHotkeyListener,
)
from openjarvis.server.api_routes import hotkey_router  # noqa: E402


class FakeVoiceService:
    def status(self):
        return {"recording": False, "active_agent_id": "coding"}

    def start_recording(self, **kwargs):
        return None

    def stop_recording(self):
        return None


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


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.state.hotkey_service = GlobalVoiceHotkeyService(
        config=JarvisConfig(),
        voice_service=FakeVoiceService(),
        permission_middleware=FakePermissionMiddleware(),
        listener=NullHotkeyListener(),
    )
    app.include_router(hotkey_router)
    return TestClient(app)


def test_hotkey_status_defaults_safe(client: TestClient) -> None:
    response = client.get("/v1/hotkeys/status")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["wake_word_enabled"] is False
    assert data["background_transcription"] is False


def test_hotkey_enable_disable_and_binding(client: TestClient) -> None:
    enabled = client.post("/v1/hotkeys/enable", json={"approved": True})
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert enabled.json()["listener_running"] is True

    binding = client.get("/v1/hotkeys/binding")
    assert binding.status_code == 200
    assert binding.json()["display_name"] == "Fn"

    disabled = client.post("/v1/hotkeys/disable")
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


def test_hotkey_enable_requires_approval(client: TestClient) -> None:
    response = client.post("/v1/hotkeys/enable", json={"approved": False})

    assert response.status_code == 403
    assert response.json()["detail"]["status"] == "blocked"


def test_hotkey_test_trigger_is_dry(client: TestClient) -> None:
    response = client.post("/v1/hotkeys/test-trigger", json={"approved": True})

    assert response.status_code == 200
    data = response.json()
    assert data["trigger"]["test"] is True
    assert data["trigger"]["phase"] == "tested"
