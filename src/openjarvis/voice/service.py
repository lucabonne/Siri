"""Passive push-to-talk voice service coordinator."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from openjarvis.core.config import JarvisConfig
from openjarvis.voice.models import (
    TranscriptionUnavailableError,
    VoiceIntentPreview,
    VoiceRecordingError,
    VoiceSession,
)
from openjarvis.voice.permissions import VoicePermissionGate
from openjarvis.voice.recorder import LocalMacOSRecorder, Recorder
from openjarvis.voice.state import VoiceStateStore
from openjarvis.voice.transcription import LocalVoiceTranscriber


class VoicePushToTalkService:
    """Coordinate explicit PTT capture, transcription, and preview."""

    def __init__(
        self,
        *,
        config: JarvisConfig | None = None,
        recorder: Recorder | None = None,
        transcriber: LocalVoiceTranscriber | None = None,
        speech_backend: Any = None,
        permission_middleware: Any = None,
        approval_queue: Any = None,
        mode_registry: Any = None,
        agent_workspace_registry: Any = None,
        context_layer: Any = None,
        memory_service: Any = None,
        state_store: VoiceStateStore | None = None,
    ) -> None:
        self._config = config or JarvisConfig()
        self._recorder = recorder or LocalMacOSRecorder(
            input_device=self._config.speech.macos_input_device
        )
        self._transcriber = transcriber or LocalVoiceTranscriber(
            config=self._config,
            backend=speech_backend,
        )
        if permission_middleware is None:
            from openjarvis.security.permissions import PermissionMiddleware

            permission_middleware = PermissionMiddleware(mode_registry=mode_registry)
        self._permission_gate = VoicePermissionGate(
            permission_middleware=permission_middleware,
            approval_queue=approval_queue,
            config=self._config,
        )
        self._mode_registry = mode_registry
        self._agent_workspace_registry = agent_workspace_registry
        self._context_layer = context_layer
        self._memory_service = memory_service
        self._state = state_store or VoiceStateStore()

    def start_recording(
        self,
        *,
        agent_id: str = "",
        explicit_approval: bool = False,
        persist_raw_audio: bool | None = None,
    ) -> VoiceSession:
        """Start a user-initiated push-to-talk recording."""
        if self._state.active_handle is not None:
            raise VoiceRecordingError("voice recording is already active")
        active_mode = self._active_mode()
        active_agent = agent_id or self._active_agent_id()
        persist_audio = self._persist_raw_audio(persist_raw_audio)
        permission = self._permission_gate.check_start(
            active_mode=active_mode,
            active_agent=active_agent,
            explicit_approval=explicit_approval,
            agent_memory_scope=self._agent_memory_scope(active_agent),
        )
        recording_id = uuid.uuid4().hex
        handle = self._recorder.start(recording_id)
        now = time.time()
        session = VoiceSession(
            id=recording_id,
            started_at=now,
            audio_path=str(handle.path),
            active_agent=active_agent,
            active_mode=getattr(active_mode, "id", ""),
            permission_decisions=[permission.to_dict()],
            status="recording",
            format=handle.format,
            persisted_raw_audio=persist_audio,
            raw_audio_available=True,
            context=self._context_snapshot(
                privacy_mode=getattr(active_mode, "id", "") == "privacy"
            ),
        )
        self._state.begin(session, handle)
        return session

    def stop_recording(self) -> VoiceSession:
        """Stop the active recording without transcribing or executing it."""
        handle = self._state.active_handle
        session = self._state.active_session
        if handle is None or session is None:
            raise VoiceRecordingError("voice recording is not active")
        self._recorder.stop(handle)
        stopped_at = time.time()
        path = Path(handle.path)
        session.stopped_at = stopped_at
        session.duration = max(0.0, stopped_at - session.started_at)
        session.byte_size = path.stat().st_size if path.exists() else 0
        session.raw_audio_available = path.exists()
        session.status = "recorded"
        self._state.finish_active()
        return session

    def status(self) -> dict[str, Any]:
        """Return passive PTT status and latest session metadata."""
        active_mode = self._active_mode()
        privacy_mode = getattr(active_mode, "id", "") == "privacy"
        latest = self._state.latest_session
        capture_enabled = self._config.speech.voice_capture_enabled
        try:
            from openjarvis.personalization.preferences import get_voice_interaction_enabled
            if get_voice_interaction_enabled():
                capture_enabled = True
        except ImportError:
            pass

        return {
            "state": "recording" if self._state.active_handle is not None else "idle",
            "recording": self._state.active_handle is not None,
            "push_to_talk_only": True,
            "wake_word_enabled": False,
            "passive_listening": False,
            "background_recording": False,
            "capture_enabled": capture_enabled,
            "requires_explicit_approval": (
                privacy_mode or self._config.speech.require_explicit_voice_approval
            ),
            "privacy_mode": privacy_mode,
            "active_mode_id": getattr(active_mode, "id", ""),
            "active_agent_id": self._active_agent_id(),
            "transcription_available": self._transcriber.available(),
            "latest": latest.to_dict() if latest else None,
        }

    def transcribe_latest(self, *, language: str | None = None) -> dict[str, Any]:
        """Transcribe latest stopped recording and return an intent preview."""
        if self._state.active_handle is not None:
            raise VoiceRecordingError("stop recording before transcription")
        session = self._state.latest_session
        if session is None:
            raise VoiceRecordingError("no recording is available to transcribe")
        if not session.audio_path or not Path(session.audio_path).exists():
            raise VoiceRecordingError("latest raw audio is no longer available")
        try:
            audio = Path(session.audio_path).read_bytes()
            result = self._transcriber.transcribe(
                audio,
                format=session.format,
                language=language,
            )
        except TranscriptionUnavailableError:
            session.status = "transcription_unavailable"
            return {
                "status": "transcription_backend_unavailable",
                "reason": (
                    "transcription backend unavailable: install faster-whisper "
                    "for local voice transcription"
                ),
                "session": session.to_dict(),
                "passive_only": True,
                "dispatched_to_agent": False,
            }

        session.transcript = result.text
        session.backend = result.backend
        session.status = "preview_ready"
        session.intent_preview = self.preview_intent(result.text)
        self._state.clear_audio_if_needed(
            persist_raw_audio=session.persisted_raw_audio
        )
        self._persist_minimal_memory(session)
        return {
            "status": "preview_ready",
            "transcript": result.text,
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "duration_seconds": result.duration_seconds,
            "segments": result.to_dict()["segments"],
            "intent_preview": session.intent_preview.to_dict(),
            "session": session.to_dict(),
            "metadata": session.to_dict(),
            "passive_only": True,
            "dispatched_to_agent": False,
        }

    def preview_intent(self, transcript: str) -> VoiceIntentPreview:
        """Return a passive intent preview without execution."""
        text = transcript.strip()
        lower = text.lower()
        planned_actions = ["preview transcript"]
        risk = "low"
        approval_required = False
        intent = "dictation"
        if "?" in text or lower.startswith(("what", "why", "how", "when", "where")):
            intent = "question"
            planned_actions.append("route to active agent if user submits")
        if any(
            token in lower
            for token in ("run ", "delete ", "send ", "open ", "commit ")
        ):
            intent = "action_request"
            planned_actions.append("request explicit approval before execution")
            risk = "medium"
            approval_required = True
        return VoiceIntentPreview(
            transcript=text,
            interpreted_intent=intent,
            planned_actions=planned_actions,
            risk_level=risk,
            approval_required=approval_required,
        )

    def _persist_raw_audio(self, override: bool | None) -> bool:
        return (
            self._config.speech.persist_raw_audio
            if override is None
            else bool(override)
        )

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
        if layer is None:
            try:
                from openjarvis.context import ContextLayer

                layer = ContextLayer()
            except Exception:
                return {}
        try:
            project = layer.current_project_context().to_dict()
        except Exception:
            project = {}
        try:
            desktop = layer.current_desktop_context(privacy_mode=privacy_mode).to_dict()
        except Exception:
            desktop = {}
        return {
            "desktop": desktop,
            "project": project,
            "voice": {
                "activation": "push_to_talk",
                "passive_only": True,
                "wake_word_enabled": False,
                "background_recording": False,
                "raw_audio_retention": (
                    "explicit_persistent"
                    if self._config.speech.persist_raw_audio
                    else "temporary_until_transcription"
                ),
            },
        }

    def _persist_minimal_memory(self, session: VoiceSession) -> None:
        if self._memory_service is None or session.active_mode == "privacy":
            return
        try:
            self._memory_service.create_memory(
                "Voice push-to-talk metadata",
                memory_type="agent_run",
                metadata=session.minimal_metadata(),
                tags=["voice", "push-to-talk"],
            )
        except Exception:
            return


__all__ = ["VoicePushToTalkService"]
