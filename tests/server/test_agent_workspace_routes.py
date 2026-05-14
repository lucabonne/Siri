from __future__ import annotations

# ruff: noqa: E402, I001

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.server.agent_workspace_routes import agent_workspace_router  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(agent_workspace_router)
    return TestClient(app)


def test_list_workspace_agents(client: TestClient) -> None:
    resp = client.get("/v1/agent-workspace/agents")

    assert resp.status_code == 200
    data = resp.json()
    assert data["active_agent_id"] == "coding"
    assert {agent["id"] for agent in data["agents"]} >= {"coding", "privacy"}


def test_get_workspace_agent(client: TestClient) -> None:
    resp = client.get("/v1/agent-workspace/agents/research")

    assert resp.status_code == 200
    agent = resp.json()["agent"]
    assert agent["id"] == "research"
    assert agent["routing"]["recommended_agent"] == "research"


def test_switch_active_workspace_agent(client: TestClient) -> None:
    switch_resp = client.post(
        "/v1/agent-workspace/active-agent",
        json={"agent_id": "terminal"},
    )

    assert switch_resp.status_code == 200
    assert switch_resp.json()["active_agent_id"] == "terminal"

    current_resp = client.get("/v1/agent-workspace/active-agent")
    assert current_resp.status_code == 200
    assert current_resp.json()["agent"]["id"] == "terminal"


def test_switch_unknown_agent_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/v1/agent-workspace/active-agent",
        json={"agent_id": "unknown"},
    )

    assert resp.status_code == 404
