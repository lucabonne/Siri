from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.modes import ModeRegistry
from openjarvis.server.mode_routes import mode_router
from openjarvis.server.routes import router


class _FakeEngine:
    def list_models(self):
        return ["qwen3:8b"]

    def generate(self, *args, **kwargs):
        return {"content": "ok", "usage": {}}


def _client(tmp_path) -> TestClient:
    app = FastAPI()
    app.state.mode_registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
    app.include_router(mode_router)
    return TestClient(app)


def test_list_modes_returns_active_mode(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.get("/v1/modes")

    assert response.status_code == 200
    data = response.json()
    assert data["active_mode_id"] == "focus"
    assert {mode["id"] for mode in data["modes"]} >= {"focus", "privacy"}


def test_switch_active_mode(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post("/v1/modes/active", json={"mode_id": "privacy"})

    assert response.status_code == 200
    data = response.json()
    assert data["active_mode_id"] == "privacy"
    assert data["mode"]["privacy_network_policy"]["cloud_apis"] == "disabled"

    active = client.get("/v1/modes/active").json()
    assert active["active_mode_id"] == "privacy"


def test_switch_unknown_mode_returns_404(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post("/v1/modes/active", json={"mode_id": "unknown"})

    assert response.status_code == 404


def test_privacy_mode_blocks_cloud_chat_completion(tmp_path) -> None:
    app = FastAPI()
    registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
    registry.switch_mode("privacy")
    app.state.mode_registry = registry
    app.state.engine = _FakeEngine()
    app.state.agent = None
    app.state.config = None
    app.state.memory_backend = None
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 403
    assert "Privacy Mode" in response.json()["detail"]
