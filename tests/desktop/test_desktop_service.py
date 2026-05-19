from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.desktop import DesktopService
from openjarvis.desktop.models import (
    AppInfo,
    DesktopLauncherState,
    LauncherHealthCheck,
    LaunchResult,
    WindowInfo,
)
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
    def __init__(self) -> None:
        self.restarted = False
        self.health_checked = False

    def state(self) -> DesktopLauncherState:
        return DesktopLauncherState()

    def health_checks(self) -> DesktopLauncherState:
        self.health_checked = True
        return DesktopLauncherState(
            health_checks=[
                LauncherHealthCheck(name="backend", status="healthy"),
                LauncherHealthCheck(name="frontend", status="unavailable"),
            ],
            last_action="health_checks",
        )

    def start_backend(self) -> DesktopLauncherState:
        return DesktopLauncherState(
            backend_status="running",
            backend_command=["jarvis", "serve"],
            last_action="start_backend",
        )

    def start_frontend(self) -> DesktopLauncherState:
        return DesktopLauncherState(
            frontend_status="running",
            frontend_command=["npm", "run", "dev"],
            last_action="start_frontend",
        )

    def restart_all(self) -> DesktopLauncherState:
        self.restarted = True
        return DesktopLauncherState(
            backend_status="running",
            frontend_status="running",
            last_action="restart",
        )

    def open_mission_control(self, *, privacy_mode: bool = False) -> LaunchResult:
        return LaunchResult(
            action="open_mission_control",
            target="http://127.0.0.1:5173/mission-control",
            status="launched",
            privacy_mode=privacy_mode,
        )

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


class FakeVoiceTrigger:
    def __init__(self) -> None:
        self.enabled = False

    def status(self) -> dict:
        return {"enabled": self.enabled, "local_only": True}

    def enable(self, *, explicit_approval: bool = False) -> dict:
        self.enabled = True
        return {"enabled": True, "approved": explicit_approval}

    def disable(self) -> dict:
        self.enabled = False
        return {"enabled": False}


class FakeStartupService:
    def __init__(self) -> None:
        self.triggered = False

    def status(self, *, privacy_mode: bool = False):
        class _Scheduler:
            def to_dict(self) -> dict:
                return {"tasks": [], "passive_only": True}

        class _Status:
            launch_at_login = False
            scheduler = _Scheduler()

        return _Status()

    def trigger_morning_briefing(self, **kwargs):
        self.triggered = True

        class _Result:
            def to_dict(self) -> dict:
                return {"triggered": True}

        return _Result()


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
    assert status.launcher_state.telemetry_enabled is False
    assert status.notification_state.autonomous_notifications is False
    assert status.tray_state.local_only is True


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


def test_notification_center_records_only_user_triggered_allowed_events(tmp_path: Path):
    service = _service(tmp_path)

    ready = service.notify(
        "workflow_finished",
        "Workflow finished",
        "Review the result.",
        user_triggered=True,
    )
    suppressed = service.notify(
        "approval_required",
        "Approval required",
        user_triggered=False,
    )
    blocked = service.notify("random", "Nope", user_triggered=True)
    state = service.notification_center.state()

    assert ready.status == "ready"
    assert suppressed.status == "suppressed"
    assert blocked.status == "blocked"
    assert [item.kind for item in state.recent] == ["workflow_finished"]
    assert state.telemetry_enabled is False
    assert state.autonomous_notifications is False


def test_tray_actions_toggle_voice_and_trigger_briefing(tmp_path: Path):
    voice = FakeVoiceTrigger()
    startup = FakeStartupService()
    service = _service(tmp_path)
    service.voice_trigger_service = voice
    service.startup_service = startup

    voice_result = service.handle_tray_action("toggle_voice_trigger")
    briefing_result = service.handle_tray_action("quick_morning_briefing")
    blocked = service.handle_tray_action(
        "open_mission_control",
        requested_by="scheduler",
    )

    assert voice_result["status"] == "ok"
    assert voice.enabled is True
    assert briefing_result["status"] == "ok"
    assert startup.triggered is True
    assert service.notification_center.state().recent[0].kind == "briefing_ready"
    assert blocked["status"] == "blocked"


def test_launcher_state_exposes_health_and_restart(tmp_path: Path):
    service = _service(tmp_path)

    health = service.launcher_status(run_health_checks=True)
    restart = service.restart_launcher()

    assert [check.name for check in health.health_checks] == ["backend", "frontend"]
    assert restart.backend_status == "running"
    assert restart.frontend_status == "running"
    assert service.session_store.load().launcher_state.last_action == "restart"


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


def test_desktop_routes_expose_phase_one_wrapper_state(tmp_path: Path):
    app = FastAPI()
    app.state.desktop_service = _service(tmp_path)
    app.include_router(desktop_router)
    client = TestClient(app)

    tray = client.get("/v1/desktop/tray")
    assert tray.status_code == 200
    assert "open_mission_control" in [item["id"] for item in tray.json()["items"]]

    notification = client.post(
        "/v1/desktop/notifications",
        json={
            "kind": "approval_required",
            "title": "Approval required",
            "body": "Review a pending workflow.",
        },
    )
    assert notification.status_code == 200
    assert notification.json()["notification"]["status"] == "ready"

    launcher = client.get("/v1/desktop/launcher/status?health=true")
    assert launcher.status_code == 200
    assert launcher.json()["last_action"] == "health_checks"
