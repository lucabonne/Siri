from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.worldmonitor_routes import worldmonitor_router
from openjarvis.worldmonitor import WorldMonitorService


class FakeClient:
    base_url = "http://127.0.0.1:5173"

    def discover_base_url(self) -> str:
        return self.base_url

    def fetch_bootstrap(self) -> dict:
        return {
            "news": [
                {
                    "id": "wm-news-1",
                    "headline": "Tokyo markets steady",
                    "description": "Markets held steady in Tokyo.",
                    "latitude": 35.6762,
                    "longitude": 139.6503,
                    "url": "https://example.test/tokyo",
                }
            ]
        }


def _client(tmp_path) -> TestClient:
    app = FastAPI()
    app.state.worldmonitor_service = WorldMonitorService(
        db_path=tmp_path / "wm.db",
        client=FakeClient(),
    )
    app.include_router(worldmonitor_router)
    return TestClient(app)


def test_worldmonitor_routes_sync_and_return_cached_data(tmp_path) -> None:
    client = _client(tmp_path)

    status = client.get("/v1/worldmonitor/status")
    assert status.status_code == 200
    assert status.json()["connected"] is True

    sync = client.post("/v1/worldmonitor/sync", json={})
    assert sync.status_code == 200
    assert sync.json()["status"] == "synced"

    events = client.get("/v1/worldmonitor/events?map_only=true")
    assert events.status_code == 200
    assert events.json()["events"][0]["source_url"] == "https://example.test/tokyo"

    briefing = client.get("/v1/worldmonitor/briefing-data")
    assert briefing.status_code == 200
    assert briefing.json()["source_urls"] == ["https://example.test/tokyo"]

    sync_status = client.get("/v1/worldmonitor/sync-status")
    assert sync_status.status_code == 200
    assert sync_status.json()["sync"]["status"] == "synced"
