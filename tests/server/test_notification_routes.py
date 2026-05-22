from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.modes import ModeRegistry
from openjarvis.notifications import NotificationService
from openjarvis.server.notification_routes import notification_router


def _client(tmp_path, *, mode: str = "focus") -> TestClient:
    app = FastAPI()
    app.state.mode_registry = ModeRegistry(
        active_mode_id=mode,
        state_path=tmp_path / "mode.json",
        persist=False,
    )
    app.state.notification_service = NotificationService(
        db_path=tmp_path / "notifications.db",
        mode_registry=app.state.mode_registry,
    )
    app.include_router(notification_router)
    return TestClient(app)


def test_notification_routes_queue_list_dismiss_clear_and_status(tmp_path):
    client = _client(tmp_path)

    queued = client.post(
        "/v1/notifications",
        json={
            "kind": "approval_required",
            "body": "A workflow needs review.",
            "payload": {"workflow_id": "wf-1"},
        },
    )
    assert queued.status_code == 200
    notification = queued.json()["notification"]
    assert notification["priority"] == "important"

    listed = client.get("/v1/notifications").json()
    assert listed["notifications"][0]["id"] == notification["id"]
    assert listed["local_only"] is True

    status = client.get("/v1/notifications/queue").json()
    assert status["unread"] == 1
    assert status["cloud_push_enabled"] is False

    dismissed = client.post(f"/v1/notifications/{notification['id']}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json()["notification"]["status"] == "dismissed"

    cleared = client.post("/v1/notifications/clear")
    assert cleared.status_code == 200
    assert "cleared" in cleared.json()


def test_notification_settings_and_mission_control_reflect_quiet_mode(tmp_path):
    client = _client(tmp_path, mode="quiet")

    settings = client.patch(
        "/v1/notifications/settings",
        json={"muted": True, "priority_filters": ["important"]},
    )
    assert settings.status_code == 200
    assert settings.json()["muted"] is True
    assert settings.json()["telemetry_enabled"] is False

    client.post("/v1/notifications", json={"kind": "startup_complete"})
    snapshot = client.get("/v1/notifications/mission-control").json()

    assert snapshot["queue"]["quiet_mode"] is True
    assert snapshot["muted_state"] is True
    assert snapshot["priority_filters"] == ["important"]
    assert snapshot["autonomous_interruptions"] is False
