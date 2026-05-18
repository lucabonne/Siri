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
    DesktopStatus,
    LaunchRequest,
    LaunchResult,
    WindowInfo,
    WorkspaceFocus,
)
from openjarvis.desktop.sessions import DesktopSessionStore
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
        mode_registry: ModeRegistry | None = None,
        coding_assistant: CodingAssistantService | None = None,
    ) -> None:
        self.window_provider = window_provider or WindowProvider()
        self.app_controller = app_controller or AppController()
        self.launcher = launcher or DesktopLauncher()
        self.session_store = session_store or DesktopSessionStore()
        self.clipboard_provider = clipboard_provider or ClipboardProvider()
        self.focus_resolver = focus_resolver or FocusResolver()
        self.memory_service = memory_service
        self.workflow_service = workflow_service
        self.mode_registry = mode_registry or ModeRegistry(persist=False)
        self.coding_assistant = coding_assistant

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
        return DesktopStatus(
            active_window=active_window,
            active_application=active_app,
            open_apps=open_apps,
            focused_workspace=focus,
            session_state=session,
            clipboard_preview=clipboard_preview,
            clipboard_sensitive=clipboard_sensitive,
            recent_launches=session.recent_launches,
            integrations=self._integration_snapshot(focus, privacy_mode=privacy),
            privacy_mode=privacy,
        )

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
            "modes": self._mode_snapshot(),
            "coding_assistant": self._coding_snapshot(focus, privacy_mode=privacy_mode),
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
