from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.memory import MemoryService  # noqa: E402
from openjarvis.server.repo_index_routes import repo_index_router  # noqa: E402


def test_repo_index_routes_return_summary_search_and_graph(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"react": "^19.0.0", "vite": "^7.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.tsx").write_text(
        "export function App() { return null }\n",
        encoding="utf-8",
    )
    app = FastAPI()
    app.state.structured_memory_service = MemoryService(
        db_path=tmp_path / "memory.db",
        enable_semantic=False,
    )
    app.include_router(repo_index_router)
    client = TestClient(app)

    summary = client.get("/v1/repo/summary", params={"cwd": str(tmp_path)})
    assert summary.status_code == 200
    assert summary.json()["detected_stack"]["project_type"] == "web frontend"

    search = client.post(
        "/v1/repo/search",
        json={"cwd": str(tmp_path), "query": "react app", "limit": 5},
    )
    assert search.status_code == 200
    assert search.json()["results"][0]["path"] == "src/App.tsx"

    graph = client.get("/v1/repo/dependency-graph", params={"cwd": str(tmp_path)})
    assert graph.status_code == 200
    names = {item["name"] for item in graph.json()["direct_dependencies"]}
    assert {"react", "vite"} <= names

    app.state.structured_memory_service.close()
