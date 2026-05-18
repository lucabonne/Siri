from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.desktop import DesktopService
from openjarvis.desktop.models import AppInfo, LaunchResult, WindowInfo
from openjarvis.desktop.sessions import DesktopSessionStore
from openjarvis.modes import ModeRegistry
from openjarvis.server.desktop_routes import desktop_router


class FakeWindowProvider:
    def active_window(self, *, privacy_mode: bool = False) -> WindowInfo:
        return WindowInfo(
            application_name="Code",
            title="[redacted window]" if privacy_mode else "OpenJarvis",
            process_id=42,
            platform="Darwin",
            privacy_mode=privacy_mode,
        )


class FakeAppController:
    def __init__(self) -> None:
        self.launched: list[str] = []

    def open_apps(self, *, active_app_name: str = "") -> list[AppInfo]:
        return [
            AppInfo(name="Code", process_id=42, frontmost=True),
            AppInfo(name="Terminal", process_id=77),
        ]

    def launch_app(
        self,
        app_name: str,
        *,
        privacy_mode: bool = False,
    ) -> LaunchResult:
        self.launched.append(app_name)
        return LaunchResult(
            action="launch_app",
            target=app_name,
            status="launched",
            app_name=app_name,
            privacy_mode=privacy_mode,
        )


class FakeClipboardProvider:
    def preview(self, *, privacy_mode: bool = False) -> tuple[str, bool]:
        return ("[redacted clipboard]", True) if privacy_mode else ("hello", False)


class FakeMemory:
    def __init__(self) -> None:
        self.created: list[dict] = []

    def create_memory(self, content: str, **kwargs):
        memory = {"content": content, **kwargs}
        self.created.append(memory)
        return {"id": "memory-1", **memory}

    def list_memories(self, **kwargs):
        return list(self.created)


class FakeLauncher:
    def open_workspace(
        self,
        path,
        *,
        app_name: str = "",
        privacy_mode: bool = False,
    ) -> LaunchResult:
        return LaunchResult(
            action="open_workspace",
            target=str(path),
            status="launched",
            app_name=app_name,
            workspace_path=str(path),
            privacy_mode=privacy_mode,
        )

    def open_repo(self, path, *, privacy_mode: bool = False) -> LaunchResult:
        return LaunchResult(
            action="open_repo",
            target=str(path),
            status="launched",
            workspace_path=str(path),
            privacy_mode=privacy_mode,
        )

    def launch_coding_environment(
        self,
        path,
        *,
        coding_environment: str = "",
        privacy_mode: bool = False,
    ) -> LaunchResult:
        return LaunchResult(
            action="launch_coding_environment",
            target=str(path),
            status="launched",
            workspace_path=str(path),
            coding_environment=coding_environment,
            privacy_mode=privacy_mode,
        )


def _service(tmp_path: Path, *, mode_id: str = "focus", memory=None) -> DesktopService:
    registry = ModeRegistry(
        active_mode_id=mode_id,
        state_path=tmp_path / "mode.json",
        persist=False,
    )
    return DesktopService(
        window_provider=FakeWindowProvider(),
        app_controller=FakeAppController(),
        launcher=FakeLauncher(),
        session_store=DesktopSessionStore(tmp_path / "desktop.json"),
        clipboard_provider=FakeClipboardProvider(),
        mode_registry=registry,
        memory_service=memory,
    )


def test_desktop_status_reports_active_app_workspace_and_privacy_flags(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\ndependencies = []\n")
    service = _service(tmp_path)

    status = service.status(cwd=tmp_path)

    assert status.active_application is not None
    assert status.active_application.name == "Code"
    assert [app.name for app in status.open_apps] == ["Code", "Terminal"]
    assert status.focused_workspace.path == str(tmp_path)
    assert status.clipboard_preview == "hello"
    assert status.local_only is True
    assert status.passive_only is True
    assert status.autonomous_launching is False
    assert status.background_monitoring is False
    assert status.telemetry_enabled is False


def test_launch_workspace_records_local_session_and_memory(tmp_path: Path):
    memory = FakeMemory()
    service = _service(tmp_path, memory=memory)

    launch = service.launch_workspace(tmp_path, app_name="Code")
    state = service.session_store.load()

    assert launch.status == "launched"
    assert state.focused_workspace.path == str(tmp_path)
    assert state.recent_launches[0].action == "open_workspace"
    assert memory.created[0]["memory_type"] == "desktop_launch"


def test_privacy_mode_redacts_and_skips_memory_writes(tmp_path: Path):
    memory = FakeMemory()
    service = _service(tmp_path, mode_id="privacy", memory=memory)

    status = service.status(cwd=tmp_path)
    service.launch_app("Code")

    assert status.privacy_mode is True
    assert status.active_window.title == "[redacted window]"
    assert status.clipboard_sensitive is True
    assert memory.created == []


def test_desktop_routes_expose_status_and_launch(tmp_path: Path):
    app = FastAPI()
    app.state.desktop_service = _service(tmp_path)
    app.include_router(desktop_router)
    client = TestClient(app)

    status = client.get(f"/v1/desktop/status?cwd={tmp_path}")
    assert status.status_code == 200
    assert status.json()["active_application"]["name"] == "Code"

    launch = client.post(
        "/v1/desktop/launch-app",
        json={"app_name": "Notes"},
    )
    assert launch.status_code == 200
    assert launch.json()["launch"]["status"] == "launched"


def test_session_store_persists_recent_launches(tmp_path: Path):
    store = DesktopSessionStore(tmp_path / "desktop.json", max_launches=2)
    first = LaunchResult(action="launch_app", target="Notes", status="launched")
    second = LaunchResult(action="launch_app", target="Code", status="launched")
    third = LaunchResult(action="launch_app", target="Terminal", status="launched")

    store.record_launch(first)
    store.record_launch(second)
    store.record_launch(third)

    state = store.load()
    assert [item.target for item in state.recent_launches] == ["Terminal", "Code"]
    assert state.telemetry_enabled is False


def test_launcher_runner_receives_local_command(tmp_path: Path):
    from openjarvis.desktop.launcher import DesktopLauncher

    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    launcher = DesktopLauncher(runner=runner)
    result = launcher.open_workspace(tmp_path)

    assert result.status == "launched"
    assert result.local_only is True
    assert calls
