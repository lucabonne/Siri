from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.context.layer import ContextLayer
from openjarvis.modes import ModeRegistry
from openjarvis.server.context_routes import context_router


def test_context_project_route_returns_local_project_context(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\ndependencies = [\"fastapi>=0.110\"]\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
    app = FastAPI()
    app.include_router(context_router)
    client = TestClient(app)

    response = client.get("/v1/context/project", params={"cwd": str(tmp_path)})

    assert response.status_code == 200
    data = response.json()
    assert data["cwd"] == str(tmp_path)
    assert "Python" in data["languages"]
    assert "FastAPI" in data["framework_build_system"]
    assert data["passive_only"] is True


def test_desktop_route_redacts_clipboard_in_privacy_mode(tmp_path, monkeypatch) -> None:
    app = FastAPI()
    registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
    registry.switch_mode("privacy")
    app.state.mode_registry = registry
    app.include_router(context_router)

    monkeypatch.setattr("openjarvis.context.layer.platform.system", lambda: "Darwin")

    def fake_run(self, args, *, cwd=None, timeout=1.0):
        if args[0] == "osascript":
            return "Safari\nSensitive Window"
        if args[0] == "pbpaste":
            return "ordinary clipboard text"
        return ""

    monkeypatch.setattr(ContextLayer, "_run", fake_run)
    client = TestClient(app)

    response = client.get("/v1/context/desktop", params={"cwd": str(tmp_path)})

    assert response.status_code == 200
    data = response.json()
    assert data["active_application"] == "Safari"
    assert data["clipboard_preview"] == "[redacted clipboard]"
    assert data["clipboard_sensitive"] is True
    assert data["privacy_mode"] is True
