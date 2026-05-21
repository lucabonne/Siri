from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.engineering import (
    EngineeringService,
    detect_engineering_project,
    scan_cad_files,
)
from openjarvis.engineering.sessions import EngineeringSessionStore
from openjarvis.modes import ModeRegistry
from openjarvis.server.engineering_routes import engineering_router


class FakeMemory:
    def __init__(self) -> None:
        self.created: list[dict] = []

    def create_memory(self, content: str, **kwargs):
        memory = {"content": content, **kwargs}
        self.created.append(memory)
        return {"id": "memory-1", **memory}


def _sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "bracket"
    project.mkdir()
    (project / "bracket.step").write_text("ISO-10303-21;")
    (project / "fixture.stl").write_text("solid fixture")
    (project / "assembly.f3d").write_text("fusion export")
    (project / "freecad.FCStd").write_text("freecad")
    return project


def test_detects_step_stl_obj_fusion_and_freecad_projects(tmp_path: Path):
    project = _sample_project(tmp_path)
    (project / "mesh.obj").write_text("o mesh")

    detection = detect_engineering_project(project)
    formats = {item.format for item in scan_cad_files(project)}

    assert detection.is_engineering_project is True
    assert detection.project_kind in {"freecad", "fusion_export"}
    assert {"STEP", "STL", "OBJ", "Fusion export", "FreeCAD project"} <= formats
    assert detection.local_only is True
    assert detection.passive_only is True


def test_open_project_sets_active_workspace_and_records_memory(tmp_path: Path):
    project = _sample_project(tmp_path)
    memory = FakeMemory()
    service = EngineeringService(
        root=tmp_path,
        session_store=EngineeringSessionStore(tmp_path / "engineering.json"),
        memory_service=memory,
    )

    opened = service.open_project(project)
    status = service.status(cwd=tmp_path)

    assert opened.name == "bracket"
    assert status.active_project is not None
    assert status.active_project.path == str(project)
    assert status.workspace_state.active_project is not None
    assert status.workspace_state.active_project.id == opened.id
    assert memory.created[0]["memory_type"] == "engineering_project"
    assert status.cad_modifications_enabled is False
    assert status.cloud_uploads_enabled is False


def test_privacy_mode_skips_engineering_memory_writes(tmp_path: Path):
    project = _sample_project(tmp_path)
    memory = FakeMemory()
    service = EngineeringService(
        root=tmp_path,
        session_store=EngineeringSessionStore(tmp_path / "engineering.json"),
        memory_service=memory,
    )

    service.open_project(project, privacy_mode=True)
    status = service.status(cwd=tmp_path, privacy_mode=True)

    assert memory.created == []
    assert status.privacy_mode is True
    assert status.integrations["memory"]["writes_enabled"] is False


def test_project_summary_is_passive_and_has_recent_files(tmp_path: Path):
    project = _sample_project(tmp_path)
    service = EngineeringService(
        root=tmp_path,
        session_store=EngineeringSessionStore(tmp_path / "engineering.json"),
    )

    summary = service.project_summary(project)

    assert summary.file_count == 4
    assert summary.formats["STEP"] == 1
    assert summary.recent_files
    assert summary.viewer_hints
    assert summary.cad_modifications_enabled is False
    assert summary.cloud_uploaded is False


def test_engineering_routes_expose_status_open_project_and_recent_files(tmp_path: Path):
    project = _sample_project(tmp_path)
    app = FastAPI()
    app.state.engineering_service = EngineeringService(
        root=tmp_path,
        session_store=EngineeringSessionStore(tmp_path / "engineering.json"),
    )
    app.include_router(engineering_router)
    client = TestClient(app)

    status = client.get(f"/v1/engineering/status?cwd={tmp_path}")
    assert status.status_code == 200
    assert status.json()["local_only"] is True

    opened = client.post(
        "/v1/engineering/open-project",
        json={"path": str(project)},
    )
    assert opened.status_code == 200
    assert opened.json()["project"]["name"] == "bracket"

    summary = client.get(
        f"/v1/engineering/project-summary?path={project}",
    )
    assert summary.status_code == 200
    assert summary.json()["summary"]["formats"]["FreeCAD project"] == 1

    recent = client.get(f"/v1/engineering/recent-files?root={tmp_path}&limit=2")
    assert recent.status_code == 200
    assert len(recent.json()["files"]) == 2


def test_engineering_routes_honor_privacy_mode_for_memory(tmp_path: Path):
    project = _sample_project(tmp_path)
    memory = FakeMemory()
    app = FastAPI()
    app.state.mode_registry = ModeRegistry(
        active_mode_id="privacy",
        state_path=tmp_path / "mode.json",
        persist=False,
    )
    app.state.engineering_service = EngineeringService(
        root=tmp_path,
        session_store=EngineeringSessionStore(tmp_path / "engineering.json"),
        memory_service=memory,
    )
    app.include_router(engineering_router)
    client = TestClient(app)

    response = client.post(
        "/v1/engineering/open-project",
        json={"path": str(project)},
    )

    assert response.status_code == 200
    assert response.json()["privacy_mode"] is True
    assert memory.created == []
