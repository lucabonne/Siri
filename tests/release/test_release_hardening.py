from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.packaging import PackagingService
from openjarvis.release import ReleaseHardeningService
from openjarvis.server.release_routes import release_router


def _project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'siri'\n")
    (tmp_path / "frontend/src").mkdir(parents=True)
    (tmp_path / "frontend/package.json").write_text(
        json.dumps({"scripts": {"build": "vite build"}})
    )
    (tmp_path / "frontend/src/main.tsx").write_text("export {}\n")
    (tmp_path / "src/openjarvis/server/static").mkdir(parents=True)
    (tmp_path / "src/openjarvis/server/static/index.html").write_text("<main></main>")
    (tmp_path / "src/openjarvis/engineering").mkdir(parents=True)
    (tmp_path / "packaging/app_bundle").mkdir(parents=True)
    (tmp_path / "packaging/config").mkdir(parents=True)
    (tmp_path / "packaging/launchers").mkdir(parents=True)
    (tmp_path / "packaging/scripts").mkdir(parents=True)
    (tmp_path / "packaging/icons").mkdir(parents=True)
    (tmp_path / "packaging/config/app_metadata.json").write_text(
        json.dumps(
            {
                "name": "Siri",
                "bundle_identifier": "com.openjarvis.siri",
                "version": "1.0.0",
                "icon": "packaging/icons/Siri.icns",
                "local_only": True,
                "telemetry_enabled": False,
            }
        )
    )
    (tmp_path / "packaging/launchers/siri-launcher.sh").write_text("#!/bin/sh\n")
    (tmp_path / "packaging/scripts/bootstrap_backend.sh").write_text("#!/bin/sh\n")
    (tmp_path / "packaging/scripts/bootstrap_frontend.sh").write_text("#!/bin/sh\n")
    (tmp_path / "packaging/icons/Siri.icns").write_bytes(b"icns")
    return tmp_path


class _Engine:
    def health(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["local-model"]


def test_release_snapshot_is_local_only_and_covers_required_health(tmp_path: Path):
    root = _project(tmp_path)
    service = ReleaseHardeningService(
        project_root=root,
        packaging_service=PackagingService(project_root=root),
    )

    snapshot = service.snapshot(app_state=SimpleNamespace(engine=_Engine())).to_dict()

    assert snapshot["local_only"] is True
    assert snapshot["telemetry_enabled"] is False
    assert snapshot["autonomous_agents"] is False
    assert snapshot["wake_words"] is False
    assert snapshot["intelligence_features"] is False
    assert {check["id"] for check in snapshot["health_checks"]} >= {
        "backend",
        "frontend",
        "packaging",
        "mcp",
        "memory",
        "voice",
        "engineering_workspace",
    }
    assert {item["id"] for item in snapshot["diagnostics"]} >= {
        "missing_dependencies",
        "broken_paths",
        "model_availability",
        "launcher_status",
        "packaging_readiness",
    }
    assert snapshot["report"]["readiness_score"] >= 0


def test_release_recovery_repair_packaging_state_creates_local_paths(tmp_path: Path):
    root = tmp_path
    (root / "pyproject.toml").write_text("[project]\nname = 'siri'\n")
    (root / "frontend").mkdir()
    service = ReleaseHardeningService(project_root=root)

    result = service.run_recovery_action("repair_packaging_state").to_dict()

    assert result["status"] == "completed"
    assert (root / "packaging/config/app_metadata.json").exists()
    assert result["local_only"] is True
    assert result["telemetry_enabled"] is False


def test_release_routes_expose_mission_control_and_recovery(tmp_path: Path):
    root = _project(tmp_path)
    app = FastAPI()
    app.state.engine = _Engine()
    app.state.release_hardening_service = ReleaseHardeningService(
        project_root=root,
        packaging_service=PackagingService(project_root=root),
    )
    app.include_router(release_router)
    client = TestClient(app)

    panel = client.get("/v1/release/mission-control")
    health = client.get("/v1/release/health")
    recovery = client.get("/v1/release/recovery")
    report = client.get("/v1/release/report")
    validate = client.post(
        "/v1/release/recovery/run",
        json={"action": "validate_memory_db"},
    )

    assert panel.status_code == 200
    assert panel.json()["privacy_mode"]["local_only"] is True
    assert health.status_code == 200
    assert len(health.json()["checks"]) == 7
    assert recovery.status_code == 200
    assert {action["id"] for action in recovery.json()["actions"]} >= {
        "rebuild_frontend",
        "clear_caches",
        "reset_indexes",
        "validate_memory_db",
        "repair_packaging_state",
    }
    assert report.status_code == 200
    assert "readiness_score" in report.json()
    assert validate.status_code == 200
    assert validate.json()["action"] == "validate_memory_db"
