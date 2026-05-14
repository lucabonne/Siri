from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.context.layer import ContextLayer
from openjarvis.context.terminal import TerminalContextStore
from openjarvis.context.vision import VisionContextStore
from openjarvis.memory import MemoryService
from openjarvis.modes import ModeRegistry
from openjarvis.security.approval_queue import ApprovalQueue
from openjarvis.server.context_routes import context_router

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
)


def test_context_project_route_returns_local_project_context(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi>=0.110"]\n',
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


def test_terminal_routes_capture_analyze_and_queue_approval(
    tmp_path, monkeypatch
) -> None:
    app = FastAPI()
    app.state.terminal_context_store = TerminalContextStore(
        history_path=tmp_path / "terminal.jsonl"
    )
    app.state.structured_memory_service = MemoryService(
        db_path=tmp_path / "memory.db",
        enable_semantic=False,
    )
    monkeypatch.setattr(
        "openjarvis.server.context_routes.ApprovalQueue",
        lambda: ApprovalQueue(tmp_path / "approvals"),
    )
    app.include_router(context_router)
    client = TestClient(app)

    capture = client.post(
        "/v1/context/terminal/commands",
        json={
            "command": "python app.py",
            "output": "ModuleNotFoundError: No module named 'rich'",
            "exit_code": 1,
            "cwd": str(tmp_path),
            "shell_type": "zsh",
        },
    )
    assert capture.status_code == 200
    assert capture.json()["memory_recorded"] is True

    current = client.get("/v1/context/terminal/current")
    assert current.status_code == 200
    data = current.json()
    assert data["current"]["command"] == "python app.py"
    assert data["error_summary"]["has_error"] is True
    command_id = data["error_summary"]["suggested_commands"][0]["id"]

    approval = client.post(
        f"/v1/context/terminal/suggested-commands/{command_id}/approval"
    )
    assert approval.status_code == 200
    approval_data = approval.json()
    assert approval_data["executed"] is False
    assert approval_data["approval"]["source"] == "terminal_copilot"

    app.state.structured_memory_service.close()


def test_terminal_route_respects_privacy_mode_and_skips_memory(tmp_path) -> None:
    app = FastAPI()
    registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
    registry.switch_mode("privacy")
    app.state.mode_registry = registry
    app.state.terminal_context_store = TerminalContextStore(
        history_path=tmp_path / "terminal.jsonl"
    )
    app.state.structured_memory_service = MemoryService(
        db_path=tmp_path / "memory.db",
        enable_semantic=False,
    )
    app.include_router(context_router)
    client = TestClient(app)

    capture = client.post(
        "/v1/context/terminal/commands",
        json={
            "command": "deploy --token secret",
            "output": "password=secret\npermission denied",
            "exit_code": 1,
            "cwd": str(tmp_path),
        },
    )

    assert capture.status_code == 200
    assert capture.json()["memory_recorded"] is False
    current = client.get("/v1/context/terminal/current").json()
    assert current["current"]["command"] == "[redacted terminal command]"
    assert current["current"]["output_preview"] == "[redacted terminal output]"
    assert current["privacy_mode"] is True
    assert app.state.structured_memory_service.list_command_history() == []
    app.state.structured_memory_service.close()


def test_vision_screenshot_capture_stores_local_metadata(tmp_path, monkeypatch) -> None:
    app = FastAPI()
    app.state.vision_context_store = VisionContextStore(root_dir=tmp_path / "vision")
    app.include_router(context_router)

    monkeypatch.setattr("openjarvis.context.vision.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        ContextLayer,
        "_active_macos_window",
        lambda self: ("Xcode", "Build"),
    )

    def fake_capture(self, path):
        path.write_bytes(PNG_1X1)

    monkeypatch.setattr(VisionContextStore, "_run_capture", fake_capture)
    client = TestClient(app)

    capture = client.post("/v1/context/vision/screenshots", json={})

    assert capture.status_code == 200
    payload = capture.json()
    screenshot = payload["screenshot"]
    assert payload["cloud_uploaded"] is False
    assert screenshot["width"] == 1
    assert screenshot["height"] == 1
    assert screenshot["active_application"] == "Xcode"
    assert screenshot["local_only"] is True
    assert screenshot["passive_only"] is True
    assert (tmp_path / "vision" / "screenshots.jsonl").exists()

    recent = client.get("/v1/context/vision/screenshots")
    assert recent.status_code == 200
    assert recent.json()["screenshots"][0]["id"] == screenshot["id"]

    latest = client.get("/v1/context/vision/latest")
    assert latest.status_code == 200
    assert latest.json()["latest_screenshot"]["id"] == screenshot["id"]


def test_vision_screenshot_capture_requires_privacy_approval(
    tmp_path,
    monkeypatch,
) -> None:
    app = FastAPI()
    registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
    registry.switch_mode("privacy")
    app.state.mode_registry = registry
    app.state.vision_context_store = VisionContextStore(root_dir=tmp_path / "vision")
    monkeypatch.setattr(
        "openjarvis.server.context_routes.ApprovalQueue",
        lambda: ApprovalQueue(tmp_path / "approvals"),
    )
    app.include_router(context_router)
    client = TestClient(app)

    response = client.post("/v1/context/vision/screenshots", json={})

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["error"] == "privacy_mode_blocks_screenshot_capture"
    assert detail["approval"]["tool"] == "vision_screenshot_capture"
    assert detail["cloud_uploaded"] is False
    assert list((tmp_path / "vision" / "screenshots").glob("*.png")) == []


def test_vision_metadata_redacted_in_privacy_mode(tmp_path, monkeypatch) -> None:
    app = FastAPI()
    registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
    registry.switch_mode("focus")
    app.state.mode_registry = registry
    store = VisionContextStore(root_dir=tmp_path / "vision")
    app.state.vision_context_store = store
    app.include_router(context_router)

    monkeypatch.setattr("openjarvis.context.vision.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        ContextLayer,
        "_active_macos_window",
        lambda self: ("Preview", "Private Doc"),
    )
    monkeypatch.setattr(
        VisionContextStore,
        "_run_capture",
        lambda self, path: path.write_bytes(PNG_1X1),
    )
    client = TestClient(app)

    assert client.post("/v1/context/vision/screenshots", json={}).status_code == 200
    registry.switch_mode("privacy")

    recent = client.get("/v1/context/vision/screenshots").json()["screenshots"][0]
    assert recent["file_path"] == ""
    assert recent["sha256"] == ""
    assert recent["active_window_title"] == "[redacted window]"
    assert recent["redacted"] is True

    latest = client.get("/v1/context/vision/latest").json()
    assert latest["privacy_mode"] is True
    assert latest["latest_screenshot"]["file_path"] == ""
