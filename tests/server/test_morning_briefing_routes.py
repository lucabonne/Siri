from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.modes import ModeRegistry
from openjarvis.morning_briefing import MorningBriefingService, NewsItem
from openjarvis.server.morning_briefing_routes import morning_briefing_router


class FakeFetcher:
    def fetch(self, *, max_items: int = 12) -> list[NewsItem]:
        return [
            NewsItem(
                title="Paris climate talks resume",
                summary="Climate negotiators returned to Paris for talks.",
                source_url="https://example.test/paris-climate",
                source_name="Example News",
            )
        ]


def _client(tmp_path, *, privacy: bool = False) -> TestClient:
    app = FastAPI()
    registry = ModeRegistry(state_path=tmp_path / "mode.json")
    if privacy:
        registry.switch_mode("privacy")
    app.state.mode_registry = registry
    app.state.morning_briefing_service = MorningBriefingService(
        db_path=tmp_path / "briefings.db",
        news_fetcher=FakeFetcher(),
    )
    app.include_router(morning_briefing_router)
    return TestClient(app)


def test_regenerate_latest_world_events_and_status(tmp_path) -> None:
    client = _client(tmp_path)

    regenerated = client.post("/v1/morning-briefing/regenerate", json={})
    assert regenerated.status_code == 200
    assert regenerated.json()["briefing"]["events"][0]["source_url"]

    latest = client.get("/v1/morning-briefing/latest")
    assert latest.status_code == 200
    assert latest.json()["briefing"]["title"].startswith("Morning Briefing")

    world_events = client.get("/v1/morning-briefing/world-events")
    assert world_events.status_code == 200
    assert world_events.json()["events"][0]["latitude"] is not None

    status = client.get("/v1/morning-briefing/status").json()
    assert status["has_cached_briefing"] is True
    assert status["external_fetching_enabled"] is True


def test_privacy_regenerate_requires_cached_briefing(tmp_path) -> None:
    client = _client(tmp_path, privacy=True)

    response = client.post("/v1/morning-briefing/regenerate", json={})

    assert response.status_code == 403
    assert "cached briefings" in response.json()["detail"]
