"""Push-to-talk voice recording service.

This layer is intentionally passive: it records only after an explicit start
call, never installs a wake word listener, and never dispatches a transcript
to an agent by itself.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from openjarvis.core.config import JarvisConfig

if TYPE_CHECKING:
    from openjarvis.speech._stubs import SpeechBackend


LOCAL_TRANSCRIPTION_BACKENDS = {"whisper.cpp", "faster-whisper"}


class VoicePermissionError(RuntimeError):
    """Raised when voice capture needs explicit user approval."""


class VoiceRecordingError(RuntimeError):
    """Raised when the local recorder cannot start or stop cleanly."""


@dataclass
class RecordingHandle:
    """Opaque handle returned by a recorder implementation."""

    recording_id: str
    path: Path
    format: str = "wav"
    process: subprocess.Popen | None = None


class Recorder(Protocol):
    """Recorder protocol used by the PTT service and tests."""

    def start(self, recording_id: str) -> RecordingHandle:
        """Start local microphone capture for *recording_id*."""

    def stop(self, handle: RecordingHandle) -> None:
        """Stop capture for *handle*."""


@dataclass
class VoiceRecordingMetadata:
    """Minimal metadata retained for the latest voice recording."""

    id: str
    state: str
    activation: str = "push_to_talk"
    started_at: float = 0.0
    stopped_at: float | None = None
    duration_seconds: float = 0.0
    byte_size: int = 0
    format: str = "wav"
    backend: str = ""
    agent_id: str = ""
    active_mode_id: str = ""
    privacy_mode: bool = False
    explicit_approval: bool = False
    persisted_raw_audio: bool = False
    raw_audio_available: bool = False
    transcript_preview: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _PermissionRequest:
    tool_name: str
    arguments: dict[str, Any]
    agent_id: str = ""
    command: str | None = None
    permission_ceiling: Any = None
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalMacOSRecorder:
    """macOS microphone recorder using local command-line capture tools."""

    def __init__(
        self,
        *,
        temp_dir: str | os.PathLike[str] | None = None,
        input_device: str = ":0",
        sample_rate: int = 16000,
    ) -> None:
        self._temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self._input_device = input_device
        self._sample_rate = sample_rate

    def start(self, recording_id: str) -> RecordingHandle:
        if platform.system() != "Darwin":
            raise VoiceRecordingError("local microphone recording is supported on macOS")
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        path = self._temp_dir / f"openjarvis-ptt-{recording_id}.wav"
        command = self._record_command(path)
        if not command:
            raise VoiceRecordingError("install ffmpeg or sox to record local microphone audio")
        try:
            process = subprocess.Popen(  # noqa: S603
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise VoiceRecordingError(str(exc)) from exc
        return RecordingHandle(
            recording_id=recording_id,
            path=path,
            format="wav",
            process=process,
        )

    def stop(self, handle: RecordingHandle) -> None:
        process = handle.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if not handle.path.exists():
            raise VoiceRecordingError("recording did not produce an audio file")

    def _record_command(self, path: Path) -> list[str]:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "avfoundation",
                "-i",
                self._input_device,
                "-ac",
                "1",
                "-ar",
                str(self._sample_rate),
                "-y",
                str(path),
            ]
        rec = shutil.which("rec")
        if rec:
            return [
                rec,
                "-q",
                str(path),
                "channels",
                "1",
                "rate",
                str(self._sample_rate),
            ]
        return []


class VoicePushToTalkService:
    """Stateful push-to-talk recording and local transcription coordinator."""

    def __init__(
        self,
        *,
        config: JarvisConfig | None = None,
        speech_backend: "SpeechBackend | None" = None,
        recorder: Recorder | None = None,
        permission_middleware: Any = None,
        mode_registry: Any = None,
        agent_workspace_registry: Any = None,
        context_layer: Any = None,
    ) -> None:
        self._config = config or JarvisConfig()
        self._speech_backend = speech_backend
        self._recorder = recorder or LocalMacOSRecorder(
            input_device=self._config.speech.macos_input_device
        )
        if permission_middleware is None:
            from openjarvis.security.permissions import PermissionMiddleware

            permission_middleware = PermissionMiddleware(mode_registry=mode_registry)
        self._permission_middleware = permission_middleware
        self._mode_registry = mode_registry
        self._agent_workspace_registry = agent_workspace_registry
        self._context_layer = context_layer
        self._handle: RecordingHandle | None = None
        self._latest: VoiceRecordingMetadata | None = None
        self._latest_path: Path | None = None

    def start_recording(
        self,
        *,
        agent_id: str = "",
        explicit_approval: bool = False,
        persist_raw_audio: bool | None = None,
    ) -> VoiceRecordingMetadata:
        """Start a user-initiated push-to-talk recording."""
        if self._handle is not None:
            raise VoiceRecordingError("voice recording is already active")
        active_mode = self._active_mode()
        active_agent_id = agent_id or self._active_agent_id()
        privacy_mode = getattr(active_mode, "id", "") == "privacy"
        persist_audio = (
            self._config.speech.persist_raw_audio
            if persist_raw_audio is None
            else bool(persist_raw_audio)
        )
        self._enforce_capture_approval(
            explicit_approval=explicit_approval,
            privacy_mode=privacy_mode,
        )
        decision = self._permission_middleware.check(
            _PermissionRequest(
                tool_name="voice_microphone_capture",
                arguments={
                    "activation": "push_to_talk",
                    "explicit_approval": explicit_approval,
                },
                agent_id=active_agent_id,
                metadata={
                    "active_mode": active_mode,
                    "active_mode_id": getattr(active_mode, "id", ""),
                    "agent_memory_scope": self._agent_memory_scope(active_agent_id),
                    "explicit_approval": explicit_approval,
                    "passive_only": True,
                    "push_to_talk_only": True,
                },
            )
        )
        if decision.denied:
            raise VoicePermissionError(decision.reason)
        if decision.requires_confirmation and not explicit_approval:
            raise VoicePermissionError(decision.reason)

        recording_id = uuid.uuid4().hex
        started_at = time.time()
        handle = self._recorder.start(recording_id)
        self._handle = handle
        self._latest_path = handle.path
        self._latest = VoiceRecordingMetadata(
            id=recording_id,
            state="recording",
            started_at=started_at,
            format=handle.format,
            agent_id=active_agent_id,
            active_mode_id=getattr(active_mode, "id", ""),
            privacy_mode=privacy_mode,
            explicit_approval=explicit_approval,
            persisted_raw_audio=persist_audio,
            raw_audio_available=True,
            context=self._context_snapshot(privacy_mode=privacy_mode),
        )
        return self._latest

    def stop_recording(self) -> VoiceRecordingMetadata:
        """Stop the active recording without transcribing or dispatching it."""
        if self._handle is None or self._latest is None:
            raise VoiceRecordingError("voice recording is not active")
        handle = self._handle
        self._recorder.stop(handle)
        stopped_at = time.time()
        byte_size = handle.path.stat().st_size if handle.path.exists() else 0
        self._latest.state = "idle"
        self._latest.stopped_at = stopped_at
        self._latest.duration_seconds = max(0.0, stopped_at - self._latest.started_at)
        self._latest.byte_size = byte_size
        self._latest.raw_audio_available = handle.path.exists()
        self._handle = None
        return self._latest

    def status(self) -> dict[str, Any]:
        """Return recording status and minimal metadata."""
        active_mode = self._active_mode()
        privacy_mode = getattr(active_mode, "id", "") == "privacy"
        approval_required = self._approval_required(privacy_mode=privacy_mode)
        metadata = self._latest.to_dict() if self._latest else None
        return {
            "state": "recording" if self._handle is not None else "idle",
            "recording": self._handle is not None,
            "push_to_talk_only": True,
            "wake_word_enabled": False,
            "passive_listening": False,
            "capture_enabled": self._config.speech.voice_capture_enabled,
            "requires_explicit_approval": approval_required,
            "privacy_mode": privacy_mode,
            "active_mode_id": getattr(active_mode, "id", ""),
            "active_agent_id": self._active_agent_id(),
            "latest": metadata,
        }

    def transcribe_latest(
        self,
        *,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Transcribe the most recent stopped recording with a local backend."""
        if self._handle is not None:
            raise VoiceRecordingError("stop recording before transcription")
        if self._latest is None or self._latest_path is None:
            raise VoiceRecordingError("no recording is available to transcribe")
        if not self._latest_path.exists():
            raise VoiceRecordingError("latest raw audio is no longer available")

        backend = self._local_speech_backend()
        audio = self._latest_path.read_bytes()
        result = backend.transcribe(
            audio,
            format=self._latest.format,
            language=language or self._config.speech.language or None,
        )
        self._latest.state = "transcribed"
        self._latest.backend = backend.backend_id
        self._latest.transcript_preview = result.text[:240]
        self._delete_raw_audio_if_needed()
        return {
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "duration_seconds": result.duration_seconds,
            "segments": [asdict(segment) for segment in result.segments],
            "metadata": self._latest.to_dict(),
            "passive_only": True,
            "dispatched_to_agent": False,
        }

    def _local_speech_backend(self) -> "SpeechBackend":
        backend = self._speech_backend
        if backend is not None and backend.backend_id in LOCAL_TRANSCRIPTION_BACKENDS:
            return backend
        try:
            from openjarvis.speech._discovery import _create_backend

            for key in ("whisper.cpp", "faster-whisper"):
                resolved = _create_backend(key, self._config)
                if resolved is not None and resolved.health():
                    return resolved
        except Exception:
            pass
        raise VoiceRecordingError(
            "no local transcription backend is available; configure whisper.cpp "
            "or install faster-whisper"
        )

    def _enforce_capture_approval(
        self,
        *,
        explicit_approval: bool,
        privacy_mode: bool,
    ) -> None:
        enabled = self._config.speech.voice_capture_enabled
        if not enabled and not explicit_approval:
            raise VoicePermissionError("voice capture is disabled until explicitly approved")
        if self._approval_required(privacy_mode=privacy_mode) and not explicit_approval:
            raise VoicePermissionError("voice capture requires explicit push-to-talk approval")

    def _approval_required(self, *, privacy_mode: bool) -> bool:
        return privacy_mode or self._config.speech.require_explicit_voice_approval

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
                "raw_audio_retention": (
                    "explicit_persistent"
                    if self._config.speech.persist_raw_audio
                    else "temporary_until_transcription"
                ),
            },
        }

    def _delete_raw_audio_if_needed(self) -> None:
        if self._latest is None or self._latest.persisted_raw_audio:
            return
        if self._latest_path is not None:
            try:
                self._latest_path.unlink(missing_ok=True)
            except OSError:
                pass
        self._latest.raw_audio_available = False


__all__ = [
    "LOCAL_TRANSCRIPTION_BACKENDS",
    "LocalMacOSRecorder",
    "RecordingHandle",
    "VoicePermissionError",
    "VoicePushToTalkService",
    "VoiceRecordingError",
    "VoiceRecordingMetadata",
]
