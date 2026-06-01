from __future__ import annotations

from pathlib import Path

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.speech._stubs import Segment, TranscriptionResult
from openjarvis.voice.models import TranscriptionUnavailableError
from openjarvis.voice.transcription import (
    EXPECTED_FUTURE_TRANSCRIPTION_ADAPTERS,
    LOCAL_TRANSCRIPTION_ADAPTERS,
    LocalVoiceTranscriber,
    SpeechBackendLocalTranscriptionAdapter,
    resolve_local_transcription_adapter_id,
)


class FakeBackend:
    backend_id = "faster-whisper"

    def __init__(self) -> None:
        self.calls: list[tuple[bytes, str, str | None]] = []

    def health(self) -> bool:
        return True

    def supported_formats(self):
        return ["wav", "mp3"]

    def transcribe(self, audio: bytes, *, format: str = "wav", language=None):
        self.calls.append((audio, format, language))
        return TranscriptionResult(
            text="hello from file",
            language=language,
            confidence=0.88,
            duration_seconds=2.0,
            segments=[Segment(text="hello", start=0.0, end=1.0)],
        )


def test_file_adapter_reads_local_audio_without_dispatch(tmp_path: Path) -> None:
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"fake audio")
    backend = FakeBackend()
    adapter = SpeechBackendLocalTranscriptionAdapter(
        adapter_id="faster-whisper",
        backend=backend,
    )

    result = adapter.transcribe_file(audio_path, language="en")

    assert result.text == "hello from file"
    assert result.backend == "faster-whisper"
    assert result.segments[0].text == "hello"
    assert backend.calls == [(b"fake audio", "mp3", "en")]


def test_adapter_rejects_cloud_or_unknown_adapter() -> None:
    with pytest.raises(ValueError, match="unsupported local transcription adapter"):
        SpeechBackendLocalTranscriptionAdapter(adapter_id="openai")


def test_adapter_reports_unavailable_backend() -> None:
    class UnhealthyBackend(FakeBackend):
        def health(self) -> bool:
            return False

    adapter = SpeechBackendLocalTranscriptionAdapter(
        adapter_id="faster-whisper",
        backend=UnhealthyBackend(),
    )

    assert adapter.available() is False
    with pytest.raises(TranscriptionUnavailableError):
        adapter.transcribe(b"audio")


def test_local_voice_transcriber_uses_adapter() -> None:
    backend = FakeBackend()
    transcriber = LocalVoiceTranscriber(backend=backend)

    result = transcriber.transcribe(b"fake wav", format="wav", language="en")

    assert result.text == "hello from file"
    assert backend.calls == [(b"fake wav", "wav", "en")]


def test_local_voice_transcriber_is_disabled_without_explicit_adapter() -> None:
    transcriber = LocalVoiceTranscriber(config=JarvisConfig())

    assert transcriber.available() is False
    with pytest.raises(TranscriptionUnavailableError, match="disabled"):
        transcriber.transcribe(b"fake wav")


def test_configured_local_adapter_is_resolved() -> None:
    config = JarvisConfig()
    config.speech.backend = "faster-whisper"

    assert (
        resolve_local_transcription_adapter_id(
            requested_adapter=None,
            config=config,
        )
        == "faster-whisper"
    )
    assert (
        resolve_local_transcription_adapter_id(
            requested_adapter="whisper.cpp",
            config=JarvisConfig(),
        )
        == "whisper.cpp"
    )


def test_faster_whisper_missing_local_model_path_is_clear() -> None:
    config = JarvisConfig()
    config.speech.model = "/missing/openjarvis/faster-whisper-model"
    adapter = SpeechBackendLocalTranscriptionAdapter(
        adapter_id="faster-whisper",
        config=config,
    )

    with pytest.raises(
        TranscriptionUnavailableError,
        match="model path does not exist",
    ):
        adapter.transcribe(b"audio")


def test_expected_future_adapters_are_documented() -> None:
    expected = {item["adapter_id"] for item in EXPECTED_FUTURE_TRANSCRIPTION_ADAPTERS}

    assert set(LOCAL_TRANSCRIPTION_ADAPTERS) == {"faster-whisper", "whisper.cpp"}
    assert {"whisper.cpp", "faster-whisper", "macos-dictation"} <= expected
