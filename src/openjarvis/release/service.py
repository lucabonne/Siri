"""Local release hardening checks and recovery helpers."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from openjarvis.packaging import PackagingService
from openjarvis.release.models import (
    RecoveryAction,
    RecoveryResult,
    ReleaseCheck,
    ReleaseHealthSnapshot,
    ReleaseReport,
    StartupDiagnostic,
)


class ReleaseHardeningService:
    """Prepare Siri for a first local release candidate.

    The service is intentionally local-only. It checks local files, local app
    state, and localhost-oriented readiness data. It does not add telemetry,
    autonomous agents, wake words, or new intelligence behavior.
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        packaging_service: PackagingService | None = None,
    ) -> None:
        self.project_root = (
            Path(project_root).expanduser().resolve()
            if project_root
            else _default_project_root()
        )
        self.packaging_service = packaging_service or PackagingService(
            project_root=self.project_root
        )

    def snapshot(self, *, app_state: Any | None = None) -> ReleaseHealthSnapshot:
        health = self.health_checks(app_state=app_state)
        diagnostics = self.startup_diagnostics(app_state=app_state)
        report = self.release_report(health_checks=health, diagnostics=diagnostics)
        packaging_status = self.packaging_service.status().to_dict()

        active_profile_summary = {}
        try:
            from openjarvis.personalization.profiles import get_active_profile
            profile = get_active_profile()
            if profile:
                active_profile_summary = (
                    profile.model_dump()
                    if hasattr(profile, "model_dump")
                    else getattr(profile, "__dict__", {})
                )
        except ImportError:
            pass

        wake_status = {}
        if app_state and getattr(app_state, "wake_word_service", None) is not None:
            try:
                wake_status = app_state.wake_word_service.status()
            except Exception:
                pass

        return ReleaseHealthSnapshot(
            health_checks=health,
            diagnostics=diagnostics,
            recovery_actions=self.recovery_actions(),
            report=report,
            privacy_mode={
                "local_only": True,
                "telemetry_enabled": False,
                "remote_network_required": False,
                "cloud_uploads": False,
            },
            packaging_status=packaging_status,
            install_readiness=packaging_status.get("install_readiness", {}),
            active_profile_summary=active_profile_summary,
            wake_status=wake_status,
            readiness_state=report.readiness_status,
        )

    def health_checks(self, *, app_state: Any | None = None) -> list[ReleaseCheck]:
        packaging_status = self.packaging_service.status()
        return [
            self._backend_health(app_state),
            self._frontend_health(),
            self._packaging_health(packaging_status),
            self._mcp_health(app_state),
            self._memory_health(app_state),
            self._voice_health(app_state),
            self._engineering_workspace_health(app_state),
        ]

    def startup_diagnostics(
        self,
        *,
        app_state: Any | None = None,
    ) -> list[StartupDiagnostic]:
        return [
            self._missing_dependencies(),
            self._broken_paths(),
            self._model_availability(app_state),
            self._launcher_status(app_state),
            self._packaging_readiness(),
        ]

    def recovery_actions(self) -> list[RecoveryAction]:
        return [
            RecoveryAction(
                id="rebuild_frontend",
                label="Rebuild frontend",
                description="Run the local frontend production build.",
            ),
            RecoveryAction(
                id="clear_caches",
                label="Clear caches",
                description=(
                    "Remove local build/test caches that are safe to regenerate."
                ),
            ),
            RecoveryAction(
                id="reset_indexes",
                label="Reset indexes",
                description=(
                    "Remove local generated indexes so they can rebuild cleanly."
                ),
            ),
            RecoveryAction(
                id="validate_memory_db",
                label="Validate memory DB",
                description=(
                    "Run SQLite integrity checks against the local memory database."
                ),
                requires_confirmation=False,
            ),
            RecoveryAction(
                id="repair_packaging_state",
                label="Repair packaging state",
                description=(
                    "Recreate local packaging directories and metadata placeholders."
                ),
            ),
        ]

    def run_recovery_action(self, action: str) -> RecoveryResult:
        handlers = {
            "rebuild_frontend": self._rebuild_frontend,
            "clear_caches": self._clear_caches,
            "reset_indexes": self._reset_indexes,
            "validate_memory_db": self._validate_memory_db_action,
            "repair_packaging_state": self._repair_packaging_state,
        }
        handler = handlers.get(action)
        if handler is None:
            return RecoveryResult(
                action=action,
                status="unknown_action",
                summary=f"Unknown recovery action: {action}",
                warnings=["No local repair helper matched this action."],
            )
        return handler()

    def release_report(
        self,
        *,
        health_checks: list[ReleaseCheck] | None = None,
        diagnostics: list[StartupDiagnostic] | None = None,
    ) -> ReleaseReport:
        health_checks = health_checks or self.health_checks()
        diagnostics = diagnostics or self.startup_diagnostics()
        packaging_status = self.packaging_service.status()
        installation = packaging_status.installation
        installed_components = [
            {
                "id": "backend",
                "label": "Backend",
                "installed": (self.project_root / "src/openjarvis/server").exists(),
            },
            {
                "id": "frontend",
                "label": "Frontend",
                "installed": (self.project_root / "frontend/package.json").exists(),
            },
            {
                "id": "packaging",
                "label": "Packaging",
                "installed": packaging_status.paths.packaging_dir
                and Path(packaging_status.paths.packaging_dir).exists(),
            },
            {
                "id": "app_bundle_install",
                "label": "Siri.app install",
                "installed": bool(installation.get("installed")),
                "path": installation.get("preferred_app_path", ""),
            },
            {
                "id": "launch_agent",
                "label": "LaunchAgent",
                "installed": bool(
                    (installation.get("launch_agent") or {}).get("installed")
                ),
            },
            {
                "id": "mcp",
                "label": "MCP",
                "installed": self._module_path_exists("mcp"),
            },
            {
                "id": "memory",
                "label": "Memory",
                "installed": self._module_path_exists("memory"),
            },
            {
                "id": "voice",
                "label": "Voice",
                "installed": self._module_path_exists("speech"),
            },
            {
                "id": "engineering",
                "label": "Engineering",
                "installed": self._module_path_exists("engineering"),
            },
        ]
        enabled_modules = [
            component["id"]
            for component in installed_components
            if component.get("installed")
        ]
        warnings = [
            item.summary
            for item in [*health_checks, *diagnostics]
            if item.status in {"warning", "missing", "blocked", "unavailable"}
        ]
        required_items = [
            item for item in [*health_checks, *diagnostics] if item.required
        ]
        passing = sum(
            1 for item in required_items if item.status in {"ok", "ready", "warning"}
        )
        readiness_score = round((passing / max(1, len(required_items))) * 100)
        readiness_status = (
            "ready"
            if readiness_score >= 90 and not any(
                item.status in {"missing", "blocked"} for item in required_items
            )
            else "needs_attention"
        )
        return ReleaseReport(
            installed_components=installed_components,
            enabled_modules=enabled_modules,
            warnings=warnings,
            readiness_score=readiness_score,
            readiness_status=readiness_status,
        )

    def _backend_health(self, app_state: Any | None) -> ReleaseCheck:
        engine = getattr(app_state, "engine", None) if app_state is not None else None
        if engine is None:
            return ReleaseCheck(
                id="backend",
                label="Backend health",
                category="health",
                status="warning",
                summary="Backend process is reachable, but no engine is attached.",
                detail="Release API is running without app.state.engine.",
            )
        try:
            ok = bool(engine.health())
        except Exception as exc:
            return ReleaseCheck(
                id="backend",
                label="Backend health",
                category="health",
                status="blocked",
                summary="Backend engine health probe failed.",
                detail=str(exc),
            )
        return ReleaseCheck(
            id="backend",
            label="Backend health",
            category="health",
            status="ok" if ok else "blocked",
            summary=(
                "Backend engine is healthy."
                if ok
                else "Backend engine is unhealthy."
            ),
        )

    def _frontend_health(self) -> ReleaseCheck:
        package_json = self.project_root / "frontend/package.json"
        entry = self.project_root / "frontend/src/main.tsx"
        dist = self.project_root / "src/openjarvis/server/static/index.html"
        if not package_json.exists() or not entry.exists():
            return ReleaseCheck(
                id="frontend",
                label="Frontend health",
                category="health",
                status="missing",
                summary="Frontend source files are missing.",
                detail=f"{package_json} / {entry}",
                repair_action="rebuild_frontend",
            )
        return ReleaseCheck(
            id="frontend",
            label="Frontend health",
            category="health",
            status="ok" if dist.exists() else "warning",
            summary=(
                "Frontend source and built static assets are present."
                if dist.exists()
                else (
                    "Frontend source is present; production static assets "
                    "are not built."
                )
            ),
            detail=str(dist),
            repair_action="" if dist.exists() else "rebuild_frontend",
        )

    def _packaging_health(self, packaging_status: Any) -> ReleaseCheck:
        ready = bool(packaging_status.install_readiness.get("ready"))
        blockers = packaging_status.install_readiness.get("blockers", [])
        return ReleaseCheck(
            id="packaging",
            label="Packaging health",
            category="health",
            status="ok" if ready else "blocked",
            summary=(
                "Packaging is ready for a local app bundle."
                if ready
                else "Packaging has release blockers."
            ),
            detail=", ".join(blockers),
            repair_action="" if ready else "repair_packaging_state",
        )

    def _mcp_health(self, app_state: Any | None) -> ReleaseCheck:
        if not self._module_path_exists("mcp"):
            return ReleaseCheck(
                id="mcp",
                label="MCP health",
                category="health",
                status="missing",
                summary="MCP layer is not importable.",
            )
        server = (
            getattr(app_state, "mcp_server", None) if app_state is not None else None
        )
        cache = (
            getattr(app_state, "_mcp_tools_cache", None)
            if app_state is not None
            else None
        )
        tool_count = len(getattr(server, "_tools", {}) or cache or {})
        summary = (
            f"MCP layer is attached with {tool_count} local tools."
            if server is not None or cache
            else "MCP layer is importable and ready for local registration."
        )
        return ReleaseCheck(
            id="mcp",
            label="MCP health",
            category="health",
            status="ok",
            summary=summary,
        )

    def _memory_health(self, app_state: Any | None) -> ReleaseCheck:
        service = (
            getattr(app_state, "structured_memory_service", None)
            if app_state is not None
            else None
        )
        db_path = getattr(service, "db_path", None)
        if db_path is None:
            db_path = Path.home() / ".openjarvis" / "siri_memory.db"
        ok, detail = self._sqlite_integrity(Path(db_path))
        return ReleaseCheck(
            id="memory",
            label="Memory health",
            category="health",
            status="ok" if ok else "warning",
            summary=(
                "Memory database is valid."
                if ok
                else "Memory database needs validation."
            ),
            detail=detail,
            repair_action="" if ok else "validate_memory_db",
        )

    def _voice_health(self, app_state: Any | None) -> ReleaseCheck:
        speech_backend = (
            getattr(app_state, "speech_backend", None)
            if app_state is not None
            else None
        )
        tts_service = (
            getattr(app_state, "tts_service", None) if app_state is not None else None
        )
        if speech_backend is None and tts_service is None:
            return ReleaseCheck(
                id="voice",
                label="Voice health",
                category="health",
                status="warning",
                summary="Voice services are not attached.",
                detail="Push-to-talk can remain disabled for this release candidate.",
                required=False,
            )
        return ReleaseCheck(
            id="voice",
            label="Voice health",
            category="health",
            status="ok",
            summary="Voice services are attached for manual use.",
        )

    def _engineering_workspace_health(self, app_state: Any | None) -> ReleaseCheck:
        available = (
            self._module_path_exists("engineering")
            and (self.project_root / "src/openjarvis/engineering").exists()
        )
        service = (
            getattr(app_state, "engineering_service", None)
            if app_state is not None
            else None
        )
        return ReleaseCheck(
            id="engineering_workspace",
            label="Engineering workspace health",
            category="health",
            status="ok" if available else "missing",
            summary=(
                "Engineering workspace module is installed."
                if available
                else "Engineering workspace module is missing."
            ),
            detail=(
                "service attached" if service is not None else "service not attached"
            ),
        )

    def _module_path_exists(self, module: str) -> bool:
        module_path = self.project_root / "src/openjarvis" / module
        return module_path.exists() or module_path.with_suffix(".py").exists()

    def _missing_dependencies(self) -> StartupDiagnostic:
        missing = []
        for module in ("fastapi", "pydantic", "openjarvis"):
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        for command in ("uv", "node", "npm", "ollama", "ffmpeg"):
            if shutil.which(command) is None:
                missing.append(command)
        return StartupDiagnostic(
            id="missing_dependencies",
            label="Missing dependencies",
            status="ok" if not missing else "missing",
            summary=(
                "Required startup dependencies are available."
                if not missing
                else "Startup dependencies are missing."
            ),
            detail=", ".join(missing),
        )

    def _broken_paths(self) -> StartupDiagnostic:
        required_paths = [
            self.project_root / "pyproject.toml",
            self.project_root / "frontend/package.json",
            self.project_root / "packaging",
            self.project_root / "packaging/scripts/install_macos.sh",
            self.project_root / "packaging/scripts/uninstall_macos.sh",
            self.project_root / "packaging/scripts/release_diagnostics.sh",
            self.project_root / "packaging/scripts/package_app.py",
            self.project_root / "src/openjarvis",
        ]
        missing = [str(path) for path in required_paths if not path.exists()]
        return StartupDiagnostic(
            id="broken_paths",
            label="Broken paths",
            status="ok" if not missing else "missing",
            summary=(
                "Release-critical paths exist."
                if not missing
                else "Release-critical paths are missing."
            ),
            detail=", ".join(missing),
        )

    def _model_availability(self, app_state: Any | None) -> StartupDiagnostic:
        engine = getattr(app_state, "engine", None) if app_state is not None else None
        if engine is None:
            return StartupDiagnostic(
                id="model_availability",
                label="Model availability",
                status="warning",
                summary="No model engine is attached to the running backend.",
                detail="Attach a local engine before release candidate validation.",
                required=False,
            )
        try:
            models = engine.list_models()
        except Exception as exc:
            return StartupDiagnostic(
                id="model_availability",
                label="Model availability",
                status="warning",
                summary="Model listing failed.",
                detail=str(exc),
                required=False,
            )
        return StartupDiagnostic(
            id="model_availability",
            label="Model availability",
            status="ok" if models else "warning",
            summary=(
                f"{len(models)} local model entries are visible."
                if models
                else "No local model entries are visible."
            ),
            required=False,
        )

    def _launcher_status(self, app_state: Any | None) -> StartupDiagnostic:
        desktop = (
            getattr(app_state, "desktop_service", None)
            if app_state is not None
            else None
        )
        if desktop is None:
            return StartupDiagnostic(
                id="launcher_status",
                label="Launcher status",
                status="warning",
                summary="Desktop launcher service is not attached.",
                detail="The launcher script can still be inspected from packaging.",
                required=False,
            )
        try:
            state = desktop.launcher_status().to_dict()
        except Exception as exc:
            return StartupDiagnostic(
                id="launcher_status",
                label="Launcher status",
                status="warning",
                summary="Launcher status probe failed.",
                detail=str(exc),
                required=False,
            )
        return StartupDiagnostic(
            id="launcher_status",
            label="Launcher status",
            status="ok",
            summary=state.get("last_action", "Launcher state is available."),
            detail=json.dumps(
                {
                    "backend": state.get("backend_status"),
                    "frontend": state.get("frontend_status"),
                },
                sort_keys=True,
            ),
            required=False,
        )

    def _packaging_readiness(self) -> StartupDiagnostic:
        status = self.packaging_service.status()
        ready = bool(status.install_readiness.get("ready"))
        blockers = status.install_readiness.get("blockers", [])
        return StartupDiagnostic(
            id="packaging_readiness",
            label="Packaging readiness",
            status="ok" if ready else "blocked",
            summary=(
                "Packaging readiness checks pass."
                if ready
                else "Packaging readiness checks have blockers."
            ),
            detail=", ".join(blockers),
        )

    def _rebuild_frontend(self) -> RecoveryResult:
        frontend = self.project_root / "frontend"
        if not frontend.exists():
            return RecoveryResult(
                action="rebuild_frontend",
                status="missing",
                summary="Frontend directory is missing.",
                warnings=[str(frontend)],
            )
        npm = shutil.which("npm")
        if npm is None:
            return RecoveryResult(
                action="rebuild_frontend",
                status="missing_dependency",
                summary="npm is not available.",
                warnings=["Install npm before rebuilding the frontend."],
            )
        command = [npm, "run", "build"]
        try:
            completed = subprocess.run(
                command,
                cwd=frontend,
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return RecoveryResult(
                action="rebuild_frontend",
                status="timeout",
                summary="Frontend build timed out.",
            )
        if completed.returncode != 0:
            return RecoveryResult(
                action="rebuild_frontend",
                status="failed",
                summary="Frontend build failed.",
                warnings=[(completed.stderr or completed.stdout)[-1000:]],
            )
        return RecoveryResult(
            action="rebuild_frontend",
            status="completed",
            summary="Frontend build completed.",
            changed_paths=[str(self.project_root / "src/openjarvis/server/static")],
        )

    def _clear_caches(self) -> RecoveryResult:
        cache_paths = [
            self.project_root / ".pytest_cache",
            self.project_root / ".ruff_cache",
            self.project_root / "frontend/node_modules/.vite",
            self.project_root / "frontend/dist",
            self.project_root / "build/packaging/__pycache__",
        ]
        removed: list[str] = []
        warnings: list[str] = []
        for path in cache_paths:
            if not path.exists():
                continue
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed.append(str(path))
            except OSError as exc:
                warnings.append(f"{path}: {exc}")
        return RecoveryResult(
            action="clear_caches",
            status="completed" if not warnings else "completed_with_warnings",
            summary=f"Cleared {len(removed)} local cache paths.",
            changed_paths=removed,
            warnings=warnings,
        )

    def _reset_indexes(self) -> RecoveryResult:
        index_paths = [
            Path.home() / ".openjarvis/repo_index",
            Path.home() / ".openjarvis/chroma_memory",
        ]
        removed: list[str] = []
        warnings: list[str] = []
        for path in index_paths:
            if not path.exists():
                continue
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed.append(str(path))
            except OSError as exc:
                warnings.append(f"{path}: {exc}")
        return RecoveryResult(
            action="reset_indexes",
            status="completed" if not warnings else "completed_with_warnings",
            summary=f"Reset {len(removed)} generated local index paths.",
            changed_paths=removed,
            warnings=warnings,
        )

    def _validate_memory_db_action(self) -> RecoveryResult:
        ok, detail = self._sqlite_integrity(Path.home() / ".openjarvis/siri_memory.db")
        return RecoveryResult(
            action="validate_memory_db",
            status="completed" if ok else "failed",
            summary=detail,
        )

    def _repair_packaging_state(self) -> RecoveryResult:
        paths = [
            self.project_root / "packaging/app_bundle",
            self.project_root / "packaging/config",
            self.project_root / "packaging/launchers",
            self.project_root / "packaging/scripts",
            self.project_root / "packaging/icons",
            self.project_root / "build/packaging",
        ]
        changed: list[str] = []
        for path in paths:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                changed.append(str(path))
        metadata_file = self.project_root / "packaging/config/app_metadata.json"
        if not metadata_file.exists():
            metadata_file.write_text(
                json.dumps(
                    {
                        "name": "Siri",
                        "display_name": "Siri",
                        "bundle_identifier": "com.openjarvis.siri",
                        "local_only": True,
                        "telemetry_enabled": False,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            changed.append(str(metadata_file))
        script_placeholders = {
            self.project_root
            / "packaging/scripts/install_macos.sh": (
                "#!/bin/sh\n"
                "set -eu\n"
                "python3 -m openjarvis.cli package install\n"
            ),
            self.project_root
            / "packaging/scripts/uninstall_macos.sh": (
                "#!/bin/sh\n"
                "set -eu\n"
                "python3 -m openjarvis.cli package uninstall\n"
            ),
            self.project_root
            / "packaging/scripts/release_diagnostics.sh": (
                "#!/bin/sh\n"
                "set -eu\n"
                "python3 -m openjarvis.cli package release-diagnostics\n"
            ),
            self.project_root
            / "packaging/scripts/package_app.py": (
                "#!/usr/bin/env python3\n"
                "from openjarvis.packaging import PackagingService\n"
                "print(PackagingService().release_diagnostics())\n"
            ),
        }
        for path, content in script_placeholders.items():
            if path.exists():
                continue
            path.write_text(content, encoding="utf-8")
            path.chmod(path.stat().st_mode | 0o755)
            changed.append(str(path))
        return RecoveryResult(
            action="repair_packaging_state",
            status="completed",
            summary="Packaging directories and metadata placeholders are present.",
            changed_paths=changed,
        )

    def _sqlite_integrity(self, path: Path) -> tuple[bool, str]:
        if str(path) == ":memory:":
            return True, "In-memory SQLite database is active."
        path = path.expanduser()
        if not path.exists():
            return True, "Memory database has not been created yet."
        try:
            with sqlite3.connect(str(path)) as conn:
                result = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error as exc:
            return False, str(exc)
        message = str(result[0]) if result else "empty integrity result"
        return message.lower() == "ok", message


def _default_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists() and (parent / "frontend").exists():
            return parent
    return Path.cwd().resolve()


__all__ = ["ReleaseHardeningService"]
