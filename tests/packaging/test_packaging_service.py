from __future__ import annotations

import json
import platform
import plistlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.packaging import PackagingService
from openjarvis.server.packaging_routes import packaging_router


def _project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'siri'\n")
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend/package.json").write_text("{}")
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
                "version": "1.2.3",
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


def test_packaging_status_reports_metadata_and_local_readiness(tmp_path: Path):
    service = PackagingService(project_root=_project(tmp_path))

    status = service.status().to_dict()

    assert status["metadata"]["name"] == "Siri"
    assert status["metadata"]["bundle_identifier"] == "com.openjarvis.siri"
    assert status["metadata"]["telemetry_enabled"] is False
    assert status["remote_installer"] is False
    assert status["notarization_enabled"] is False
    assert status["updater_enabled"] is False
    assert status["install_readiness"]["ready"] is (platform.system() == "Darwin")


def test_build_app_bundle_creates_minimal_local_macos_bundle(tmp_path: Path):
    service = PackagingService(project_root=_project(tmp_path))

    result = service.build_app_bundle(output_dir=tmp_path / "dist")
    app_path = Path(result["app_bundle_path"])
    plist_path = app_path / "Contents/Info.plist"
    executable = app_path / "Contents/MacOS/Siri"

    assert result["status"] == "built"
    assert plist_path.exists()
    assert executable.exists()
    assert executable.stat().st_mode & 0o111
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    assert plist["CFBundleName"] == "Siri"
    assert plist["CFBundleIdentifier"] == "com.openjarvis.siri"
    assert result["notarization_enabled"] is False
    assert result["updater_enabled"] is False


def test_packaging_routes_expose_status_diagnostics_launcher_and_build(
    tmp_path: Path,
):
    app = FastAPI()
    app.state.packaging_service = PackagingService(project_root=_project(tmp_path))
    app.include_router(packaging_router)
    client = TestClient(app)

    status = client.get("/v1/packaging/status")
    diagnostics = client.get("/v1/packaging/diagnostics")
    launcher = client.get("/v1/packaging/launcher/state")
    build = client.post(
        "/v1/packaging/build",
        json={"output_dir": str(tmp_path / "api-dist")},
    )

    assert status.status_code == 200
    assert status.json()["metadata"]["name"] == "Siri"
    assert diagnostics.status_code == 200
    assert diagnostics.json()["local_only"] is True
    assert launcher.status_code == 200
    assert launcher.json()["single_command_launch"].endswith("siri-launcher.sh launch")
    assert build.status_code == 200
    assert Path(build.json()["app_bundle_path"]).exists()
