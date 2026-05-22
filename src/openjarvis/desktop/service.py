"""Coordinator for Siri desktop integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openjarvis.coding_assistant import CodingAssistantService
from openjarvis.desktop.apps import AppController
from openjarvis.desktop.clipboard import ClipboardProvider
from openjarvis.desktop.focus import FocusResolver
from openjarvis.desktop.launcher import DesktopLauncher
from openjarvis.desktop.models import (
    AppInfo,
    DesktopLauncherState,
    DesktopNotification,
    DesktopNotificationState,
    DesktopStatus,
    LaunchRequest,
    LaunchResult,
    TrayState,
    WindowInfo,
    WorkspaceFocus,
)
from openjarvis.desktop.notifications import NotificationCenter
from openjarvis.desktop.sessions import DesktopSessionStore
from openjarvis.desktop.tray import MenuBarController
from openjarvis.desktop.windows import WindowProvider
from openjarvis.modes import ModeRegistry


class DesktopService:
    """Local desktop awareness and explicit launch service.

    The service is intentionally passive unless a launch method is called by a
    user-triggered API route. It does not start background monitors or emit
    telemetry.
    """

    def __init__(
        self,
        *,
        window_provider: WindowProvider | None = None,
        app_controller: AppController | None = None,
        launcher: DesktopLauncher | None = None,
        session_store: DesktopSessionStore | None = None,
        clipboard_provider: ClipboardProvider | None = None,
        focus_resolver: FocusResolver | None = None,
        memory_service: Any = None,
        workflow_service: Any = None,
        startup_service: Any = None,
        voice_trigger_service: Any = None,
        wake_word_service: Any = None,
        tts_service: Any = None,
        permission_middleware: Any = None,
        mcp_server: Any = None,
        mcp_clients: list[Any] | None = None,
        mcp_tools_cache: Any = None,
        mode_registry: ModeRegistry | None = None,
        coding_assistant: CodingAssistantService | None = None,
        engineering_service: Any = None,
        notification_center: NotificationCenter | None = None,
        menu_bar: MenuBarController | None = None,
    ) -> None:
        self.window_provider = window_provider or WindowProvider()
        self.app_controller = app_controller or AppController()
        self.launcher = launcher or DesktopLauncher()
        self.session_store = session_store or DesktopSessionStore()
        self.clipboard_provider = clipboard_provider or ClipboardProvider()
        self.focus_resolver = focus_resolver or FocusResolver()
        self.memory_service = memory_service
        self.workflow_service = workflow_service
        self.startup_service = startup_service
        self.voice_trigger_service = voice_trigger_service
        self.wake_word_service = wake_word_service
        self.tts_service = tts_service
        self.permission_middleware = permission_middleware
        self.mcp_server = mcp_server
        self.mcp_clients = list(mcp_clients or [])
        self.mcp_tools_cache = mcp_tools_cache
        self.mode_registry = mode_registry or ModeRegistry(persist=False)
        self.coding_assistant = coding_assistant
        self.engineering_service = engineering_service
        self.notification_center = notification_center or NotificationCenter(
            session_store=self.session_store
        )
        self.menu_bar = menu_bar or MenuBarController()
        self._last_tray_action = ""

    def status(
        self,
        *,
        cwd: str | Path | None = None,
        privacy_mode: bool | None = None,
    ) -> DesktopStatus:
        privacy = self._privacy_mode(privacy_mode)
        active_window = self.window_provider.active_window(privacy_mode=privacy)
        open_apps = self.app_controller.open_apps(
            active_app_name=active_window.application_name
        )
        active_app = self._active_app(active_window, open_apps)
        session = self.session_store.load()
        focus = self.focus_resolver.focused_workspace(
            cwd=cwd,
            session_state=session,
        )
        clipboard_preview, clipboard_sensitive = self.clipboard_provider.preview(
            privacy_mode=privacy
        )
        launcher_state = self.launcher.state()
        notification_state = self.notification_center.state()
        tray_state = self.tray_state(
            focus=focus,
            launcher_state=launcher_state,
            notification_state=notification_state,
        )
        return DesktopStatus(
            active_window=active_window,
            active_application=active_app,
            open_apps=open_apps,
            focused_workspace=focus,
            session_state=session,
            clipboard_preview=clipboard_preview,
            clipboard_sensitive=clipboard_sensitive,
            recent_launches=session.recent_launches,
            launcher_state=launcher_state,
            notification_state=notification_state,
            tray_state=tray_state,
            integrations=self._integration_snapshot(focus, privacy_mode=privacy),
            privacy_mode=privacy,
        )

    def tray_state(
        self,
        *,
        focus: WorkspaceFocus | None = None,
        launcher_state: DesktopLauncherState | None = None,
        notification_state: DesktopNotificationState | None = None,
    ) -> TrayState:
        focus = focus or self.session_store.load().focused_workspace
        launcher_state = launcher_state or self.launcher.state()
        notification_state = notification_state or self.notification_center.state()
        return self.menu_bar.state(
            voice_trigger_enabled=self._voice_trigger_enabled(),
            current_workspace_available=bool(focus.path),
            launcher_running=(
                launcher_state.backend_status == "running"
                or launcher_state.frontend_status == "running"
            ),
            pending_notifications=len(
                [item for item in notification_state.recent if item.status == "ready"]
            ),
            last_action=self._last_tray_action,
        )

    def handle_tray_action(
        self,
        action_id: str,
        *,
        cwd: str | Path | None = None,
        requested_by: str = "user",
        privacy_mode: bool | None = None,
    ) -> dict[str, Any]:
        privacy = self._privacy_mode(privacy_mode)
        self._last_tray_action = action_id
        if requested_by != "user":
            return {
                "action": action_id,
                "status": "blocked",
                "reason": "desktop tray actions must be user-triggered",
                "local_only": True,
                "passive_only": True,
            }
        if action_id == "open_mission_control":
            result = self.launcher.open_mission_control(privacy_mode=privacy)
            return {"action": action_id, "launch": result.to_dict()}
        if action_id == "toggle_voice_trigger":
            return self._toggle_voice_trigger()
        if action_id == "quick_morning_briefing":
            return self._quick_morning_briefing(privacy_mode=privacy)
        if action_id == "open_current_workspace":
            focus = self.status(cwd=cwd, privacy_mode=privacy).focused_workspace
            if not focus.path:
                return {
                    "action": action_id,
                    "status": "unavailable",
                    "reason": "no focused workspace",
                    "local_only": True,
                    "passive_only": True,
                }
            result = self.launch_workspace(
                focus.path,
                requested_by=requested_by,
                privacy_mode=privacy,
            )
            return {"action": action_id, "launch": result.to_dict()}
        if action_id == "package_status":
            return {
                "action": action_id,
                "status": "ok",
                "package": self._packaging_snapshot(),
                "local_only": True,
                "passive_only": True,
                "telemetry_enabled": False,
            }
        if action_id == "restart_backend":
            state = self.launcher.restart_backend()
            self.session_store.set_launcher_state(state)
            return {"action": action_id, "launcher_state": state.to_dict()}
        if action_id == "restart":
            state = self.launcher.restart_all()
            self.session_store.set_launcher_state(state)
            return {
                "action": action_id,
                "launcher_state": state.to_dict(),
                "deprecated": True,
            }
        if action_id == "quit":
            return {
                "action": action_id,
                "status": "queued",
                "message": "native shell should quit the desktop process",
                "local_only": True,
                "passive_only": True,
                "telemetry_enabled": False,
            }
        return {
            "action": action_id,
            "status": "unknown",
            "reason": "unknown tray action",
            "local_only": True,
            "passive_only": True,
        }

    def notify(
        self,
        kind: str,
        title: str,
        body: str = "",
        *,
        user_triggered: bool = True,
        delivered: bool = False,
    ) -> DesktopNotification:
        return self.notification_center.notify(
            kind,
            title,
            body,
            user_triggered=user_triggered,
            delivered=delivered,
        )

    def launcher_status(
        self,
        *,
        run_health_checks: bool = False,
        run_startup_diagnostics: bool = False,
    ) -> DesktopLauncherState:
        if run_startup_diagnostics:
            state = self.launcher.startup_diagnostics()
        elif run_health_checks:
            state = self.launcher.health_checks()
        else:
            state = self.launcher.state()
        self.session_store.set_launcher_state(state)
        return state

    def start_backend(self) -> DesktopLauncherState:
        state = self.launcher.start_backend()
        self.session_store.set_launcher_state(state)
        return state

    def start_frontend(self) -> DesktopLauncherState:
        state = self.launcher.start_frontend()
        self.session_store.set_launcher_state(state)
        return state

    def restart_launcher(self) -> DesktopLauncherState:
        state = self.launcher.restart_all()
        self.session_store.set_launcher_state(state)
        return state

    def restart_backend(self) -> DesktopLauncherState:
        state = self.launcher.restart_backend()
        self.session_store.set_launcher_state(state)
        return state

    def restart_frontend(self) -> DesktopLauncherState:
        state = self.launcher.restart_frontend()
        self.session_store.set_launcher_state(state)
        return state

    def active_app(self, *, privacy_mode: bool | None = None) -> dict[str, Any]:
        status = self.status(privacy_mode=privacy_mode)
        return {
            "active_application": (
                status.active_application.to_dict()
                if status.active_application is not None
                else None
            ),
            "active_window": status.active_window.to_dict(),
            "privacy_mode": status.privacy_mode,
            "local_only": True,
            "passive_only": True,
        }

    def open_apps(self, *, privacy_mode: bool | None = None) -> dict[str, Any]:
        status = self.status(privacy_mode=privacy_mode)
        return {
            "open_apps": [app.to_dict() for app in status.open_apps],
            "active_application": (
                status.active_application.to_dict()
                if status.active_application is not None
                else None
            ),
            "privacy_mode": status.privacy_mode,
            "local_only": True,
            "passive_only": True,
        }

    def launch_app(
        self,
        app_name: str,
        *,
        requested_by: str = "user",
        privacy_mode: bool | None = None,
    ) -> LaunchResult:
        privacy = self._privacy_mode(privacy_mode)
        result = self.app_controller.launch_app(app_name, privacy_mode=privacy)
        return self._record_launch(
            LaunchRequest(
                action="launch_app",
                target=app_name,
                app_name=app_name,
                requested_by=requested_by,
            ),
            result,
            privacy_mode=privacy,
        )

    def launch_workspace(
        self,
        path: str | Path,
        *,
        app_name: str = "",
        requested_by: str = "user",
        privacy_mode: bool | None = None,
    ) -> LaunchResult:
        privacy = self._privacy_mode(privacy_mode)
        focus = self.focus_resolver.focused_workspace(explicit_path=path)
        result = self.launcher.open_workspace(
            path,
            app_name=app_name,
            privacy_mode=privacy,
        )
        return self._record_launch(
            LaunchRequest(
                action="open_workspace",
                target=str(path),
                app_name=app_name,
                workspace_path=str(path),
                requested_by=requested_by,
            ),
            result,
            privacy_mode=privacy,
            focus=focus,
        )

    def launch_repo(
        self,
        path: str | Path,
        *,
        requested_by: str = "user",
        privacy_mode: bool | None = None,
    ) -> LaunchResult:
        privacy = self._privacy_mode(privacy_mode)
        focus = self.focus_resolver.focused_workspace(explicit_path=path)
        result = self.launcher.open_repo(path, privacy_mode=privacy)
        return self._record_launch(
            LaunchRequest(
                action="open_repo",
                target=str(path),
                workspace_path=str(path),
                requested_by=requested_by,
            ),
            result,
            privacy_mode=privacy,
            focus=focus,
        )

    def launch_coding_environment(
        self,
        path: str | Path,
        *,
        coding_environment: str = "",
        requested_by: str = "user",
        privacy_mode: bool | None = None,
    ) -> LaunchResult:
        privacy = self._privacy_mode(privacy_mode)
        focus = self.focus_resolver.focused_workspace(explicit_path=path)
        result = self.launcher.launch_coding_environment(
            path,
            coding_environment=coding_environment,
            privacy_mode=privacy,
        )
        return self._record_launch(
            LaunchRequest(
                action="launch_coding_environment",
                target=str(path),
                workspace_path=str(path),
                coding_environment=coding_environment,
                requested_by=requested_by,
            ),
            result,
            privacy_mode=privacy,
            focus=focus,
        )

    def _record_launch(
        self,
        request: LaunchRequest,
        result: LaunchResult,
        *,
        privacy_mode: bool,
        focus: WorkspaceFocus | None = None,
    ) -> LaunchResult:
        result.privacy_mode = privacy_mode
        state = self.session_store.record_launch(result, focused_workspace=focus)
        if (
            result.status == "launched"
            and not privacy_mode
            and self.memory_service is not None
        ):
            self._record_memory(request, result, state.focused_workspace)
        return result

    def _record_memory(
        self,
        request: LaunchRequest,
        result: LaunchResult,
        focus: WorkspaceFocus,
    ) -> None:
        try:
            self.memory_service.create_memory(
                f"Desktop launch: {result.action} {result.target}".strip(),
                memory_type="desktop_launch",
                metadata={
                    "request": request.to_dict(),
                    "result": result.to_dict(),
                    "focused_workspace": focus.to_dict(),
                    "local_only": True,
                    "telemetry": False,
                },
                tags=["desktop", "launch"],
            )
        except Exception:
            return

    def _integration_snapshot(
        self,
        focus: WorkspaceFocus,
        *,
        privacy_mode: bool,
    ) -> dict[str, Any]:
        return {
            "context_layer": {
                "focused_workspace": focus.to_dict(),
                "local_only": True,
                "passive_only": True,
            },
            "memory": self._memory_snapshot(privacy_mode=privacy_mode),
            "workflows": self._workflow_snapshot(),
            "startup_scheduler": self._startup_snapshot(privacy_mode=privacy_mode),
            "voice": self._voice_snapshot(),
            "tts": self._tts_snapshot(),
            "mcp": self._mcp_snapshot(),
            "permissions": self._permissions_snapshot(),
            "modes": self._mode_snapshot(),
            "coding_assistant": self._coding_snapshot(focus, privacy_mode=privacy_mode),
            "engineering": self._engineering_snapshot(privacy_mode=privacy_mode),
            "packaging": self._packaging_snapshot(),
        }

    def _memory_snapshot(self, *, privacy_mode: bool) -> dict[str, Any]:
        if self.memory_service is None:
            return {"available": False, "writes_enabled": not privacy_mode}
        try:
            memories = self.memory_service.list_memories(
                memory_type="desktop_launch",
                limit=5,
            )
        except Exception:
            memories = []
        return {
            "available": True,
            "recent_desktop_launches": memories,
            "writes_enabled": not privacy_mode,
            "local_only": True,
        }

    def _workflow_snapshot(self) -> dict[str, Any]:
        if self.workflow_service is None:
            return {"available": False}
        try:
            snapshot = self.workflow_service.mission_control_snapshot()
            return {
                "available": True,
                "running_count": len(snapshot.get("running_workflows", [])),
                "history_count": len(snapshot.get("history", [])),
                "local_only": True,
            }
        except Exception:
            return {"available": False}

    def _engineering_snapshot(self, *, privacy_mode: bool) -> dict[str, Any]:
        if self.engineering_service is None:
            return {"available": False}
        try:
            snapshot = self.engineering_service.mission_control_snapshot(
                privacy_mode=privacy_mode,
            )
            return {"available": True, **snapshot}
        except Exception:
            return {"available": False}

    def _packaging_snapshot(self) -> dict[str, Any]:
        try:
            from openjarvis.packaging import PackagingService

            status = PackagingService().status()
            data = status.to_dict()
            return {
                "available": True,
                "status": data["status"],
                "app_bundle_exists": data["app_bundle_exists"],
                "install_readiness": data["install_readiness"],
                "app_bundle_path": data["app_bundle_path"],
                "local_only": True,
                "telemetry_enabled": False,
                "remote_installer": False,
            }
        except Exception:
            return {"available": False}

    def _startup_snapshot(self, *, privacy_mode: bool) -> dict[str, Any]:
        if self.startup_service is None:
            return {"available": False}
        try:
            status = self.startup_service.status(privacy_mode=privacy_mode)
            scheduler = status.scheduler.to_dict()
            return {
                "available": True,
                "launch_at_login": status.launch_at_login,
                "scheduler": scheduler,
                "local_only": True,
                "passive_only": True,
                "external_telemetry": False,
            }
        except Exception:
            return {"available": False}

    def _voice_snapshot(self) -> dict[str, Any]:
        if self.voice_trigger_service is None:
            return {"available": False}
        try:
            status = self.voice_trigger_service.status()
            wake_words = False
            if self.wake_word_service is not None:
                wake_words = bool(self.wake_word_service.status().get("enabled", False))
            return {
                "available": True,
                "status": status,
                "voice_trigger_enabled": bool(status.get("enabled", False)),
                "wake_words": wake_words,
                "local_only": True,
                "passive_only": True,
            }
        except Exception:
            return {"available": False}

    def _tts_snapshot(self) -> dict[str, Any]:
        if self.tts_service is None:
            return {"available": False}
        try:
            status = self.tts_service.status()
            return {
                "available": True,
                "status": status,
                "cloud_tts_enabled": False,
                "local_only": True,
                "passive_only": True,
            }
        except Exception:
            return {"available": False}

    def _permissions_snapshot(self) -> dict[str, Any]:
        return {
            "available": self.permission_middleware is not None,
            "approval_required_notifications": "user_triggered_only",
            "local_only": True,
            "passive_only": True,
        }

    def _mcp_snapshot(self) -> dict[str, Any]:
        cached_tools = []
        if isinstance(self.mcp_tools_cache, tuple) and self.mcp_tools_cache:
            cached_tools = list(self.mcp_tools_cache[0] or [])
        tool_count = len(cached_tools)
        if tool_count == 0 and self.mcp_server is not None:
            try:
                tool_count = len(self.mcp_server.get_tools())
            except Exception:
                tool_count = 0
        return {
            "available": bool(self.mcp_server or self.mcp_clients or cached_tools),
            "registered_tools": tool_count,
            "external_clients": len(self.mcp_clients),
            "registration_events": "user_triggered_notifications",
            "local_only": True,
            "passive_only": True,
            "telemetry_enabled": False,
        }

    def _mode_snapshot(self) -> dict[str, Any]:
        try:
            active = self.mode_registry.get_active_mode()
            return {
                "active_mode_id": active.active_mode_id,
                "mode": active.mode.to_dict(),
                "local_only": True,
            }
        except Exception:
            return {"available": False}

    def _coding_snapshot(
        self,
        focus: WorkspaceFocus,
        *,
        privacy_mode: bool,
    ) -> dict[str, Any]:
        if self.coding_assistant is None or not focus.path:
            return {"available": False}
        try:
            stack = self.coding_assistant.detect_stack(
                focus.path,
                privacy_mode=privacy_mode,
            )
            return {
                "available": True,
                "stack": stack.to_dict(),
                "workspace_path": focus.path,
                "local_only": True,
                "passive_only": True,
            }
        except Exception:
            return {"available": False}

    def _privacy_mode(self, override: bool | None) -> bool:
        if override is not None:
            return override
        try:
            return self.mode_registry.get_active_mode().mode.id == "privacy"
        except Exception:
            return False

    def _voice_trigger_enabled(self) -> bool:
        if self.voice_trigger_service is None:
            return False
        try:
            return bool(self.voice_trigger_service.status().get("enabled", False))
        except Exception:
            return False

    def _toggle_voice_trigger(self) -> dict[str, Any]:
        if self.voice_trigger_service is None:
            return {
                "action": "toggle_voice_trigger",
                "status": "unavailable",
                "reason": "voice trigger service is not available",
                "local_only": True,
                "passive_only": True,
            }
        try:
            if self._voice_trigger_enabled():
                result = self.voice_trigger_service.disable()
            else:
                result = self.voice_trigger_service.enable(explicit_approval=True)
            return {
                "action": "toggle_voice_trigger",
                "status": "ok",
                "voice": result,
                "wake_words": False,
                "local_only": True,
                "passive_only": True,
            }
        except Exception as exc:
            return {
                "action": "toggle_voice_trigger",
                "status": "failed",
                "reason": str(exc),
                "local_only": True,
                "passive_only": True,
            }

    def _quick_morning_briefing(self, *, privacy_mode: bool) -> dict[str, Any]:
        if self.startup_service is None:
            return {
                "action": "quick_morning_briefing",
                "status": "unavailable",
                "reason": "startup scheduler service is not available",
                "local_only": True,
                "passive_only": True,
            }
        try:
            result = self.startup_service.trigger_morning_briefing(
                force=True,
                privacy_mode=privacy_mode,
                source="tray",
                persist_memory=not privacy_mode,
            )
            notification = self.notify(
                "briefing_ready",
                "Briefing ready",
                "Your morning briefing is ready for review.",
                user_triggered=True,
            )
            return {
                "action": "quick_morning_briefing",
                "status": "ok",
                "briefing": result.to_dict(),
                "notification": notification.to_dict(),
                "local_only": True,
                "passive_only": True,
            }
        except Exception as exc:
            return {
                "action": "quick_morning_briefing",
                "status": "failed",
                "reason": str(exc),
                "local_only": True,
                "passive_only": True,
            }

    @staticmethod
    def _active_app(
        active_window: WindowInfo,
        open_apps: list[AppInfo],
    ) -> AppInfo | None:
        for app in open_apps:
            if app.frontmost or app.name == active_window.application_name:
                return app
        if active_window.application_name:
            return AppInfo(
                name=active_window.application_name,
                process_id=active_window.process_id,
                frontmost=True,
            )
        return None


__all__ = ["DesktopService"]
