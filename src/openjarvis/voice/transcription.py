"""Local-only voice transcription adapters for push-to-talk sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from openjarvis.core.config import JarvisConfig
from openjarvis.voice.models import TranscriptionUnavailableError

LOCAL_TRANSCRIPTION_ADAPTERS = ("faster-whisper", "whisper.cpp")

EXPECTED_FUTURE_TRANSCRIPTION_ADAPTERS = (
    {
        "adapter_id": "whisper.cpp",
        "local_only": True,
        "status": "planned",
        "notes": "Local subprocess adapter for installed whisper.cpp binaries.",
    },
    {
        "adapter_id": "faster-whisper",
        "local_only": True,
        "status": "planned",
        "notes": "Local CTranslate2 adapter for faster-whisper models.",
    },
    {
        "adapter_id": "macos-dictation",
        "local_only": True,
        "status": "deferred",
        "notes": "Fallback only if explicitly enabled in a later phase.",
    },
)


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


class LocalTranscriptionAdapter(Protocol):
    """Protocol implemented by local audio transcription adapters."""

    adapter_id: str

    def available(self) -> bool:
        """Return whether this adapter can transcribe on the current machine."""

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: str | None = None,
    ) -> LocalTranscriptionResult:
        """Transcribe in-memory audio bytes without dispatching the transcript."""

    def transcribe_file(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
    ) -> LocalTranscriptionResult:
        """Transcribe a local audio file without dispatching the transcript."""


class SpeechBackendLocalTranscriptionAdapter:
    """Local adapter wrapper around speech backends such as faster-whisper."""

    def __init__(
        self,
        *,
        adapter_id: str = "faster-whisper",
        config: JarvisConfig | None = None,
        backend: Any = None,
    ) -> None:
        if adapter_id not in LOCAL_TRANSCRIPTION_ADAPTERS:
            raise ValueError(f"unsupported local transcription adapter: {adapter_id}")
        self.adapter_id = adapter_id
        self._config = config or JarvisConfig()
        self._backend = backend

    def available(self) -> bool:
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
        return self._normalize_result(result, backend_id=backend.backend_id)

    def transcribe_file(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
    ) -> LocalTranscriptionResult:
        path = Path(audio_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(path)
        if not path.is_file():
            raise IsADirectoryError(path)
        suffix = path.suffix.lstrip(".").lower()
        return self.transcribe(
            path.read_bytes(),
            format=suffix or "wav",
            language=language,
        )

    def _resolve_backend(self):
        backend = self._backend
        if backend is not None:
            if backend.backend_id != self.adapter_id:
                raise TranscriptionUnavailableError(
                    f"{self.adapter_id} adapter received {backend.backend_id} backend"
                )
            if backend.health():
                return backend
            raise TranscriptionUnavailableError(
                f"transcription backend unavailable: {self.adapter_id} is not ready"
            )

        try:
            from openjarvis.speech._discovery import _create_backend

            resolved = _create_backend(self.adapter_id, self._config)
            if resolved is not None and resolved.health():
                return resolved
        except Exception:
            pass
        raise TranscriptionUnavailableError(
            f"transcription backend unavailable: configure {self.adapter_id} locally"
        )

    @staticmethod
    def _normalize_result(
        result: Any,
        *,
        backend_id: str,
    ) -> LocalTranscriptionResult:
        return LocalTranscriptionResult(
            text=result.text,
            language=result.language,
            confidence=result.confidence,
            duration_seconds=result.duration_seconds,
            backend=backend_id,
            segments=list(result.segments),
        )


class LocalVoiceTranscriber:
    """Resolve and use a local adapter for PTT transcription."""

    def __init__(
        self,
        *,
        config: JarvisConfig | None = None,
        adapter: LocalTranscriptionAdapter | None = None,
        backend: Any = None,
    ) -> None:
        self._config = config or JarvisConfig()
        self._adapter = adapter or SpeechBackendLocalTranscriptionAdapter(
            adapter_id="faster-whisper",
            config=self._config,
            backend=backend,
        )

    def available(self) -> bool:
        return self._adapter.available()

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: str | None = None,
    ) -> LocalTranscriptionResult:
        return self._adapter.transcribe(
            audio,
            format=format,
            language=language or self._config.speech.language or None,
        )

    def transcribe_file(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
    ) -> LocalTranscriptionResult:
        return self._adapter.transcribe_file(
            audio_path,
            language=language or self._config.speech.language or None,
        )


__all__ = [
    "EXPECTED_FUTURE_TRANSCRIPTION_ADAPTERS",
    "LOCAL_TRANSCRIPTION_ADAPTERS",
    "LocalTranscriptionAdapter",
    "LocalTranscriptionResult",
    "LocalVoiceTranscriber",
    "SpeechBackendLocalTranscriptionAdapter",
]
