"""Tests for the local typed/mock voice CLI bridge."""

from __future__ import annotations

import importlib.util
import wave
from pathlib import Path
from typing import Any

from click.testing import CliRunner


def _load_voice_cmd_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "openjarvis"
        / "cli"
        / "voice_cmd.py"
    )
    spec = importlib.util.spec_from_file_location("voice_cmd_under_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


voice_cmd = _load_voice_cmd_module()


def _preview_response() -> dict[str, Any]:
    return {
        "status": "awaiting_approval",
        "fsm_state": "awaiting_approval",
        "transcript": "open notes",
        "intent_preview": {
            "interpreted_intent": "action_request",
            "risk_level": "medium",
            "approval_required": True,
            "planned_actions": [
                "preview transcript",
                "request explicit approval before execution",
            ],
        },
        "approved": False,
        "dispatched": False,
    }


class _FakeTranscriptionResult:
    text = "open notes"
    language = "en"
    confidence = 0.91
    duration_seconds = 1.25
    backend = "faster-whisper"
    segments: list[Any] = []

    def to_dict(self):
        return {
            "text": self.text,
            "language": self.language,
            "confidence": self.confidence,
            "duration_seconds": self.duration_seconds,
            "backend": self.backend,
            "segments": self.segments,
        }


def test_voice_command_help_lists_subcommands() -> None:
    result = CliRunner().invoke(voice_cmd.voice, ["--help"])

    assert result.exit_code == 0
    assert "submit" in result.output
    assert "transcribe-file" in result.output
    assert "speak" in result.output
    assert "record-local" in result.output
    assert "capture-preview" in result.output
    assert "run-local" in result.output
    assert "cancel" in result.output


def test_voice_submit_previews_without_dispatch(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        calls.append((endpoint, payload))
        return _preview_response()

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(voice_cmd.voice, ["submit", "open", "notes"])

    assert result.exit_code == 0
    assert calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        )
    ]
    assert "Voice transcript preview" in result.output
    assert "dispatch: skipped" in result.output


def test_voice_submit_dispatches_only_with_approval_flag(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        calls.append((endpoint, payload))
        if endpoint.endswith("/submit-transcript"):
            return _preview_response()
        return {
            "dispatched": True,
            "status": "completed",
            "fsm_state": "idle",
            "agent_id": "agent-1",
        }

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "submit",
            "open",
            "notes",
            "--agent-id",
            "agent-1",
            "--approve-dispatch",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        ),
        (
            "/v1/voice/ptt/dispatch",
            {"transcript": "open notes", "agent_id": "agent-1", "approved": True},
        ),
    ]
    assert "Voice dispatch result" in result.output
    assert "dispatched: True" in result.output


def test_voice_cancel_calls_cancel_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        calls.append((endpoint, payload))
        return {"fsm_state": "idle"}

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(voice_cmd.voice, ["cancel"])

    assert result.exit_code == 0
    assert calls == [("/v1/voice/ptt/cancel", {})]
    assert "idle" in result.output


def test_voice_transcribe_file_prints_transcript_without_dispatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"fake wav")
    post_calls: list[tuple[str, dict[str, Any] | None]] = []
    adapter_calls: list[tuple[Path, str | None]] = []

    class FakeResult:
        text = "open notes"
        language = "en"
        confidence = 0.91
        duration_seconds = 1.25
        backend = "faster-whisper"
        segments: list[Any] = []

        def to_dict(self):
            return {
                "text": self.text,
                "language": self.language,
                "confidence": self.confidence,
                "duration_seconds": self.duration_seconds,
                "backend": self.backend,
                "segments": self.segments,
            }

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"
            assert config == "config"

        def transcribe_file(self, path, *, language=None):
            adapter_calls.append((path, language))
            return FakeResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return {}

    monkeypatch.setattr(voice_cmd, "load_config", lambda: "config")
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "transcribe-file",
            str(audio_path),
            "--adapter",
            "faster-whisper",
            "--language",
            "en",
        ],
    )

    assert result.exit_code == 0
    assert adapter_calls == [(audio_path, "en")]
    assert post_calls == []
    assert "Voice file transcription" in result.output
    assert "open notes" in result.output
    assert "dispatch: skipped" in result.output


def test_voice_speak_uses_local_adapter_without_dispatch(monkeypatch) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None]] = []
    speak_calls: list[str] = []

    class FakeSpeechOutput:
        def speak(self, text: str) -> None:
            speak_calls.append(text)

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return {}

    def fake_build_speech_output(adapter_id: str, *, voice_name: str, rate: int | None):
        assert adapter_id == "macos-say"
        assert voice_name == "Alex"
        assert rate == 180
        return FakeSpeechOutput()

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_build_speech_output", fake_build_speech_output)

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["speak", "hello", "there", "--voice", "Alex", "--rate", "180"],
    )

    assert result.exit_code == 0
    assert speak_calls == ["hello there"]
    assert post_calls == []
    assert "Voice speech output" in result.output
    assert "dispatch: skipped" in result.output


def test_voice_speak_requires_text() -> None:
    result = CliRunner().invoke(voice_cmd.voice, ["speak", ""])

    assert result.exit_code != 0
    assert "text must not be empty" in result.output


def test_voice_record_local_requires_explicit_duration() -> None:
    result = CliRunner().invoke(voice_cmd.voice, ["record-local"])

    assert result.exit_code != 0
    assert "Missing option '--duration'" in result.output


def test_voice_record_local_writes_dev_file_without_dispatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return {}

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "record-local",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    recorded_path = Path(result.output.strip())
    assert recorded_path.exists()
    assert recorded_path.parent == tmp_path
    with wave.open(str(recorded_path), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000
    assert post_calls == []


def test_voice_capture_preview_requires_explicit_duration() -> None:
    result = CliRunner().invoke(voice_cmd.voice, ["capture-preview"])

    assert result.exit_code != 0
    assert "Missing option '--duration'" in result.output


def test_voice_capture_preview_requires_adapter_before_recording(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorder_calls: list[str] = []

    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: type(
            "Config",
            (),
            {"speech": type("Speech", (), {"backend": "auto"})()},
        )(),
    )
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda *args, **kwargs: recorder_calls.append("record") or None,
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "capture-preview",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "local voice transcription is disabled" in result.output
    assert recorder_calls == []


def test_voice_capture_preview_records_transcribes_and_previews_without_dispatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None]] = []
    adapter_calls: list[tuple[Path, str | None]] = []

    class FakeResult:
        text = "open notes"
        language = "en"
        confidence = 0.91
        duration_seconds = 1.25
        backend = "faster-whisper"
        segments: list[Any] = []

        def to_dict(self):
            return {
                "text": self.text,
                "language": self.language,
                "confidence": self.confidence,
                "duration_seconds": self.duration_seconds,
                "backend": self.backend,
                "segments": self.segments,
            }

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"
            assert config == "config"

        def transcribe_file(self, path, *, language=None):
            adapter_calls.append((path, language))
            return FakeResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return _preview_response()

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "load_config", lambda: "config")
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "capture-preview",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--adapter",
            "faster-whisper",
            "--language",
            "en",
        ],
    )

    assert result.exit_code == 0
    assert len(adapter_calls) == 1
    recorded_path, language = adapter_calls[0]
    assert recorded_path.exists()
    assert recorded_path.parent == tmp_path
    assert language == "en"
    assert post_calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        )
    ]
    assert "/dispatch" not in result.output
    assert "Voice capture preview" in result.output
    assert "stage: recording local WAV" in result.output
    assert "stage: transcribing local WAV" in result.output
    assert "stage: submitting transcript preview" in result.output
    assert "dispatch: skipped" in result.output


def test_voice_transcribe_file_requires_explicit_or_configured_adapter(
    monkeypatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"fake wav")
    post_calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return {}

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: type(
            "Config",
            (),
            {"speech": type("Speech", (), {"backend": "auto"})()},
        )(),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["transcribe-file", str(audio_path)])

    assert result.exit_code != 0
    assert "local voice transcription is disabled" in result.output
    assert post_calls == []


def test_voice_run_local_previews_without_dispatch_or_speech(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None]] = []
    adapter_calls: list[tuple[Path, str | None]] = []
    speech_calls: list[str] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"
            assert config == "config"

        def transcribe_file(self, path, *, language=None):
            adapter_calls.append((path, language))
            return _FakeTranscriptionResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return _preview_response()

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "load_config", lambda: "config")
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")
    monkeypatch.setattr(
        voice_cmd,
        "_build_speech_output",
        lambda *args, **kwargs: speech_calls.append("build"),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "run-local",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--adapter",
            "faster-whisper",
            "--language",
            "en",
        ],
    )

    assert result.exit_code == 0
    assert len(adapter_calls) == 1
    recorded_path, language = adapter_calls[0]
    assert recorded_path.exists()
    assert recorded_path.parent == tmp_path
    assert language == "en"
    assert post_calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        )
    ]
    assert speech_calls == []
    assert "Voice local run" in result.output
    assert "stage: recording local WAV" in result.output
    assert "stage: transcribing local WAV" in result.output
    assert "stage: submitting transcript preview" in result.output
    assert "dispatch: skipped" in result.output
    assert "speech: skipped" in result.output


def test_voice_run_local_dispatches_only_with_approval_flag(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None]] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"

        def transcribe_file(self, path, *, language=None):
            return _FakeTranscriptionResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        if endpoint.endswith("/submit-transcript"):
            return _preview_response()
        return {
            "dispatched": True,
            "status": "completed",
            "fsm_state": "idle",
            "agent_id": "agent-1",
            "content": "done",
        }

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "load_config", lambda: "config")
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "run-local",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--adapter",
            "faster-whisper",
            "--agent-id",
            "agent-1",
            "--approve-dispatch",
        ],
    )

    assert result.exit_code == 0
    assert post_calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        ),
        (
            "/v1/voice/ptt/dispatch",
            {"transcript": "open notes", "agent_id": "agent-1", "approved": True},
        ),
    ]
    assert "stage: dispatching approved transcript" in result.output
    assert "Voice dispatch result" in result.output
    assert "speech: skipped" in result.output


def test_voice_run_local_speak_result_requires_dispatch_approval() -> None:
    result = CliRunner().invoke(
        voice_cmd.voice,
        ["run-local", "--duration", "0.1", "--speak-result"],
    )

    assert result.exit_code != 0
    assert "--speak-result requires --approve-dispatch" in result.output


def test_voice_run_local_speaks_only_with_explicit_flag(
    monkeypatch,
    tmp_path: Path,
) -> None:
    speak_calls: list[str] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"

        def transcribe_file(self, path, *, language=None):
            return _FakeTranscriptionResult()

    class FakeSpeechOutput:
        def speak(self, text: str) -> None:
            speak_calls.append(text)

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        if endpoint.endswith("/submit-transcript"):
            return _preview_response()
        return {
            "dispatched": True,
            "status": "completed",
            "fsm_state": "idle",
            "agent_id": "agent-1",
            "content": "done",
        }

    def fake_build_speech_output(adapter_id: str, *, voice_name: str, rate: int | None):
        assert adapter_id == "macos-say"
        assert voice_name == "Alex"
        assert rate == 180
        return FakeSpeechOutput()

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "load_config", lambda: "config")
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")
    monkeypatch.setattr(voice_cmd, "_build_speech_output", fake_build_speech_output)

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "run-local",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--adapter",
            "faster-whisper",
            "--agent-id",
            "agent-1",
            "--approve-dispatch",
            "--speak-result",
            "--voice",
            "Alex",
            "--rate",
            "180",
        ],
    )

    assert result.exit_code == 0
    assert speak_calls == ["done"]
    assert "speech: spoken" in result.output


def test_voice_run_local_recorder_dependency_failure_is_clear(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"

        def transcribe_file(self, path, *, language=None):
            raise AssertionError("should not transcribe when recording fails")

    class BrokenRecorder:
        def start(self, recording_id: str):
            raise voice_cmd.VoiceRecordingError("install ffmpeg or sox")

        def stop(self, handle) -> None:
            raise AssertionError("should not stop without a handle")

    monkeypatch.setattr(voice_cmd, "load_config", lambda: "config")
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda *args, **kwargs: BrokenRecorder(),
    )
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "run-local",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--adapter",
            "faster-whisper",
        ],
    )

    assert result.exit_code != 0
    assert "install ffmpeg or sox" in result.output
