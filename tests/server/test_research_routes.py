from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.memory import MemoryService
from openjarvis.modes import ModeRegistry
from openjarvis.research import ResearchService
from openjarvis.server.research_routes import research_router


def test_research_routes_start_status_report_citations_and_memory(tmp_path):
    app = FastAPI()
    memory = MemoryService(
        db_path=tmp_path / "memory.db",
        chroma_path=tmp_path / "chroma",
        enable_semantic=False,
    )
    app.state.structured_memory_service = memory
    app.state.research_service = ResearchService(
        db_path=tmp_path / "research.db",
        memory_service=memory,
    )
    app.include_router(research_router)
    client = TestClient(app)

    start = client.post(
        "/v1/research/start",
        json={
            "question": "What is the research API contract?",
            "sources": [
                {
                    "title": "API note",
                    "url": "https://example.test/api",
                    "content": (
                        "The research API exposes status, reports, citations, "
                        "and memory entries."
                    ),
                }
            ],
        },
    )
    assert start.status_code == 200
    research = start.json()["research"]
    research_id = research["id"]

    status = client.get(f"/v1/research/{research_id}/status")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"

    report = client.get(f"/v1/research/{research_id}/report")
    assert report.status_code == 200
    assert "citations" in report.json()["report"]

    citations = client.get(f"/v1/research/{research_id}/citations")
    assert citations.status_code == 200
    assert citations.json()["citations"][0]["label"] == "[1]"
    assert citations.json()["sources"][0]["extracted_claims"]

    memories = client.get(f"/v1/research/{research_id}/memory")
    assert memories.status_code == 200
    assert memories.json()["memories"]

    listed = client.get("/v1/research")
    assert listed.status_code == 200
    assert listed.json()["research"][0]["id"] == research_id


def test_research_route_respects_privacy_mode_cached_only(tmp_path):
    app = FastAPI()
    app.state.mode_registry = ModeRegistry(
        active_mode_id="privacy",
        state_path=tmp_path / "mode.json",
        persist=False,
    )
    app.state.research_service = ResearchService(db_path=tmp_path / "research.db")
    app.include_router(research_router)
    client = TestClient(app)

    response = client.post(
        "/v1/research/start",
        json={
            "question": "Privacy",
            "allow_external_search": True,
            "sources": [
                {
                    "title": "Cached",
                    "content": "Privacy uses cached research.",
                }
            ],
        },
    )

    assert response.status_code == 200
    research = response.json()["research"]
    assert research["privacy_mode"] is True
    assert research["cached_sources_only"] is True
    assert all(
        source["source_type"] != "external_search"
        for source in research["sources"]
    )
