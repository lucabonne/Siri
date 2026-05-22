from __future__ import annotations

import faulthandler
import json
import plistlib
import subprocess
import sys
import time
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
        "/bin/bash",
        str(app_path / "Contents/MacOS/Siri")
    ]

    uninstalled = service.uninstall_app_bundle()

    assert uninstalled["status"] == "uninstalled"
    assert app_path.exists() is False
    assert uninstalled["launch_agent"]["installed"] is False


def test_release_diagnostics_reports_missing_ffmpeg_with_brew_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from openjarvis.packaging import service as packaging_service

    real_which = packaging_service._which_command

    def fake_which(name: str):
        if name == "ffmpeg":
            return None
        return real_which(name)

    monkeypatch.setattr(packaging_service, "_which_command", fake_which)
    service = PackagingService(project_root=_project(tmp_path))

    diagnostics = service.release_diagnostics()

    ffmpeg = diagnostics["dependency_summary"]["ffmpeg"]
    assert ffmpeg["status"] == "missing"
    assert "brew install ffmpeg" in ffmpeg["message"]


def test_backend_bootstrap_prefers_project_venv_python(tmp_path: Path):
    root = tmp_path / "project"
    launcher_dir = tmp_path / "launcher"
    capture = tmp_path / "python-args.txt"
    (root / ".venv/bin").mkdir(parents=True)
    fake_python = root / ".venv/bin/python"
    fake_python.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$0 $*\" > {capture}\n"
        "sleep 30\n"
    )
    fake_python.chmod(0o755)

    result = subprocess.run(
        ["sh", "packaging/scripts/bootstrap_backend.sh"],
        cwd=Path(__file__).resolve().parents[2],
        env={
            "HOME": str(tmp_path / "home"),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "SIRI_PROJECT_ROOT": str(root),
            "OPENJARVIS_LAUNCHER_DIR": str(launcher_dir),
        },
        text=True,
        capture_output=True,
        timeout=10,
    )
    try:
        deadline = time.time() + 5
        while not capture.exists() and time.time() < deadline:
            time.sleep(0.05)
        pid = int((launcher_dir / "backend.pid").read_text().strip())
        subprocess.run(["kill", str(pid)], check=False)
    except Exception:
        pass

    assert result.returncode == 0
    assert str(fake_python) in capture.read_text()
    assert "-m openjarvis.packaging.local_backend --host 127.0.0.1" in capture.read_text()


def test_launcher_backend_health_timeout_prints_diagnostics(tmp_path: Path):
    root = tmp_path / "project"
    launcher_dir = tmp_path / "launcher"
    (root / "packaging/scripts").mkdir(parents=True)
    (root / "packaging/config").mkdir(parents=True)
    (root / "frontend").mkdir(parents=True)
    (root / "packaging/config/app_metadata.json").write_text("{}")
    bootstrap = root / "packaging/scripts/bootstrap_backend.sh"
    bootstrap.write_text(
        "#!/bin/sh\n"
        "mkdir -p \"$OPENJARVIS_LAUNCHER_DIR\"\n"
        "sleep 30 >/dev/null 2>&1 < /dev/null &\n"
        "echo $! > \"$OPENJARVIS_LAUNCHER_DIR/backend.pid\"\n"
        "echo backend fake failure > \"$OPENJARVIS_LAUNCHER_DIR/backend.log\"\n"
        "echo backend fake stderr > \"$OPENJARVIS_LAUNCHER_DIR/backend.err.log\"\n"
        "echo backend started pid=$(cat \"$OPENJARVIS_LAUNCHER_DIR/backend.pid\")\n"
    )
    bootstrap.chmod(0o755)

    result = subprocess.run(
        ["sh", "packaging/launchers/siri-launcher.sh", "launch"],
        cwd=Path(__file__).resolve().parents[2],
        env={
            "HOME": str(tmp_path / "home"),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "SIRI_PROJECT_ROOT": str(root),
            "OPENJARVIS_LAUNCHER_DIR": str(launcher_dir),
            "OPENJARVIS_BACKEND_HEALTH_TIMEOUT": "1",
            "OPENJARVIS_BACKEND_HEALTH_URL": "http://127.0.0.1:9/health",
            "OPENJARVIS_SKIP_FRONTEND": "1",
        },
        text=True,
        capture_output=True,
        timeout=10,
    )
    try:
        pid = int((launcher_dir / "backend.pid").read_text().strip())
        subprocess.run(["kill", str(pid)], check=False)
    except Exception:
        pass

    assert result.returncode == 1
    assert "backend=unhealthy" in result.stdout
    assert "backend fake failure" in result.stdout
    assert "backend fake stderr" in result.stdout


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
