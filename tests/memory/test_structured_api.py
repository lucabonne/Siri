"""Tests for structured memory API routes."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.memory import MemoryService  # noqa: E402
from openjarvis.server.api_routes import memory_router  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    app = FastAPI()
    app.state.structured_memory_service = MemoryService(
        db_path=tmp_path / "memory.db",
        chroma_path=tmp_path / "chroma",
        enable_semantic=False,
    )
    app.include_router(memory_router)
    with TestClient(app) as test_client:
        yield test_client
    app.state.structured_memory_service.close()


def test_create_list_search_delete_memory(client: TestClient):
    create_resp = client.post(
        "/v1/memory",
        json={
            "content": "Remember the local-first memory contract",
            "memory_type": "decision",
            "project_id": "siri-memory",
            "tags": ["phase-1"],
            "source": {
                "title": "Phase plan",
                "url": "https://example.test/phase-plan",
                "timestamp": "2026-05-14T08:10:00Z",
                "relevance": 0.8,
                "tags": ["plan"],
            },
        },
    )
    assert create_resp.status_code == 200
    memory = create_resp.json()["memory"]

    list_resp = client.get("/v1/memory", params={"project_id": "siri-memory"})
    assert list_resp.status_code == 200
    assert list_resp.json()["memories"][0]["id"] == memory["id"]

    search_resp = client.post(
        "/v1/memory/search",
        json={"query": "local-first contract", "top_k": 3, "memory_type": "decision"},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert results[0]["id"] == memory["id"]
    assert results[0]["source"]["title"] == "Phase plan"

    pin_resp = client.post(f"/v1/memory/{memory['id']}/pin", json={"pinned": True})
    assert pin_resp.status_code == 200
    assert pin_resp.json()["memory"]["pinned"] is True

    delete_resp = client.delete(f"/v1/memory/{memory['id']}")
    assert delete_resp.status_code == 200
    assert client.delete(f"/v1/memory/{memory['id']}").status_code == 404


def test_store_alias_returns_structured_memory(client: TestClient):
    resp = client.post(
        "/v1/memory/store",
        json={"content": "Alias path still writes structured memory"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "stored"
    assert data["memory"]["content"] == "Alias path still writes structured memory"
