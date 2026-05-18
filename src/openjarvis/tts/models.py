"""Models for local-only voice output."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class TTSError(RuntimeError):
    """Base error for text-to-speech failures."""


class TTSUnavailableError(TTSError):
    """Raised when no local text-to-speech engine is available."""


class TTSPermissionError(TTSError):
    """Raised when voice output is blocked by mode or permissions."""


@dataclass(slots=True)
class TTSVoice:
    """A local voice exposed by a TTS engine."""

    id: str
    name: str
    engine: str
    locale: str = ""
    local_only: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TTSSpeakRequest:
    """Normalized request accepted by the TTS service."""

    text: str
    voice_id: str = ""
    engine: str = ""
    user_triggered: bool = True
    allow_quiet: bool = False
    speed: float = 1.0


@dataclass(slots=True)
class TTSSpeech:
    """Metadata for the currently active or latest speech request."""

    id: str
    text: str
    spoken_text: str
    started_at: float
    stopped_at: float | None = None
    status: str = "speaking"
    engine: str = ""
    voice_id: str = ""
    active_agent: str = ""
    active_mode: str = ""
    local_only: bool = True
    user_triggered: bool = True
    passive_only: bool = True
    autonomous_speech: bool = False
    truncated: bool = False
    permission_decisions: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["text_length"] = len(self.text)
        data["spoken_text_length"] = len(self.spoken_text)
        return data


@dataclass(slots=True)
class TTSPermissionDecision:
    """Voice-output permission decision summary."""

    action: str
    level: str
    reason: str
    requires_approval: bool = False
    matched_pattern: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "TTSError",
    "TTSPermissionDecision",
    "TTSPermissionError",
    "TTSSpeakRequest",
    "TTSSpeech",
    "TTSUnavailableError",
    "TTSVoice",
]
