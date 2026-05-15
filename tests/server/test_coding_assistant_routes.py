from __future__ import annotations

import json

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.context.terminal import TerminalContextStore  # noqa: E402
from openjarvis.memory import MemoryService  # noqa: E402
from openjarvis.server.coding_assistant_routes import (  # noqa: E402
    coding_assistant_router,
)


def test_coding_assistant_routes_return_build_health_and_panel(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {"build": "vite build"},
                "dependencies": {"vite": "^7.0.0", "react": "^19.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.tsx").write_text(
        "export function App() { return null }\n",
        encoding="utf-8",
    )
    terminal = TerminalContextStore(history_path=tmp_path / "terminal.jsonl")
    terminal.record(
        command="npm run build",
        output=(
            "vite build failed\n"
            "src/App.tsx:1:1 - error TS2307: Cannot find module './missing'\n"
        ),
        exit_code=1,
        cwd=tmp_path,
    )

    app = FastAPI()
    app.state.structured_memory_service = MemoryService(
        db_path=tmp_path / "memory.db",
        enable_semantic=False,
    )
    app.state.terminal_context_store = terminal
    app.include_router(coding_assistant_router)
    client = TestClient(app)

    analysis = client.post(
        "/v1/coding/analyze-build",
        json={
            "cwd": str(tmp_path),
            "command": "npm run build",
            "output": (
                "vite build failed\nerror TS2307: Cannot find module './missing'\n"
            ),
            "exit_code": 1,
        },
    )
    assert analysis.status_code == 200
    assert analysis.json()["has_failure"] is True
    assert analysis.json()["local_only"] is True
    categories = {item["category"] for item in analysis.json()["failures"]}
    assert "vite_or_typescript" in categories

    panel = client.get("/v1/coding/panel", params={"cwd": str(tmp_path)})
    assert panel.status_code == 200
    data = panel.json()
    assert data["passive_only"] is True
    assert data["cloud_uploaded"] is False
    assert "Node/Vite" in data["current_stack"]["specializations"]
    assert data["architecture_overview"]["major_systems"]

    app.state.structured_memory_service.close()
