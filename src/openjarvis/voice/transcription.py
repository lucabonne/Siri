"""Local-only voice transcription adapters for push-to-talk sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from openjarvis.core.config import JarvisConfig
from openjarvis.voice.models import TranscriptionUnavailableError

LOCAL_TRANSCRIPTION_ADAPTERS = ("faster-whisper", "whisper.cpp")

LOCAL_TRANSCRIPTION_SETUP_HINTS = {
    "faster-whisper": (
        "install the optional dependency with `uv sync --extra speech` and set "
        "[speech].model to a supported faster-whisper model name or an existing "
        "local CTranslate2 model directory"
    ),
    "whisper.cpp": (
        "install whisper.cpp, ensure `whisper-cli` is on PATH or set "
        "WHISPER_CPP_BINARY, and set WHISPER_CPP_MODEL to an existing ggml model file"
    ),
}

EXPECTED_FUTURE_TRANSCRIPTION_ADAPTERS = (
    {
        "adapter_id": "whisper.cpp",
        "local_only": True,
        "status": "optional",
        "notes": (
            "Local subprocess adapter for explicitly configured whisper.cpp binaries."
        ),
    },
    {
        "adapter_id": "faster-whisper",
        "local_only": True,
        "status": "optional",
        "notes": (
            "Local CTranslate2 adapter for explicitly selected faster-whisper models."
        ),
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
        try:
            result = backend.transcribe(
                audio,
                format=format,
                language=language or self._config.speech.language or None,
            )
        except TranscriptionUnavailableError:
            raise
        except Exception as exc:
            raise TranscriptionUnavailableError(
                self._setup_error(reason=str(exc))
            ) from exc
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
            resolved = self._create_local_backend()
            if resolved.health():
                return resolved
        except TranscriptionUnavailableError:
            raise
        except Exception as exc:
            raise TranscriptionUnavailableError(
                self._setup_error(reason=str(exc))
            ) from exc
        raise TranscriptionUnavailableError(self._setup_error())

    def _create_local_backend(self):
        if self.adapter_id == "faster-whisper":
            model = self._config.speech.model
            model_path = Path(model).expanduser()
            if _looks_like_model_path(model) and not model_path.exists():
                raise TranscriptionUnavailableError(
                    f"faster-whisper model path does not exist: {model_path}"
                )
            from openjarvis.speech.faster_whisper import FasterWhisperBackend

            return FasterWhisperBackend(
                model_size=model,
                device=self._config.speech.device,
                compute_type=self._config.speech.compute_type,
            )
        if self.adapter_id == "whisper.cpp":
            from openjarvis.speech.whisper_cpp import WhisperCppBackend

            return WhisperCppBackend()
        raise TranscriptionUnavailableError(
            f"unsupported local transcription adapter: {self.adapter_id}"
        )

    def _setup_error(self, *, reason: str = "") -> str:
        hint = LOCAL_TRANSCRIPTION_SETUP_HINTS[self.adapter_id]
        message = f"{self.adapter_id} transcription adapter unavailable; {hint}."
        if reason:
            message = f"{message} Reason: {reason}"
        return message

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
        if adapter is not None:
            self._adapter = adapter
        elif backend is not None:
            self._adapter = SpeechBackendLocalTranscriptionAdapter(
                adapter_id=backend.backend_id,
                config=self._config,
                backend=backend,
            )
        elif self._config.speech.backend in LOCAL_TRANSCRIPTION_ADAPTERS:
            self._adapter = SpeechBackendLocalTranscriptionAdapter(
                adapter_id=self._config.speech.backend,
                config=self._config,
            )
        else:
            self._adapter = DisabledLocalTranscriptionAdapter()

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


class DisabledLocalTranscriptionAdapter:
    """Adapter used when local transcription has not been explicitly enabled."""

    adapter_id = "disabled"

    def available(self) -> bool:
        return False

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: str | None = None,
    ) -> LocalTranscriptionResult:
        raise TranscriptionUnavailableError(local_transcription_disabled_message())

    def transcribe_file(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
    ) -> LocalTranscriptionResult:
        raise TranscriptionUnavailableError(local_transcription_disabled_message())


def resolve_local_transcription_adapter_id(
    *,
    requested_adapter: str | None,
    config: JarvisConfig,
) -> str:
    """Resolve an explicitly selected or configured local transcription adapter."""
    if requested_adapter:
        if requested_adapter not in LOCAL_TRANSCRIPTION_ADAPTERS:
            raise ValueError(
                f"unsupported local transcription adapter: {requested_adapter}"
            )
        return requested_adapter
    if config.speech.backend in LOCAL_TRANSCRIPTION_ADAPTERS:
        return config.speech.backend
    raise TranscriptionUnavailableError(local_transcription_disabled_message())


def local_transcription_disabled_message() -> str:
    adapters = ", ".join(LOCAL_TRANSCRIPTION_ADAPTERS)
    return (
        "local voice transcription is disabled; select an adapter with "
        f"`--adapter` or set [speech].backend to one of: {adapters}"
    )


def _looks_like_model_path(model: str) -> bool:
    return (
        "/" in model or "\\" in model or model.startswith(".") or model.startswith("~")
    )


__all__ = [
    "EXPECTED_FUTURE_TRANSCRIPTION_ADAPTERS",
    "LOCAL_TRANSCRIPTION_ADAPTERS",
    "LocalTranscriptionAdapter",
    "LocalTranscriptionResult",
    "LocalVoiceTranscriber",
    "DisabledLocalTranscriptionAdapter",
    "LOCAL_TRANSCRIPTION_SETUP_HINTS",
    "SpeechBackendLocalTranscriptionAdapter",
    "local_transcription_disabled_message",
    "resolve_local_transcription_adapter_id",
]
