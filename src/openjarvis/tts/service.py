"""Local-only text-to-speech service coordinator."""

from __future__ import annotations

import time
import uuid
from typing import Any

from openjarvis.tts.engines import LocalTTSEngine, default_local_engines
from openjarvis.tts.models import (
    TTSPermissionError,
    TTSSpeakRequest,
    TTSSpeech,
    TTSUnavailableError,
    TTSVoice,
)
from openjarvis.tts.permissions import TTSPermissionGate
from openjarvis.tts.state import TTSStateStore


class LocalTTSService:
    """Coordinate explicit local voice output."""

    def __init__(
        self,
        *,
        engines: list[LocalTTSEngine] | None = None,
        permission_middleware: Any = None,
        mode_registry: Any = None,
        agent_workspace_registry: Any = None,
        context_layer: Any = None,
        memory_service: Any = None,
        voice_service: Any = None,
        state_store: TTSStateStore | None = None,
    ) -> None:
        self._engines = engines or default_local_engines()
        if permission_middleware is None:
            from openjarvis.security.permissions import PermissionMiddleware

            permission_middleware = PermissionMiddleware(mode_registry=mode_registry)
        self._permission_gate = TTSPermissionGate(
            permission_middleware=permission_middleware
        )
        self._mode_registry = mode_registry
        self._agent_workspace_registry = agent_workspace_registry
        self._context_layer = context_layer
        self._memory_service = memory_service
        self._voice_service = voice_service
        self._state = state_store or TTSStateStore()

    def speak(
        self,
        text: str,
        *,
        voice_id: str = "",
        engine: str = "",
        user_triggered: bool = True,
        allow_quiet: bool = False,
        speed: float = 1.0,
    ) -> TTSSpeech:
        """Speak text through a local engine after explicit checks."""
        req = TTSSpeakRequest(
            text=text,
            voice_id=voice_id,
            engine=engine,
            user_triggered=user_triggered,
            allow_quiet=allow_quiet,
            speed=speed,
        )
        raw_text = req.text.strip()
        if not raw_text:
            raise TTSUnavailableError("no text provided")

        active_mode = self._active_mode()
        mode_id = getattr(active_mode, "id", "")
        try:
            from openjarvis.personalization.preferences import get_quiet_mode_preference
            if get_quiet_mode_preference():
                mode_id = "quiet"
        except ImportError:
            pass

        if mode_id == "quiet" and not req.allow_quiet:
            raise TTSPermissionError("Quiet Mode disables voice output by default")

        selected = self._select_engine(req.engine, req.voice_id)
        voices = selected.voices()
        selected_voice = self._select_voice_id(selected, voices, req.voice_id)
        active_agent = self._active_agent_id()
        spoken_text, truncated = self._mode_adjusted_text(raw_text, mode_id)
        decision = self._permission_gate.check_speak(
            text=spoken_text,
            engine_id=selected.engine_id,
            voice_id=selected_voice,
            active_mode=active_mode,
            active_agent=active_agent,
            user_triggered=req.user_triggered,
            local_only=True,
            agent_memory_scope=self._agent_memory_scope(active_agent),
        )

        if self._state.active_handle is not None:
            self.stop()

        handle = selected.speak(spoken_text, voice_id=selected_voice, speed=req.speed)
        speech = TTSSpeech(
            id=uuid.uuid4().hex,
            text=raw_text,
            spoken_text=spoken_text,
            started_at=time.time(),
            status="speaking",
            engine=selected.engine_id,
            voice_id=selected_voice,
            active_agent=active_agent,
            active_mode=mode_id,
            truncated=truncated,
            permission_decisions=[decision.to_dict()],
            context=self._context_snapshot(privacy_mode=mode_id == "privacy"),
        )
        self._state.begin(speech, handle)
        self._persist_minimal_memory(speech)
        return speech

    def stop(self) -> TTSSpeech | None:
        """Stop active speech if present."""
        speech = self._state.active_speech
        handle = self._state.active_handle
        if speech is None:
            return None
        engine = self._engine_by_id(speech.engine)
        if engine is not None:
            engine.stop(handle)
        speech.status = "stopped"
        speech.stopped_at = time.time()
        self._state.finish_active()
        return speech

    def status(self) -> dict[str, Any]:
        """Return voice output status for Mission Control."""
        active_mode = self._active_mode()
        mode_id = getattr(active_mode, "id", "")
        try:
            from openjarvis.personalization.preferences import get_quiet_mode_preference
            if get_quiet_mode_preference():
                mode_id = "quiet"
        except ImportError:
            pass
        voices = self.voices()
        selected_voice = self._state.selected_voice_id
        if not selected_voice and voices:
            selected_voice = voices[0].id
        active = self._state.active_speech
        return {
            "state": "speaking" if active is not None else "idle",
            "speaking": active is not None,
            "local_only": True,
            "cloud_tts_enabled": False,
            "autonomous_speech": False,
            "passive_only": True,
            "quiet_mode": mode_id == "quiet",
            "muted": mode_id == "quiet",
            "privacy_mode": mode_id == "privacy",
            "active_mode_id": mode_id,
            "active_agent_id": self._active_agent_id(),
            "selected_voice_id": selected_voice,
            "selected_engine": self._state.selected_engine
            or (voices[0].engine if voices else ""),
            "available": any(engine.available() for engine in self._engines),
            "available_engines": [
                engine.engine_id for engine in self._engines if engine.available()
            ],
            "response_style": self._response_style(mode_id),
            "voice_input": self._voice_status_snapshot(),
            "latest": self._state.latest_speech.to_dict()
            if self._state.latest_speech
            else None,
        }

    def voices(self) -> list[TTSVoice]:
        """Return voices from all local engines."""
        all_voices: list[TTSVoice] = []
        for engine in self._engines:
            try:
                all_voices.extend(engine.voices())
            except Exception:
                continue
        return all_voices

    def _select_engine(self, requested_engine: str, requested_voice: str):
        engines = [engine for engine in self._engines if engine.available()]
        if not engines:
            raise TTSUnavailableError("no local TTS engine is available")
        if requested_engine:
            for engine in engines:
                if engine.engine_id == requested_engine:
                    return engine
            raise TTSUnavailableError(
                f"local TTS engine '{requested_engine}' is unavailable"
            )
        if requested_voice:
            for engine in engines:
                if any(voice.id == requested_voice for voice in engine.voices()):
                    return engine
        if self._state.selected_engine:
            for engine in engines:
                if engine.engine_id == self._state.selected_engine:
                    return engine
        return engines[0]

    @staticmethod
    def _select_voice_id(
        engine: LocalTTSEngine,
        voices: list[TTSVoice],
        requested_voice: str,
    ) -> str:
        if requested_voice:
            return requested_voice
        return voices[0].id if voices else ""

    def _engine_by_id(self, engine_id: str):
        for engine in self._engines:
            if engine.engine_id == engine_id:
                return engine
        return None

    def _active_mode(self) -> Any:
        if self._mode_registry is None:
            return None
        try:
            return self._mode_registry.get_active_mode().mode
        except Exception:
            return None

    def _active_agent_id(self) -> str:
        if self._agent_workspace_registry is None:
            return ""
        try:
            return self._agent_workspace_registry.get_active_agent().active_agent_id
        except Exception:
            return ""

    def _agent_memory_scope(self, agent_id: str) -> list[str]:
        if not agent_id or self._agent_workspace_registry is None:
            return []
        try:
            return list(self._agent_workspace_registry.memory_scopes_for(agent_id))
        except Exception:
            return []

    def _context_snapshot(self, *, privacy_mode: bool) -> dict[str, Any]:
        layer = self._context_layer
        project: dict[str, Any] = {}
        desktop: dict[str, Any] = {}
        if layer is None:
            try:
                from openjarvis.context import ContextLayer

                layer = ContextLayer()
            except Exception:
                layer = None
        if layer is not None:
            try:
                project = layer.current_project_context().to_dict()
            except Exception:
                project = {}
            try:
                desktop = layer.current_desktop_context(
                    privacy_mode=privacy_mode
                ).to_dict()
            except Exception:
                desktop = {}
        return {
            "desktop": desktop,
            "project": project,
            "voice_output": {
                "local_only": True,
                "user_triggered": True,
                "autonomous_speech": False,
            },
        }

    def _voice_status_snapshot(self) -> dict[str, Any]:
        if self._voice_service is None:
            return {
                "push_to_talk_only": True,
                "wake_word_enabled": False,
                "passive_listening": False,
            }
        try:
            status = self._voice_service.status()
            return {
                "push_to_talk_only": status.get("push_to_talk_only", True),
                "wake_word_enabled": status.get("wake_word_enabled", False),
                "passive_listening": status.get("passive_listening", False),
                "recording": status.get("recording", False),
            }
        except Exception:
            return {
                "push_to_talk_only": True,
                "wake_word_enabled": False,
                "passive_listening": False,
            }

    @staticmethod
    def _mode_adjusted_text(text: str, mode_id: str) -> tuple[str, bool]:
        limits = {
            "quiet": 140,
            "focus": 260,
            "research": 1400,
        }
        limit = limits.get(mode_id, 700)
        if len(text) <= limit:
            return text, False
        return text[: max(0, limit - 3)].rstrip() + "...", True

    @staticmethod
    def _response_style(mode_id: str) -> str:
        if mode_id == "quiet":
            return "muted_by_default"
        if mode_id == "focus":
            return "short"
        if mode_id == "research":
            return "long_summary"
        return "balanced"

    def _persist_minimal_memory(self, speech: TTSSpeech) -> None:
        if self._memory_service is None or speech.active_mode == "privacy":
            return
        try:
            self._memory_service.create_memory(
                "Voice output metadata",
                memory_type="agent_run",
                metadata={
                    "id": speech.id,
                    "status": speech.status,
                    "engine": speech.engine,
                    "voice_id": speech.voice_id,
                    "active_agent": speech.active_agent,
                    "active_mode": speech.active_mode,
                    "text_length": len(speech.text),
                    "spoken_text_length": len(speech.spoken_text),
                    "local_only": speech.local_only,
                    "user_triggered": speech.user_triggered,
                    "autonomous_speech": speech.autonomous_speech,
                    "truncated": speech.truncated,
                },
                tags=["voice", "tts", "local-only"],
            )
        except Exception:
            return


__all__ = ["LocalTTSService"]
