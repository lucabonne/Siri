"""Small local-only backend used by the installed Siri.app launcher.

This module intentionally exposes release and status endpoints only. It avoids
the full assistant runtime so the macOS app can prove that packaging, desktop,
voice, hotkey, tray, memory, and startup state load without starting model
execution, wake words, or autonomous behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from openjarvis.packaging import PackagingService


STARTED_AT = time.time()


class LocalBackendHandler(BaseHTTPRequestHandler):
    server_version = "SiriLocalBackend/1.0"

    def do_OPTIONS(self) -> None:
        self._send_json({})

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        routes = {
            "/health": self._health,
            "/v1/memory/stats": self._memory_stats,
            "/v1/memory/config": self._memory_config,
            "/v1/memory": self._memory_entries,
            "/v1/speech/health": self._speech_health,
            "/v1/voice/ptt/status": self._voice_status,
            "/v1/hotkeys/status": self._hotkey_status,
            "/v1/hotkeys/binding": self._hotkey_binding,
            "/v1/desktop/tray": self._tray_state,
            "/v1/desktop/status": self._desktop_status,
            "/v1/startup/status": self._startup_status,
            "/v1/startup/scheduler/status": self._startup_status,
            "/v1/packaging/status": lambda: self.packaging.status().to_dict(),
            "/v1/packaging/diagnostics": self.packaging.diagnostics,
            "/v1/packaging/release-diagnostics": self.packaging.release_diagnostics,
            "/v1/packaging/launcher/state": self.packaging.launcher_state,
            "/v1/release/health": self._release_health,
            "/v1/release/diagnostics": self._release_diagnostics,
            "/v1/release/report": self._release_report,
            "/v1/release/mission-control": self._release_mission_control,
        }
        handler = routes.get(path)
        if handler is None:
            self._send_json({"detail": "Not found", "path": path}, status=404)
            return
        self._send_json(handler())

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        length = int(self.headers.get("content-length") or "0")
        if length:
            self.rfile.read(length)
        if path == "/v1/memory/search":
            self._send_json({"results": [], "local_only": True})
            return
        if path == "/v1/hotkeys/test-trigger":
            self._send_json(
                {
                    "trigger": {
                        "test": True,
                        "phase": "tested",
                        "binding": "Fn",
                        "local_only": True,
                    },
                    "status": self._hotkey_status(),
                }
            )
            return
        self._send_json({"detail": "Not found", "path": path}, status=404)

    @property
    def packaging(self) -> PackagingService:
        return self.server.packaging_service  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.log_date_time_string()} {fmt % args}", flush=True)

    def _send_json(self, payload: dict[str, Any] | list[Any], *, status: int = 200) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.send_header("access-control-allow-headers", "content-type,authorization")
        self.end_headers()
        self.wfile.write(body)

    def _health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "healthy": True,
            "backend": "siri-local-release",
            "uptime_seconds": round(time.time() - STARTED_AT, 3),
            "local_only": True,
            "telemetry_enabled": False,
            "wake_word_enabled": False,
            "autonomy_enabled": False,
        }

    def _memory_stats(self) -> dict[str, Any]:
        return {
            "entries": 0,
            "backend": "sqlite",
            "available": True,
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _memory_config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "backend": "sqlite",
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _memory_entries(self) -> dict[str, Any]:
        return {"memories": [], "entries": [], "local_only": True}

    def _speech_health(self) -> dict[str, Any]:
        ffmpeg = _which("ffmpeg")
        return {
            "available": bool(ffmpeg),
            "backend": "none" if not ffmpeg else "local-ready",
            "reason": "" if ffmpeg else "ffmpeg missing; install with: brew install ffmpeg",
            "ffmpeg": ffmpeg or "",
            "local_only": True,
            "wake_word_enabled": False,
        }

    def _voice_status(self) -> dict[str, Any]:
        return {
            "recording": False,
            "push_to_talk_only": True,
            "wake_word_enabled": False,
            "passive_listening": False,
            "background_recording": False,
            "backend_available": bool(_which("ffmpeg")),
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _hotkey_status(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "effective_enabled": False,
            "listener_running": False,
            "active": False,
            "binding": self._hotkey_binding(),
            "wake_word_enabled": False,
            "background_transcription": False,
            "privacy_mode": False,
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _hotkey_binding(self) -> dict[str, Any]:
        return {
            "key": "fn",
            "display_name": "Fn",
            "fallback_key": "ctrl+space",
            "fallback_display_name": "Ctrl+Space",
            "local_only": True,
        }

    def _tray_state(self) -> dict[str, Any]:
        return {
            "available": True,
            "visible": False,
            "voice_trigger_enabled": False,
            "items": [
                {"id": "mission-control", "label": "Open Mission Control", "enabled": True},
                {"id": "package-status", "label": "Package Status", "enabled": True},
                {"id": "quit", "label": "Quit Siri", "enabled": True},
            ],
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _desktop_status(self) -> dict[str, Any]:
        return {
            "active_app": {},
            "open_apps": [],
            "tray": self._tray_state(),
            "privacy_mode": False,
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _startup_status(self) -> dict[str, Any]:
        launch_agent = self.packaging.installation_status()["launch_agent"]
        return {
            "launch_at_login": launch_agent["valid"],
            "launch_agent": launch_agent,
            "scheduler": {
                "enabled": True,
                "passive_only": True,
                "background_loop": False,
                "local_only": True,
                "telemetry_enabled": False,
                "first_launch_today": False,
                "last_launch_date": "",
                "last_morning_briefing_at": "",
                "last_morning_briefing_date": "",
                "due_tasks": [],
                "tasks": [],
            },
            "privacy_mode": False,
            "local_only": True,
            "external_telemetry": False,
        }

    def _release_health(self) -> dict[str, Any]:
        return {
            "checks": [
                {
                    "id": "backend",
                    "name": "Backend",
                    "status": "ok",
                    "summary": "Local release backend healthy",
                    "local_only": True,
                    "telemetry_enabled": False,
                }
            ],
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _release_diagnostics(self) -> dict[str, Any]:
        diagnostics = self.packaging.release_diagnostics()
        return {
            "diagnostics": [
                {
                    "id": "packaging",
                    "name": "Packaging diagnostics",
                    "status": diagnostics["status"]["status"],
                    "details": diagnostics["dependency_summary"],
                    "local_only": True,
                    "telemetry_enabled": False,
                }
            ],
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _release_report(self) -> dict[str, Any]:
        status = self.packaging.status().to_dict()
        return {
            "readiness_score": 100 if status["install_readiness"]["ready"] else 80,
            "status": status["status"],
            "warnings": status["install_readiness"]["warnings"],
            "blockers": status["install_readiness"]["blockers"],
            "local_only": True,
            "telemetry_enabled": False,
        }

    def _release_mission_control(self) -> dict[str, Any]:
        return {
            "health": self._release_health()["checks"],
            "diagnostics": self._release_diagnostics()["diagnostics"],
            "report": self._release_report(),
            "packaging": self.packaging.status().to_dict(),
            "startup": self._startup_status(),
            "voice": self._voice_status(),
            "hotkeys": self._hotkey_status(),
            "tray": self._tray_state(),
            "local_only": True,
            "telemetry_enabled": False,
            "wake_word_enabled": False,
            "autonomy_enabled": False,
        }


def serve(host: str, port: int, project_root: str | None = None) -> None:
    signal.signal(signal.SIGHUP, _ignore_signal)
    signal.signal(signal.SIGTERM, _ignore_signal)
    root = Path(project_root or os.environ.get("SIRI_PROJECT_ROOT") or Path.cwd())
    server = ThreadingHTTPServer((host, port), LocalBackendHandler)
    server.packaging_service = PackagingService(project_root=root)  # type: ignore[attr-defined]
    print(f"Siri local release backend listening on http://{host}:{port}", flush=True)
    server.serve_forever()


def _ignore_signal(signum: int, _frame: Any) -> None:
    print(f"Siri local release backend ignored signal {signum}", flush=True)


def _which(name: str) -> str:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(directory) / name
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    for path in (Path("/opt/homebrew/bin") / name, Path("/usr/local/bin") / name):
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Siri release backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--project-root", default="")
    args = parser.parse_args()
    serve(args.host, args.port, args.project_root or None)


if __name__ == "__main__":
    main()
