"""Local-only voice transcription for push-to-talk sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openjarvis.core.config import JarvisConfig
from openjarvis.voice.models import TranscriptionUnavailableError


@dataclass
class LocalTranscriptionResult:
    """Normalized local transcription result."""

    text: str
    language: str | None = None
    confidence: float | None = None
    duration_seconds: float = 0.0
    backend: str = ""
    segments: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "confidence": self.confidence,
            "duration_seconds": self.duration_seconds,
            "backend": self.backend,
            "segments": [
                segment.to_dict() if hasattr(segment, "to_dict") else vars(segment)
                for segment in self.segments
            ],
        }


class LocalVoiceTranscriber:
    """Resolve and use faster-whisper only for PTT transcription."""

    def __init__(self, *, config: JarvisConfig | None = None, backend: Any = None) -> None:
        self._config = config or JarvisConfig()
        self._backend = backend

    def available(self) -> bool:
        backend = self._backend
        if backend is not None:
            return backend.backend_id == "faster-whisper" and backend.health()
        try:
            return self._resolve_backend().health()
        except TranscriptionUnavailableError:
            return False

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: str | None = None,
    ) -> LocalTranscriptionResult:
        backend = self._resolve_backend()
        result = backend.transcribe(
            audio,
            format=format,
            language=language or self._config.speech.language or None,
        )
        return LocalTranscriptionResult(
            text=result.text,
            language=result.language,
            confidence=result.confidence,
            duration_seconds=result.duration_seconds,
            backend=backend.backend_id,
            segments=list(result.segments),
        )

    def _resolve_backend(self):
        backend = self._backend
        if backend is not None and backend.backend_id == "faster-whisper":
            if backend.health():
                return backend
            raise TranscriptionUnavailableError(
                "transcription backend unavailable: faster-whisper is not ready"
            )

        try:
            from openjarvis.speech._discovery import _create_backend

            resolved = _create_backend("faster-whisper", self._config)
            if resolved is not None and resolved.health():
                return resolved
        except Exception:
            pass
        raise TranscriptionUnavailableError(
            "transcription backend unavailable: install faster-whisper for local voice transcription"
        )


__all__ = ["LocalTranscriptionResult", "LocalVoiceTranscriber"]
