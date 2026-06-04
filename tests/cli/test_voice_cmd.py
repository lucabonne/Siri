"""Tests for the local typed/mock voice CLI bridge."""

from __future__ import annotations

import importlib.util
import json
import wave
from pathlib import Path
from types import SimpleNamespace
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


def setup_function() -> None:
    voice_cmd._log_voice_event = lambda *args, **kwargs: None


def _safe_config(**voice_overrides: Any) -> SimpleNamespace:
    voice_defaults = {
        "transcription_adapter": "",
        "model_path": "",
        "default_record_duration": 0.0,
        "default_api_base_url": "",
        "speech_output_adapter": "",
        "speech_voice": "",
        "speech_rate": 0,
        "hotkey_bridge_format": "command",
        "hotkey_bridge_jarvis_bin": "jarvis",
        "hotkey_bridge_recorder": "macos",
        "hotkey_bridge_input_device": ":0",
        "hotkey_bridge_session_id": "",
        "voice_logs_enabled": False,
        "voice_logs_path": "",
        "voice_logs_include_full_transcripts": False,
        "voice_logs_preview_chars": 80,
    }
    voice_defaults.update(voice_overrides)
    return SimpleNamespace(
        server=SimpleNamespace(host="0.0.0.0", port=8000),
        speech=SimpleNamespace(
            backend="auto",
            model="base",
            language="",
            device="auto",
            compute_type="float16",
            require_explicit_voice_approval=True,
        ),
        voice_control=SimpleNamespace(**voice_defaults),
    )


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
    assert "doctor" in result.output
    assert "hotkey-bridge" in result.output
    assert "logs" in result.output
    assert "cancel" in result.output


def test_voice_logs_command_outputs_recent_events(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    logger = voice_cmd.VoiceEventLogger(
        voice_cmd.voice_log_settings_from_config(
            _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path))
        )
    )
    logger.record(
        command="submit",
        event="preview_result",
        transcript="email luca@example.com token sk-1234567890abcdef",
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["logs", "--limit", "5"])

    assert result.exit_code == 0
    assert "Voice logs" in result.output
    assert "submit preview_result" in result.output
    assert "transcript_length=" in result.output
    assert "luca@example.com" not in result.output
    assert "sk-1234567890abcdef" not in result.output


def test_voice_doctor_json_reports_available_configured_setup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "fw-model"
    model_path.mkdir()

    def fail_api(*args, **kwargs):
        raise AssertionError("voice doctor must not call the API")

    monkeypatch.setattr(voice_cmd, "_post_json", fail_api)
    monkeypatch.setattr(voice_cmd, "_get_json", fail_api)
    monkeypatch.setattr(voice_cmd.sys, "platform", "darwin")
    monkeypatch.setattr(voice_cmd.shutil, "which", lambda name: "/usr/bin/say")
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            transcription_adapter="faster-whisper",
            model_path=str(model_path),
            default_record_duration=2.5,
            default_api_base_url="http://configured:9000/",
            speech_output_adapter="macos-say",
            hotkey_bridge_format="json",
        ),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["doctor", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["api_base_url"] == {
        "value": "http://configured:9000",
        "source": "[voice_control].default_api_base_url",
    }
    assert data["transcription_adapter"]["effective"] == "faster-whisper"
    assert data["transcription_adapter"]["supported"] is True
    assert data["model_path"]["value"] == str(model_path)
    assert data["model_path"]["required"] is True
    assert data["model_path"]["exists"] is True
    assert data["record_duration"]["effective_default_seconds"] == 2.5
    assert data["record_duration"]["duration_flag_required"] is False
    assert data["speech_output"]["effective"] == "macos-say"
    assert data["macos_say"]["available"] is True
    assert data["hotkey_bridge"]["print_only"] is True
    assert data["hotkey_bridge"]["enabled"] is False
    assert data["approval"]["required"] is True
    assert data["safety"] == {
        "microphone_access_required": False,
        "model_download_required": False,
        "dispatch_called": False,
        "speech_called": False,
        "hotkeys_started": False,
        "approval_bypassed": False,
    }


def test_voice_doctor_reports_missing_dependencies_without_side_effects(
    monkeypatch,
) -> None:
    def fail_api(*args, **kwargs):
        raise AssertionError("voice doctor must not call the API")

    monkeypatch.delenv("WHISPER_CPP_MODEL", raising=False)
    monkeypatch.setattr(voice_cmd, "_post_json", fail_api)
    monkeypatch.setattr(voice_cmd, "_get_json", fail_api)
    monkeypatch.setattr(voice_cmd.sys, "platform", "linux")
    monkeypatch.setattr(voice_cmd.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(transcription_adapter="whisper.cpp"),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["doctor"])

    assert result.exit_code == 0
    assert "Voice doctor" in result.output
    assert "api_base_url: http://127.0.0.1:8000" in result.output
    assert "transcription_adapter: whisper.cpp" in result.output
    assert "model_path: -" in result.output
    assert "required=True, exists=False" in result.output
    assert "record_duration: requires --duration" in result.output
    assert "macos_say_available: False" in result.output
    assert "hotkey_bridge: print_only=True, enabled=False" in result.output
    assert "approval_required: True" in result.output
    assert "no microphone, downloads, dispatch, speech, or hotkeys started" in (
        result.output
    )


def test_voice_hotkey_bridge_prints_disabled_run_local_command(monkeypatch) -> None:
    def fake_post(*args, **kwargs):
        raise AssertionError("hotkey bridge must not call the API")

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "hotkey-bridge",
            "--duration",
            "1.5",
            "--adapter",
            "faster-whisper",
        ],
    )

    assert result.exit_code == 0
    assert "macOS hotkey bridge (disabled)" in result.output
    command_line = next(
        line
        for line in result.output.splitlines()
        if line.strip().startswith("command:")
    )
    assert "jarvis voice run-local --duration 1.5" in command_line
    assert "--recorder macos" in command_line
    assert "--adapter faster-whisper" in command_line
    assert "--approve-dispatch" not in command_line
    assert "--speak-result" not in command_line
    assert "no global key capture is started" in result.output
    assert "dispatch: skipped" in result.output
    assert "speech: skipped" in result.output


def test_voice_hotkey_bridge_json_reports_safe_defaults(monkeypatch) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(voice_cmd.voice, ["hotkey-bridge", "--format", "json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["enabled"] is False
    assert data["listener_started"] is False
    assert data["global_key_capture"] is False
    assert data["dispatch_enabled"] is False
    assert data["speech_enabled"] is False
    assert "/v1/voice/ptt/dispatch" not in data["command"]
    assert "--approve-dispatch" not in data["argv"]
    assert "--speak-result" not in data["argv"]


def test_voice_hotkey_bridge_hammerspoon_snippet_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--format", "hammerspoon", "--adapter", "faster-whisper"],
    )

    assert result.exit_code == 0
    assert "local enable_openjarvis_voice_hotkey = false" in result.output
    assert "hs.hotkey.bind" in result.output
    assert "jarvis voice run-local" in result.output
    assert "--adapter faster-whisper" in result.output
    assert "--approve-dispatch" not in result.output


def test_voice_hotkey_bridge_uses_configured_preview_defaults(monkeypatch) -> None:
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            transcription_adapter="whisper.cpp",
            default_record_duration=1.25,
            default_api_base_url="http://configured:9000",
            hotkey_bridge_format="json",
            hotkey_bridge_jarvis_bin="/opt/bin/jarvis",
            hotkey_bridge_recorder="dev-silent",
            hotkey_bridge_input_device=":2",
            hotkey_bridge_session_id="voice-session",
        ),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["hotkey-bridge"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["enabled"] is False
    assert data["listener_started"] is False
    assert data["dispatch_enabled"] is False
    assert data["speech_enabled"] is False
    assert data["argv"] == [
        "/opt/bin/jarvis",
        "voice",
        "run-local",
        "--duration",
        "1.25",
        "--recorder",
        "dev-silent",
        "--input-device",
        ":2",
        "--adapter",
        "whisper.cpp",
        "--base-url",
        "http://configured:9000",
        "--session-id",
        "voice-session",
    ]
    assert "--approve-dispatch" not in data["argv"]
    assert "--speak-result" not in data["argv"]


def test_voice_hotkey_bridge_cli_flags_override_config(monkeypatch) -> None:
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            transcription_adapter="whisper.cpp",
            default_record_duration=9.0,
            default_api_base_url="http://configured:9000",
            hotkey_bridge_format="json",
            hotkey_bridge_jarvis_bin="/opt/bin/jarvis",
            hotkey_bridge_recorder="dev-silent",
        ),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "hotkey-bridge",
            "--format",
            "json",
            "--duration",
            "1.5",
            "--adapter",
            "faster-whisper",
            "--base-url",
            "http://cli:8000",
            "--jarvis-bin",
            "jarvis-cli",
            "--recorder",
            "macos",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["argv"][:9] == [
        "jarvis-cli",
        "voice",
        "run-local",
        "--duration",
        "1.5",
        "--recorder",
        "macos",
        "--input-device",
        ":0",
    ]
    assert "--adapter" in data["argv"]
    assert "faster-whisper" in data["argv"]
    assert "http://cli:8000" in data["argv"]


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
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "speak",
            "hello",
            "there",
            "--adapter",
            "macos-say",
            "--voice",
            "Alex",
            "--rate",
            "180",
        ],
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


def test_voice_speak_uses_configured_adapter_only_when_invoked(monkeypatch) -> None:
    speak_calls: list[tuple[str, str, int | None, str]] = []

    class FakeSpeechOutput:
        def speak(self, text: str) -> None:
            speak_calls.append(("speak", "Alex", 180, text))

    def fake_build_speech_output(adapter_id: str, *, voice_name: str, rate: int | None):
        assert adapter_id == "macos-say"
        assert voice_name == "Alex"
        assert rate == 180
        return FakeSpeechOutput()

    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            speech_output_adapter="macos-say",
            speech_voice="Alex",
            speech_rate=180,
        ),
    )
    monkeypatch.setattr(voice_cmd, "_build_speech_output", fake_build_speech_output)

    result = CliRunner().invoke(voice_cmd.voice, ["speak", "hello"])

    assert result.exit_code == 0
    assert speak_calls == [("speak", "Alex", 180, "hello")]
    assert "dispatch: skipped" in result.output


def test_voice_record_local_requires_explicit_duration(monkeypatch) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(voice_cmd.voice, ["record-local"])

    assert result.exit_code != 0
    assert "Missing option '--duration'" in result.output


def test_voice_record_local_uses_configured_duration(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(default_record_duration=0.1),
    )
    monkeypatch.setattr(
        voice_cmd, "_sleep", lambda seconds: sleep_calls.append(seconds)
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["record-local", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    recorded_path = Path(result.output.strip())
    assert recorded_path.exists()
    assert sleep_calls == [0.1]


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
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

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


def test_voice_capture_preview_requires_explicit_duration(monkeypatch) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

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


def test_voice_run_local_uses_configured_safe_defaults(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None, str]] = []
    adapter_calls: list[tuple[str, Path, str | None]] = []
    sleep_calls: list[float] = []
    speech_calls: list[str] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"
            assert config.speech.model == "base"
            self.adapter_id = adapter_id

        def transcribe_file(self, path, *, language=None):
            adapter_calls.append((self.adapter_id, path, language))
            return _FakeTranscriptionResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload, kwargs["base_url"]))
        return _preview_response()

    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            transcription_adapter="faster-whisper",
            default_record_duration=0.1,
            default_api_base_url="http://configured:9000",
        ),
    )
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        voice_cmd, "_sleep", lambda seconds: sleep_calls.append(seconds)
    )
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(
        voice_cmd,
        "_build_speech_output",
        lambda *args, **kwargs: speech_calls.append("build"),
    )
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["run-local", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert sleep_calls == [0.1]
    assert len(adapter_calls) == 1
    adapter_id, recorded_path, language = adapter_calls[0]
    assert adapter_id == "faster-whisper"
    assert recorded_path.exists()
    assert language is None
    assert post_calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
            "http://configured:9000",
        )
    ]
    assert speech_calls == []
    assert "dispatch: skipped" in result.output
    assert "speech: skipped" in result.output


def test_voice_run_local_cli_flags_override_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, str]] = []
    adapter_ids: list[str] = []
    sleep_calls: list[float] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            adapter_ids.append(adapter_id)

        def transcribe_file(self, path, *, language=None):
            return _FakeTranscriptionResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, kwargs["base_url"]))
        return _preview_response()

    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            transcription_adapter="whisper.cpp",
            default_record_duration=9.0,
            default_api_base_url="http://configured:9000",
        ),
    )
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        voice_cmd, "_sleep", lambda seconds: sleep_calls.append(seconds)
    )
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
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
            "--base-url",
            "http://cli:8000",
        ],
    )

    assert result.exit_code == 0
    assert adapter_ids == ["faster-whisper"]
    assert sleep_calls == [0.1]
    assert post_calls == [("/v1/voice/ptt/submit-transcript", "http://cli:8000")]


def test_voice_configured_missing_model_path_fails_clearly(
    monkeypatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "clip.wav"
    audio_path.write_bytes(b"fake wav")
    missing_model = tmp_path / "missing-model"

    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            transcription_adapter="faster-whisper",
            model_path=str(missing_model),
        ),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["transcribe-file", str(audio_path)])

    assert result.exit_code != 0
    assert f"faster-whisper model path does not exist: {missing_model}" in result.output


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
