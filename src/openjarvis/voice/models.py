"""Models for explicit push-to-talk voice sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class VoicePermissionError(RuntimeError):
    """Raised when microphone capture is blocked or needs approval."""


class VoiceRecordingError(RuntimeError):
    """Raised when local microphone capture cannot proceed."""


class TranscriptionUnavailableError(RuntimeError):
    """Raised when no local transcription backend is available."""


@dataclass
class RecordingHandle:
    """Opaque handle returned by the recorder implementation."""

    recording_id: str
    path: Path
    format: str = "wav"
    process: Any = None
    started_at: float = 0.0


@dataclass
class VoicePermissionDecision:
    """Voice-specific permission decision summary."""

    action: str
    level: str
    reason: str
    requires_approval: bool = False
    approval_id: str = ""
    matched_pattern: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VoiceIntentPreview:
    """Passive interpretation of a transcript without execution."""

    transcript: str
    interpreted_intent: str
    planned_actions: list[str] = field(default_factory=list)
    risk_level: str = "low"
    approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VoiceSession:
    """Push-to-talk voice session state and minimal metadata."""

    id: str
    started_at: float
    stopped_at: float | None = None
    duration: float = 0.0
    audio_path: str = ""
    transcript: str = ""
    active_agent: str = ""
    active_mode: str = ""
    permission_decisions: list[dict[str, Any]] = field(default_factory=list)
    invoked_tools: list[str] = field(default_factory=list)
    status: str = "recording"
    format: str = "wav"
    byte_size: int = 0
    backend: str = ""
    persisted_raw_audio: bool = False
    raw_audio_available: bool = False
    context: dict[str, Any] = field(default_factory=dict)
    intent_preview: VoiceIntentPreview | None = None
    passive_only: bool = True
    local_only: bool = True
    wake_word_enabled: bool = False
    background_recording: bool = False

    @property
    def duration_seconds(self) -> float:
        return self.duration

    def minimal_metadata(self) -> dict[str, Any]:
        """Return metadata safe for default persistence."""
        return {
            "id": self.id,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "duration": self.duration,
            "active_agent": self.active_agent,
            "active_mode": self.active_mode,
            "status": self.status,
            "byte_size": self.byte_size,
            "backend": self.backend,
            "transcript_length": len(self.transcript),
            "permission_decisions": self.permission_decisions,
            "invoked_tools": list(self.invoked_tools),
            "persisted_raw_audio": self.persisted_raw_audio,
            "raw_audio_available": self.raw_audio_available,
            "passive_only": self.passive_only,
            "local_only": self.local_only,
            "wake_word_enabled": self.wake_word_enabled,
            "background_recording": self.background_recording,
        }

    def to_dict(self, *, expose_audio_path: bool | None = None) -> dict[str, Any]:
        expose = (
            self.persisted_raw_audio if expose_audio_path is None else expose_audio_path
        )
        data = asdict(self)
        data["duration_seconds"] = self.duration
        data["audio_path"] = self.audio_path if expose else ""
        data["intent_preview"] = (
            self.intent_preview.to_dict() if self.intent_preview is not None else None
        )
        return data


__all__ = [
    "RecordingHandle",
    "TranscriptionUnavailableError",
    "VoiceIntentPreview",
    "VoicePermissionDecision",
    "VoicePermissionError",
    "VoiceRecordingError",
    "VoiceSession",
]
