from __future__ import annotations

import faulthandler
import json
import plistlib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.packaging import PackagingService
from openjarvis.server.packaging_routes import packaging_router


@pytest.fixture(autouse=True)
def _dump_traceback_on_packaging_test_hang():
    faulthandler.dump_traceback_later(30, file=sys.stderr)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()


def _project(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
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
    (tmp_path / "packaging/scripts/install_macos.sh").write_text("#!/bin/sh\n")
    (tmp_path / "packaging/scripts/uninstall_macos.sh").write_text("#!/bin/sh\n")
    (tmp_path / "packaging/scripts/release_diagnostics.sh").write_text("#!/bin/sh\n")
    (tmp_path / "packaging/scripts/package_app.py").write_text(
        "#!/usr/bin/env python3\n"
    )
    for script in (tmp_path / "packaging").glob("**/*.sh"):
        script.chmod(script.stat().st_mode | 0o755)
    (tmp_path / "packaging/scripts/package_app.py").chmod(0o755)
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
    assert status["install_readiness"]["ready"] is (
        not status["install_readiness"]["blockers"]
    )
    assert "installation" in status
    assert {check["name"] for check in status["checks"]} >= {
        "python",
        "uv",
        "node",
        "npm",
        "ollama",
        "ffmpeg",
        "macos_permissions_guidance",
    }


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


def test_install_and_uninstall_app_bundle_updates_launch_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    service = PackagingService(project_root=_project(tmp_path / "project"))

    installed = service.install_app_bundle(destination="user")
    app_path = Path(installed["app_bundle_path"])

    assert installed["status"] == "installed"
    assert app_path.exists()
    assert installed["launch_agent"]["valid"] is True
    assert installed["launch_agent"]["installed_program_arguments"] == [
        str(app_path / "Contents/MacOS/Siri")
    ]

    uninstalled = service.uninstall_app_bundle()

    assert uninstalled["status"] == "uninstalled"
    assert app_path.exists() is False
    assert uninstalled["launch_agent"]["installed"] is False


def test_packaging_routes_expose_status_diagnostics_launcher_and_build(
    tmp_path: Path,
):
    app = FastAPI()
    app.state.packaging_service = PackagingService(project_root=_project(tmp_path))
    app.include_router(packaging_router)
    client = TestClient(app)

    status = client.get("/v1/packaging/status")
    diagnostics = client.get("/v1/packaging/diagnostics")
    release_diagnostics = client.get("/v1/packaging/release-diagnostics")
    launcher = client.get("/v1/packaging/launcher/state")
    build = client.post(
        "/v1/packaging/build",
        json={"output_dir": str(tmp_path / "api-dist")},
    )

    assert status.status_code == 200
    assert status.json()["metadata"]["name"] == "Siri"
    assert diagnostics.status_code == 200
    assert diagnostics.json()["local_only"] is True
    assert release_diagnostics.status_code == 200
    assert "dependency_summary" in release_diagnostics.json()
    assert launcher.status_code == 200
    assert launcher.json()["single_command_launch"].endswith("siri-launcher.sh launch")
    assert build.status_code == 200
    assert Path(build.json()["app_bundle_path"]).exists()
