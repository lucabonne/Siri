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
        "default_recorder": "dev-silent",
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
    assert "mic-smoke" in result.output
    assert "mic-transcribe-smoke" in result.output
    assert "mic-preview" in result.output
    assert "mic-run" in result.output
    assert "capture-preview" in result.output
    assert "run-local" in result.output
    assert "doctor" in result.output
    assert "hotkey-bridge" in result.output
    assert "logs" in result.output
    assert "cancel" in result.output


def test_voice_microphone_command_help_separates_pipeline_stages() -> None:
    expected_descriptions = [
        ("record-local", "Record only to a local WAV"),
        ("mic-smoke", "Record only from a real mic"),
        ("mic-transcribe-smoke", "Record from a real mic and transcribe locally"),
        ("mic-preview", "Record and transcribe from a real mic"),
        ("mic-run", "approved dispatch is opt-in"),
        ("run-local", "approved dispatch is opt-in"),
    ]

    for command, description in expected_descriptions:
        result = CliRunner().invoke(voice_cmd.voice, [command, "--help"])

        assert result.exit_code == 0
        assert description in result.output


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


def test_voice_logs_json_filters_without_exposing_redacted_text(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    logger = voice_cmd.VoiceEventLogger(
        voice_cmd.voice_log_settings_from_config(
            _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path))
        )
    )
    logger.record(
        command="submit",
        event="preview_result",
        transcript="email luca@example.com",
        details={"approval_required": True, "approved": False},
    )
    logger.record(
        command="submit",
        event="dispatch_decision",
        status="skipped",
        transcript="token sk-1234567890abcdef",
        details={"approved": False, "attempted": False},
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "logs",
            "--approval-dispatch-only",
            "--status",
            "skipped",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["filters"]["approval_dispatch_only"] is True
    assert data["filters"]["statuses"] == ["skipped"]
    assert [event["event"] for event in data["events"]] == ["dispatch_decision"]
    transcript = data["events"][0]["transcript"]
    assert transcript["preview"] == "token [secret]"
    assert "text" not in transcript
    assert "sk-1234567890abcdef" not in result.output
    assert "luca@example.com" not in result.output


def test_voice_logs_empty_log_outputs_empty_json(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice, ["logs", "--event", "missing", "--json"]
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["enabled"] is True
    assert data["events"] == []
    assert data["filters"]["event_types"] == ["missing"]


def test_voice_logs_export_jsonl_preserves_filters(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    export_path = tmp_path / "filtered.jsonl"
    logger = voice_cmd.VoiceEventLogger(
        voice_cmd.voice_log_settings_from_config(
            _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path))
        )
    )
    logger.record(command="status", event="status_result")
    logger.record(
        command="run-local",
        event="dispatch_result",
        details={"dispatch_status": "ok"},
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "logs",
            "--approval-dispatch-only",
            "--export",
            str(export_path),
        ],
    )

    assert result.exit_code == 0
    assert "export: wrote 1 event(s)" in result.output
    exported_lines = export_path.read_text(encoding="utf-8").splitlines()
    exported = [json.loads(line) for line in exported_lines]
    assert [event["event"] for event in exported] == ["dispatch_result"]


def test_voice_logs_export_json_output(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    export_path = tmp_path / "filtered.json"
    logger = voice_cmd.VoiceEventLogger(
        voice_cmd.voice_log_settings_from_config(
            _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path))
        )
    )
    logger.record(command="status", event="status_result")
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["logs", "--export", str(export_path), "--export-format", "json"],
    )

    assert result.exit_code == 0
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert isinstance(exported, list)
    assert len(exported) == 1
    assert exported[0]["command"] == "status"
    assert exported[0]["event"] == "status_result"
    assert exported[0]["status"] == "ok"
    assert "timestamp" in exported[0]


def test_voice_logs_export_preserves_redaction(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    export_path = tmp_path / "redacted.jsonl"
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

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["logs", "--export", str(export_path)],
    )

    assert result.exit_code == 0
    exported_text = export_path.read_text(encoding="utf-8")
    exported = json.loads(exported_text)
    assert exported["transcript"]["preview"] == "email [email] token [secret]"
    assert "text" not in exported["transcript"]
    assert "luca@example.com" not in exported_text
    assert "sk-1234567890abcdef" not in exported_text


def test_voice_logs_export_empty_log(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    export_path = tmp_path / "empty.json"
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["logs", "--event", "missing", "--export", str(export_path)],
    )

    assert result.exit_code == 0
    assert json.loads(export_path.read_text(encoding="utf-8")) == []


def test_voice_logs_export_rejects_missing_parent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    missing_parent_export = tmp_path / "missing" / "export.jsonl"
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["logs", "--export", str(missing_parent_export)],
    )

    assert result.exit_code != 0
    assert "Export parent directory does not exist" in result.output
    assert not missing_parent_export.exists()


def test_voice_logs_clear_dry_run_does_not_modify_log(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    log_path.write_text(
        json.dumps({"command": "status", "event": "status_result"}) + "\n",
        encoding="utf-8",
    )
    original = log_path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["logs", "--clear", "--dry-run"])

    assert result.exit_code == 0
    assert "Voice log cleanup" in result.output
    assert "dry_run: True" in result.output
    assert "matched_for_delete: 1" in result.output
    assert log_path.read_text(encoding="utf-8") == original


def test_voice_logs_clear_refuses_without_confirmation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    log_path.write_text(
        json.dumps({"command": "status", "event": "status_result"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["logs", "--clear"])

    assert result.exit_code == 1
    assert "refused: pass --confirm" in result.output
    assert "status_result" in log_path.read_text(encoding="utf-8")


def test_voice_logs_confirmed_clear_truncates_log(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    log_path.write_text(
        json.dumps({"command": "status", "event": "status_result"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["logs", "--clear", "--confirm"])

    assert result.exit_code == 0
    assert "matched_for_delete: 1" in result.output
    assert "changed: true" in result.output
    assert log_path.read_text(encoding="utf-8") == ""


def test_voice_logs_clear_before_retains_events_on_or_after_date(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    records = [
        {"timestamp": "2025-12-31T23:59:59Z", "event": "old"},
        {"timestamp": "2026-01-01T00:00:00Z", "event": "kept"},
        {"event": "undated"},
    ]
    log_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["logs", "--clear-before", "2026-01-01", "--confirm"],
    )

    remaining = log_path.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "clear_before: 2026-01-01" in result.output
    assert "matched_for_delete: 1" in result.output
    assert '"event": "old"' not in remaining
    assert '"event": "kept"' in remaining
    assert '"event": "undated"' in remaining


def test_voice_logs_clear_empty_log_outputs_zero_changes_json(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "missing.jsonl"
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["logs", "--clear", "--confirm", "--json"],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["cleanup"]["exists"] is False
    assert data["cleanup"]["deleted_count"] == 0
    assert data["cleanup"]["changed"] is False
    assert not log_path.exists()


def test_voice_logs_clear_before_dry_run_json(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    log_path.write_text(
        json.dumps({"timestamp": "2025-12-31T23:59:59Z", "event": "old"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(voice_logs_enabled=True, voice_logs_path=str(log_path)),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["logs", "--clear-before", "2026-01-01", "--dry-run", "--json"],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["cleanup"]["mode"] == "clear-before"
    assert data["cleanup"]["dry_run"] is True
    assert data["cleanup"]["confirmed"] is False
    assert data["cleanup"]["refused"] is False
    assert data["cleanup"]["deleted_count"] == 1
    assert "old" in log_path.read_text(encoding="utf-8")


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
    assert data["recorder"]["configured_default"] == "dev-silent"
    assert data["recorder"]["supported"] is True
    assert data["recorder"]["backend_available"] is True
    assert data["recorder"]["microphone_recording_configured"] is False
    assert data["recorder"]["microphone_configuration_ready"] is False
    assert isinstance(data["recorder"]["sounddevice_importable"], bool)
    assert data["recorder"]["microphone_permission_checked"] is False
    assert data["recorder"]["status_check"] == "configuration_only"
    assert data["recorder"]["requires_explicit_command"] is True
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
    assert "microphone_duration_bounds: 0.1-30 seconds" in result.output
    assert "temporary_wav_cleanup: deleted by default" in result.output
    assert "sounddevice_importable:" in result.output
    assert "microphone_recording_configured: False" in result.output
    assert "permission not checked" in result.output
    assert "System Settings > Privacy & Security > Microphone" in result.output
    assert "macos_say_available: False" in result.output
    assert "hotkey_bridge: print_only=True, enabled=False" in result.output
    assert "approval_required: True" in result.output
    assert "no microphone, downloads, dispatch, speech, or hotkeys started" in (
        result.output
    )


def test_voice_hotkey_bridge_prints_disabled_mic_run_command(monkeypatch) -> None:
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
    assert "jarvis voice mic-run --duration 1.5" in command_line
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
    assert "jarvis voice mic-run" in result.output
    assert "--adapter faster-whisper" in result.output
    active_command = next(
        line
        for line in result.output.splitlines()
        if line.startswith("local openjarvis_voice_command =")
    )
    assert "--approve-dispatch" not in active_command
    assert "--speak-result" not in active_command
    assert "-- local openjarvis_voice_command" in result.output


def test_voice_hotkey_bridge_writes_disabled_hammerspoon_example(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
    output_path = tmp_path / "openjarvis-voice.lua"

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "hotkey-bridge",
            "--adapter",
            "faster-whisper",
            "--write-hammerspoon",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "local enable_openjarvis_voice_hotkey = false" in content
    assert "local openjarvis_voice_command =" in content
    active_command = next(
        line
        for line in content.splitlines()
        if line.startswith("local openjarvis_voice_command =")
    )
    assert "jarvis voice mic-run" in active_command
    assert "--approve-dispatch" not in active_command
    assert "--speak-result" not in active_command
    assert "-- local openjarvis_voice_command" in content
    assert "Wrote disabled Hammerspoon bridge example" in result.output


def _write_hammerspoon_validation_fixture(
    path: Path,
    *,
    extra_active_flags: str = "",
    include_duration: bool = True,
) -> None:
    duration = " --duration 2" if include_duration else ""
    path.write_text(
        "-- Generated OpenJarvis bridge example.\n"
        "local enable_openjarvis_voice_hotkey = false\n"
        "local openjarvis_voice_command = "
        f"'jarvis voice mic-run{duration} --recorder macos --input-device :0"
        f"{extra_active_flags}'\n"
        "-- local openjarvis_voice_command = "
        "'jarvis voice mic-run --duration 2 --recorder macos "
        "--approve-dispatch --speak-result'\n"
        "if enable_openjarvis_voice_hotkey then\n"
        "  hs.hotkey.bind({}, 'F18', function() end)\n"
        "end\n",
        encoding="utf-8",
    )


def test_voice_hotkey_bridge_validates_safe_generated_file(tmp_path) -> None:
    bridge_path = tmp_path / "openjarvis-voice.lua"
    _write_hammerspoon_validation_fixture(bridge_path)

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--validate-hammerspoon", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert "Hammerspoon bridge validation passed" in result.output


def test_voice_hotkey_bridge_install_preview_prints_manual_steps(
    monkeypatch, tmp_path
) -> None:
    bridge_path = tmp_path / "openjarvis-voice.lua"
    _write_hammerspoon_validation_fixture(bridge_path)
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: (_ for _ in ()).throw(AssertionError("config must not load")),
    )
    monkeypatch.setattr(
        voice_cmd,
        "_log_voice_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("install preview must not write voice logs")
        ),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--install-preview", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert "Hammerspoon bridge install preview (no changes made)" in result.output
    assert f"bridge: {bridge_path.resolve(strict=True)}" in result.output
    assert "validation: passed" in result.output
    assert "disabled/preview-only by default" in result.output
    assert "dofile(" in result.output
    assert str(bridge_path.resolve(strict=True)) in result.output
    assert "approved dispatch: manual opt-in only" in result.output
    assert "result speech: manual opt-in only" in result.output
    assert "listener startup: not started" in result.output
    assert "global hotkey capture: not enabled" in result.output
    assert "~/.hammerspoon/init.lua: not modified" in result.output
    assert "files copied: none" in result.output
    assert "Hammerspoon install: not attempted" in result.output
    assert "Accessibility permission: not requested" in result.output
    assert "--approve-dispatch` command variant" in result.output
    assert "--approve-dispatch --speak-result` command variant" in result.output


def test_voice_hotkey_bridge_install_preview_validation_failure_has_no_steps(
    tmp_path,
) -> None:
    bridge_path = tmp_path / "unsafe-dispatch.lua"
    _write_hammerspoon_validation_fixture(
        bridge_path, extra_active_flags=" --approve-dispatch"
    )
    original_content = bridge_path.read_text(encoding="utf-8")

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--install-preview", str(bridge_path)],
    )

    assert result.exit_code != 0
    assert "Hammerspoon bridge validation failed" in result.output
    assert "active content contains unsafe --approve-dispatch" in result.output
    assert "Manual install steps" not in result.output
    assert bridge_path.read_text(encoding="utf-8") == original_content


def test_voice_hotkey_bridge_install_preview_does_not_mutate_files(
    monkeypatch, tmp_path
) -> None:
    home = tmp_path / "home"
    active_init = home / ".hammerspoon" / "init.lua"
    active_init.parent.mkdir(parents=True)
    active_init.write_text("-- user hammerspoon config\n", encoding="utf-8")
    bridge_path = tmp_path / "openjarvis-voice.lua"
    _write_hammerspoon_validation_fixture(bridge_path)
    original_bridge = bridge_path.read_text(encoding="utf-8")
    original_init = active_init.read_text(encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--install-preview", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert bridge_path.read_text(encoding="utf-8") == original_bridge
    assert active_init.read_text(encoding="utf-8") == original_init


def test_voice_hotkey_bridge_install_preview_refuses_active_init(
    monkeypatch, tmp_path
) -> None:
    home = tmp_path / "home"
    active_init = home / ".hammerspoon" / "init.lua"
    active_init.parent.mkdir(parents=True)
    _write_hammerspoon_validation_fixture(active_init)
    original_content = active_init.read_text(encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--install-preview", str(active_init)],
    )

    assert result.exit_code != 0
    assert "Refusing to validate the active ~/.hammerspoon/init.lua" in result.output
    assert "Manual install steps" not in result.output
    assert active_init.read_text(encoding="utf-8") == original_content


def test_voice_hotkey_bridge_install_preview_starts_no_listener_or_voice_flow(
    monkeypatch, tmp_path
) -> None:
    bridge_path = tmp_path / "openjarvis-voice.lua"
    _write_hammerspoon_validation_fixture(bridge_path)

    def fail_side_effect(*args, **kwargs):
        raise AssertionError("install preview must not start voice flow")

    monkeypatch.setattr(voice_cmd, "_post_json", fail_side_effect)
    monkeypatch.setattr(voice_cmd, "_get_json", fail_side_effect)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fail_side_effect)
    monkeypatch.setattr(voice_cmd, "_build_speech_output", fail_side_effect)

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--install-preview", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert "listener startup: not started" in result.output
    assert "global hotkey capture: not enabled" in result.output
    assert "active command: preview-only `jarvis voice mic-run`" in result.output


def test_voice_hotkey_bridge_status_reports_valid_file(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bridge_path = tmp_path / "openjarvis-voice.lua"
    _write_hammerspoon_validation_fixture(bridge_path)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(voice_cmd.sys, "platform", "linux")
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: (_ for _ in ()).throw(AssertionError("config must not load")),
    )
    monkeypatch.setattr(
        voice_cmd,
        "_log_voice_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("status must not write voice logs")
        ),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--status", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert "Hammerspoon bridge status (read-only)" in result.output
    assert "file exists: True" in result.output
    assert "validation: passed (Phase 6 static validator)" in result.output
    assert "preview-only default detected: True" in result.output
    assert "readiness: ready_for_manual_review" in result.output
    assert "activation deferred: True" in result.output
    assert "global hotkey enabled: False" in result.output
    assert "active init reference detected: False" in result.output
    assert "manual install reference present: False" in result.output
    assert "Hammerspoon app detected: not checked (not macOS)" in result.output
    assert "no listener was started: True" in result.output
    assert "no files were modified: True" in result.output
    assert "Lua execution: not attempted" in result.output
    assert "shell commands from bridge: not run" in result.output
    assert "Accessibility permission: not requested" in result.output
    assert "dispatch started: False" in result.output
    assert "speech started: False" in result.output


def test_voice_hotkey_bridge_status_reports_invalid_file(tmp_path) -> None:
    bridge_path = tmp_path / "unsafe-dispatch.lua"
    _write_hammerspoon_validation_fixture(
        bridge_path, extra_active_flags=" --approve-dispatch"
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--status", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert "file exists: True" in result.output
    assert "validation: failed (Phase 6 static validator)" in result.output
    assert "active content contains unsafe --approve-dispatch" in result.output
    assert "preview-only default detected: False" in result.output
    assert "readiness: not_ready" in result.output
    assert "no listener was started: True" in result.output
    assert "no files were modified: True" in result.output


def test_voice_hotkey_bridge_status_reports_missing_file(tmp_path) -> None:
    bridge_path = tmp_path / "missing.lua"

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--status", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert "file exists: False" in result.output
    assert "validation: failed (Phase 6 static validator)" in result.output
    assert "bridge file does not exist" in result.output
    assert "preview-only default detected: False" in result.output
    assert "readiness: not_ready" in result.output


def test_voice_hotkey_bridge_status_detects_active_init_reference(
    monkeypatch, tmp_path
) -> None:
    home = tmp_path / "home"
    active_init = home / ".hammerspoon" / "init.lua"
    active_init.parent.mkdir(parents=True)
    bridge_path = tmp_path / "openjarvis-voice.lua"
    _write_hammerspoon_validation_fixture(bridge_path)
    active_init.write_text(
        f"dofile({json.dumps(str(bridge_path.resolve(strict=True)))})\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--status", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert f"active init: {active_init}" in result.output
    assert "active init reference detected: True" in result.output
    assert "manual install reference present: True" in result.output
    assert "no listener was started: True" in result.output


def test_voice_hotkey_bridge_status_does_not_mutate_files(
    monkeypatch, tmp_path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bridge_path = tmp_path / "openjarvis-voice.lua"
    _write_hammerspoon_validation_fixture(bridge_path)
    original_bridge = bridge_path.read_text(encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    def fail_side_effect(*args, **kwargs):
        raise AssertionError("status must not start voice flow")

    monkeypatch.setattr(voice_cmd, "_post_json", fail_side_effect)
    monkeypatch.setattr(voice_cmd, "_get_json", fail_side_effect)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fail_side_effect)
    monkeypatch.setattr(voice_cmd, "_build_speech_output", fail_side_effect)

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--status", str(bridge_path)],
    )

    assert result.exit_code == 0
    assert bridge_path.read_text(encoding="utf-8") == original_bridge
    assert not (home / ".hammerspoon").exists()
    assert not (home / "Applications" / "Hammerspoon.app").exists()
    assert "no files were modified: True" in result.output


def test_voice_hotkey_bridge_validation_rejects_active_dispatch(tmp_path) -> None:
    bridge_path = tmp_path / "unsafe-dispatch.lua"
    _write_hammerspoon_validation_fixture(
        bridge_path, extra_active_flags=" --approve-dispatch"
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--validate-hammerspoon", str(bridge_path)],
    )

    assert result.exit_code != 0
    assert "active content contains unsafe --approve-dispatch" in result.output


def test_voice_hotkey_bridge_validation_rejects_active_speech(tmp_path) -> None:
    bridge_path = tmp_path / "unsafe-speech.lua"
    _write_hammerspoon_validation_fixture(
        bridge_path, extra_active_flags=" --speak-result"
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--validate-hammerspoon", str(bridge_path)],
    )

    assert result.exit_code != 0
    assert "active content contains unsafe --speak-result" in result.output


def test_voice_hotkey_bridge_validation_rejects_missing_duration(tmp_path) -> None:
    bridge_path = tmp_path / "missing-duration.lua"
    _write_hammerspoon_validation_fixture(bridge_path, include_duration=False)

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--validate-hammerspoon", str(bridge_path)],
    )

    assert result.exit_code != 0
    assert "requires exactly one duration" in result.output


def test_voice_hotkey_bridge_validation_refuses_active_init(
    monkeypatch, tmp_path
) -> None:
    home = tmp_path / "home"
    active_init = home / ".hammerspoon" / "init.lua"
    active_init.parent.mkdir(parents=True)
    _write_hammerspoon_validation_fixture(active_init)
    original_content = active_init.read_text(encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--validate-hammerspoon", str(active_init)],
    )

    assert result.exit_code != 0
    assert "Refusing to validate the active ~/.hammerspoon/init.lua" in result.output
    assert active_init.read_text(encoding="utf-8") == original_content


def test_voice_hotkey_bridge_validation_rejects_format_option(tmp_path) -> None:
    bridge_path = tmp_path / "openjarvis-voice.lua"
    _write_hammerspoon_validation_fixture(bridge_path)

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "hotkey-bridge",
            "--validate-hammerspoon",
            str(bridge_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert "--validate-hammerspoon cannot be combined with --format" in result.output


def test_voice_hotkey_bridge_write_requires_existing_parent(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
    output_path = tmp_path / "missing" / "openjarvis-voice.lua"

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--write-hammerspoon", str(output_path)],
    )

    assert result.exit_code != 0
    assert "parent directory does not exist" in result.output
    assert not output_path.parent.exists()


def test_voice_hotkey_bridge_write_refuses_existing_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
    output_path = tmp_path / "openjarvis-voice.lua"
    output_path.write_text("user content\n", encoding="utf-8")

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--write-hammerspoon", str(output_path)],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert output_path.read_text(encoding="utf-8") == "user content\n"


def test_voice_hotkey_bridge_write_does_not_install_or_modify_active_init(
    monkeypatch, tmp_path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
    output_path = tmp_path / "openjarvis-voice.lua"

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["hotkey-bridge", "--write-hammerspoon", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert not (home / ".hammerspoon").exists()

    active_result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "hotkey-bridge",
            "--write-hammerspoon",
            str(home / ".hammerspoon" / "init.lua"),
        ],
    )
    assert active_result.exit_code != 0
    assert "Refusing to modify the active ~/.hammerspoon/init.lua" in (
        active_result.output
    )
    assert not (home / ".hammerspoon").exists()


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
            hotkey_bridge_recorder="sounddevice",
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
        "mic-run",
        "--duration",
        "1.25",
        "--recorder",
        "sounddevice",
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
            hotkey_bridge_recorder="sounddevice",
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
        "mic-run",
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


def test_voice_hotkey_bridge_rejects_non_microphone_config(monkeypatch) -> None:
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(hotkey_bridge_recorder="dev-silent"),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["hotkey-bridge"])

    assert result.exit_code != 0
    assert "requires a real microphone recorder" in result.output


def test_voice_hotkey_bridge_rejects_unbounded_configured_duration(monkeypatch) -> None:
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(default_record_duration=31.0),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["hotkey-bridge"])

    assert result.exit_code != 0
    assert "duration must be between 0.1 and 30 seconds" in result.output


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


def test_voice_record_local_accepts_explicit_sounddevice_recorder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorder_kinds: list[str] = []
    post_calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_build_recorder(recorder_kind: str, *, output_dir: Path | None, **kwargs):
        recorder_kinds.append(recorder_kind)
        return voice_cmd.SilentWavRecorder(temp_dir=output_dir)

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return {}

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "record-local",
            "--duration",
            "0.1",
            "--recorder",
            "sounddevice",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert recorder_kinds == ["sounddevice"]
    assert Path(result.output.strip()).exists()
    assert post_calls == []


def test_voice_record_local_uses_configured_sounddevice_recorder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorder_kinds: list[str] = []

    def fake_build_recorder(recorder_kind: str, *, output_dir: Path | None, **kwargs):
        recorder_kinds.append(recorder_kind)
        return voice_cmd.SilentWavRecorder(temp_dir=output_dir)

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            default_record_duration=0.1, default_recorder="sounddevice"
        ),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["record-local", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert recorder_kinds == ["sounddevice"]


def test_voice_record_local_rejects_unsupported_configured_recorder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(default_record_duration=0.1, default_recorder="always-on"),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["record-local", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "[voice_control].default_recorder" in result.output


def test_voice_record_local_bounds_real_microphone_duration_before_recording(
    monkeypatch,
) -> None:
    recorder_calls: list[str] = []
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda *args, **kwargs: recorder_calls.append("record"),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["record-local", "--recorder", "sounddevice", "--duration", "31"],
    )

    assert result.exit_code != 0
    assert "between 0.1 and 30 seconds" in result.output
    assert recorder_calls == []


def test_voice_record_local_bounds_configured_real_microphone_duration(
    monkeypatch,
) -> None:
    recorder_calls: list[str] = []
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            default_recorder="sounddevice",
            default_record_duration=31.0,
        ),
    )
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda *args, **kwargs: recorder_calls.append("record"),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["record-local"])

    assert result.exit_code != 0
    assert "between 0.1 and 30 seconds" in result.output
    assert recorder_calls == []


def test_voice_mic_smoke_requires_explicit_duration(monkeypatch) -> None:
    recorder_calls: list[str] = []
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda *args, **kwargs: recorder_calls.append("record"),
    )

    result = CliRunner().invoke(voice_cmd.voice, ["mic-smoke"])

    assert result.exit_code != 0
    assert "Missing option '--duration'" in result.output
    assert recorder_calls == []


def test_voice_mic_smoke_requires_real_microphone_backend(monkeypatch) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["mic-smoke", "--duration", "0.1"],
    )

    assert result.exit_code != 0
    assert "--recorder macos" in result.output
    assert "--recorder sounddevice" in result.output


def test_voice_mic_smoke_inspects_and_deletes_mocked_recording(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[str] = []
    recorded_paths: list[Path] = []

    def fake_build_recorder(
        recorder_kind: str,
        *,
        output_dir: Path | None,
        **kwargs,
    ):
        assert recorder_kind == "sounddevice"
        recorder = voice_cmd.SilentWavRecorder(temp_dir=output_dir, sample_rate=8000)
        original_start = recorder.start

        def start(recording_id: str):
            handle = original_start(recording_id)
            recorded_paths.append(handle.path)
            return handle

        recorder.start = start
        return recorder

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(
        voice_cmd,
        "_post_json",
        lambda *args, **kwargs: post_calls.append("post"),
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(default_recorder="sounddevice"),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["mic-smoke", "--duration", "0.1", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "Microphone smoke test" in result.output
    assert "recorder: sounddevice" in result.output
    assert "sample_rate_hz: 8000" in result.output
    assert "file_kept: False" in result.output
    assert "transcription: skipped" in result.output
    assert "dispatch: skipped" in result.output
    assert "speech: skipped" in result.output
    assert len(recorded_paths) == 1
    assert not recorded_paths[0].exists()
    assert post_calls == []


def test_voice_mic_smoke_keeps_file_only_when_requested(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda recorder_kind, *, output_dir, **kwargs: voice_cmd.SilentWavRecorder(
            temp_dir=output_dir
        ),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-smoke",
            "--duration",
            "0.1",
            "--recorder",
            "sounddevice",
            "--output-dir",
            str(tmp_path),
            "--keep-file",
        ],
    )

    assert result.exit_code == 0
    path_line = next(
        line for line in result.output.splitlines() if line.strip().startswith("path:")
    )
    recorded_path = Path(path_line.split(":", 1)[1].strip())
    assert recorded_path.exists()
    assert "file_kept: True" in result.output


def test_voice_mic_smoke_invalid_wav_is_clear_and_deleted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorded_path = tmp_path / "invalid.wav"

    class InvalidWavRecorder:
        def start(self, recording_id: str):
            return SimpleNamespace(path=recorded_path)

        def stop(self, handle) -> None:
            handle.path.write_bytes(b"not a wav")

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda *args, **kwargs: InvalidWavRecorder(),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["mic-smoke", "--recorder", "sounddevice", "--duration", "0.1"],
    )

    assert result.exit_code != 0
    assert "readable WAV" in result.output
    assert "microphone permission" in result.output
    assert "input device access" in result.output
    assert not recorded_path.exists()


def test_voice_mic_transcribe_smoke_records_transcribes_and_deletes_without_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorded_paths: list[Path] = []
    post_calls: list[str] = []
    adapter_calls: list[tuple[Path, str | None]] = []

    class FakeAdapter:
        def transcribe_file(self, path: Path, *, language: str | None = None):
            adapter_calls.append((path, language))
            assert path.exists()
            return _FakeTranscriptionResult()

    def fake_build_recorder(recorder_kind: str, *, output_dir: Path | None, **kwargs):
        assert recorder_kind == "sounddevice"
        recorder = voice_cmd.SilentWavRecorder(temp_dir=output_dir, sample_rate=8000)
        original_start = recorder.start

        def start(recording_id: str):
            handle = original_start(recording_id)
            recorded_paths.append(handle.path)
            return handle

        recorder.start = start
        return recorder

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(
        voice_cmd,
        "_build_transcriber",
        lambda adapter: ("faster-whisper", FakeAdapter()),
    )
    monkeypatch.setattr(
        voice_cmd,
        "_post_json",
        lambda *args, **kwargs: post_calls.append("post"),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-transcribe-smoke",
            "--duration",
            "0.1",
            "--recorder",
            "sounddevice",
            "--adapter",
            "faster-whisper",
            "--language",
            "en",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert adapter_calls == [(recorded_paths[0], "en")]
    assert not recorded_paths[0].exists()
    assert post_calls == []
    assert "Microphone transcription smoke test" in result.output
    assert "sample_rate_hz: 8000" in result.output
    assert "adapter: faster-whisper" in result.output
    assert "transcript: open notes" in result.output
    assert "file_kept: False" in result.output
    assert "submission: skipped" in result.output
    assert "dispatch: skipped" in result.output
    assert "speech: skipped" in result.output


def test_voice_mic_transcribe_smoke_resolves_adapter_before_recording(
    monkeypatch,
) -> None:
    recorder_calls: list[str] = []
    monkeypatch.setattr(
        voice_cmd,
        "_build_transcriber",
        lambda adapter: (_ for _ in ()).throw(
            voice_cmd.click.ClickException("local transcription adapter is required")
        ),
    )
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda *args, **kwargs: recorder_calls.append("record"),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-transcribe-smoke",
            "--duration",
            "0.1",
            "--recorder",
            "sounddevice",
        ],
    )

    assert result.exit_code != 0
    assert "local transcription adapter is required" in result.output
    assert recorder_calls == []


def test_voice_mic_transcribe_smoke_uses_configured_recorder_adapter_and_model(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorder_kinds: list[str] = []
    adapter_ids: list[str] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            adapter_ids.append(adapter_id)
            assert config.speech.model == "tiny"

        def transcribe_file(self, path: Path, *, language: str | None = None):
            return _FakeTranscriptionResult()

    def fake_build_recorder(recorder_kind: str, *, output_dir: Path | None, **kwargs):
        recorder_kinds.append(recorder_kind)
        return voice_cmd.SilentWavRecorder(temp_dir=output_dir)

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            default_recorder="sounddevice",
            transcription_adapter="faster-whisper",
            model_path="tiny",
        ),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-transcribe-smoke",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert recorder_kinds == ["sounddevice"]
    assert adapter_ids == ["faster-whisper"]


def test_voice_mic_transcribe_smoke_deletes_wav_when_transcription_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorded_paths: list[Path] = []

    class FailingAdapter:
        def transcribe_file(self, path: Path, *, language: str | None = None):
            raise voice_cmd.TranscriptionUnavailableError(
                "faster-whisper unavailable; install the speech dependency"
            )

    def fake_build_recorder(recorder_kind: str, *, output_dir: Path | None, **kwargs):
        recorder = voice_cmd.SilentWavRecorder(temp_dir=output_dir)
        original_start = recorder.start

        def start(recording_id: str):
            handle = original_start(recording_id)
            recorded_paths.append(handle.path)
            return handle

        recorder.start = start
        return recorder

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(
        voice_cmd,
        "_build_transcriber",
        lambda adapter: ("faster-whisper", FailingAdapter()),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-transcribe-smoke",
            "--duration",
            "0.1",
            "--recorder",
            "sounddevice",
            "--adapter",
            "faster-whisper",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "install the speech dependency" in result.output
    assert len(recorded_paths) == 1
    assert not recorded_paths[0].exists()


def test_voice_mic_transcribe_smoke_keeps_wav_only_when_requested(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda recorder_kind, *, output_dir, **kwargs: voice_cmd.SilentWavRecorder(
            temp_dir=output_dir
        ),
    )
    monkeypatch.setattr(
        voice_cmd,
        "_build_transcriber",
        lambda adapter: (
            "faster-whisper",
            SimpleNamespace(
                transcribe_file=lambda path, language=None: _FakeTranscriptionResult()
            ),
        ),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-transcribe-smoke",
            "--duration",
            "0.1",
            "--recorder",
            "sounddevice",
            "--adapter",
            "faster-whisper",
            "--output-dir",
            str(tmp_path),
            "--keep-file",
        ],
    )

    assert result.exit_code == 0
    path_line = next(
        line for line in result.output.splitlines() if line.strip().startswith("path:")
    )
    assert Path(path_line.split(":", 1)[1].strip()).exists()
    assert "file_kept: True" in result.output


def test_voice_capture_preview_requires_explicit_duration(monkeypatch) -> None:
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())

    result = CliRunner().invoke(voice_cmd.voice, ["capture-preview"])

    assert result.exit_code != 0
    assert "Missing option '--duration'" in result.output


def test_voice_mic_preview_requires_explicit_duration() -> None:
    result = CliRunner().invoke(voice_cmd.voice, ["mic-preview"])

    assert result.exit_code != 0
    assert "Missing option '--duration'" in result.output


def test_voice_mic_preview_requires_real_recorder_before_recording(
    monkeypatch,
) -> None:
    recorder_calls: list[str] = []
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda *args, **kwargs: recorder_calls.append("record") or None,
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        ["mic-preview", "--duration", "0.1", "--adapter", "faster-whisper"],
    )

    assert result.exit_code != 0
    assert "requires a real microphone recorder" in result.output
    assert recorder_calls == []


def test_voice_mic_preview_records_transcribes_previews_and_deletes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None]] = []
    recorded_paths: list[Path] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"

        def transcribe_file(self, path, *, language=None):
            recorded_paths.append(path)
            assert path.exists()
            assert language == "en"
            return _FakeTranscriptionResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return _preview_response()

    def fake_build_recorder(recorder_kind: str, *, output_dir: Path | None, **kwargs):
        assert recorder_kind == "sounddevice"
        return voice_cmd.SilentWavRecorder(temp_dir=output_dir, sample_rate=8000)

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
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
            "mic-preview",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--recorder",
            "sounddevice",
            "--adapter",
            "faster-whisper",
            "--language",
            "en",
        ],
    )

    assert result.exit_code == 0
    assert len(recorded_paths) == 1
    assert not recorded_paths[0].exists()
    assert post_calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        )
    ]
    assert "Microphone preview" in result.output
    assert "status: awaiting_approval" in result.output
    assert "dispatch: skipped" in result.output
    assert "speech: skipped" in result.output


def test_voice_mic_preview_deletes_wav_when_api_connection_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorded_paths: list[Path] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            pass

        def transcribe_file(self, path, *, language=None):
            recorded_paths.append(path)
            return _FakeTranscriptionResult()

    def fake_build_recorder(recorder_kind: str, *, output_dir: Path | None, **kwargs):
        return voice_cmd.SilentWavRecorder(temp_dir=output_dir, sample_rate=8000)

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        voice_cmd,
        "_post_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            voice_cmd.click.ClickException(
                "Could not reach http://test: connection refused"
            )
        ),
    )
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-preview",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--recorder",
            "sounddevice",
            "--adapter",
            "faster-whisper",
        ],
    )

    assert result.exit_code != 0
    assert "Could not reach http://test" in result.output
    assert len(recorded_paths) == 1
    assert not recorded_paths[0].exists()


def test_voice_mic_preview_uses_configured_backends_and_keeps_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorder_kinds: list[str] = []
    adapter_ids: list[str] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            adapter_ids.append(adapter_id)
            assert config.speech.model == "tiny"

        def transcribe_file(self, path, *, language=None):
            return _FakeTranscriptionResult()

    def fake_build_recorder(recorder_kind: str, *, output_dir: Path | None, **kwargs):
        recorder_kinds.append(recorder_kind)
        return voice_cmd.SilentWavRecorder(temp_dir=output_dir)

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(voice_cmd, "_build_recorder", fake_build_recorder)
    monkeypatch.setattr(
        voice_cmd,
        "SpeechBackendLocalTranscriptionAdapter",
        FakeAdapter,
    )
    monkeypatch.setattr(
        voice_cmd,
        "load_config",
        lambda: _safe_config(
            default_recorder="sounddevice",
            transcription_adapter="faster-whisper",
            model_path="tiny",
        ),
    )
    monkeypatch.setattr(
        voice_cmd,
        "_post_json",
        lambda *args, **kwargs: _preview_response(),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-preview",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--keep-file",
        ],
    )

    assert result.exit_code == 0
    assert recorder_kinds == ["sounddevice"]
    assert adapter_ids == ["faster-whisper"]
    path_line = next(
        line for line in result.output.splitlines() if line.strip().startswith("path:")
    )
    assert Path(path_line.split(":", 1)[1].strip()).exists()
    assert "file_kept: True" in result.output


def test_voice_mic_run_previews_only_and_deletes_wav_by_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None]] = []
    recorded_paths: list[Path] = []
    speech_calls: list[str] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            assert adapter_id == "faster-whisper"

        def transcribe_file(self, path, *, language=None):
            recorded_paths.append(path)
            assert path.exists()
            return _FakeTranscriptionResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        post_calls.append((endpoint, payload))
        return _preview_response()

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda recorder_kind, *, output_dir, **kwargs: voice_cmd.SilentWavRecorder(
            temp_dir=output_dir,
            sample_rate=8000,
        ),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
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
            "mic-run",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--recorder",
            "sounddevice",
            "--adapter",
            "faster-whisper",
        ],
    )

    assert result.exit_code == 0
    assert post_calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        )
    ]
    assert len(recorded_paths) == 1
    assert not recorded_paths[0].exists()
    assert speech_calls == []
    assert "status: awaiting_approval" in result.output
    assert "dispatch: skipped" in result.output
    assert "speech: skipped" in result.output


def test_voice_mic_run_dispatches_and_speaks_only_with_explicit_flags(
    monkeypatch,
    tmp_path: Path,
) -> None:
    post_calls: list[tuple[str, dict[str, Any] | None]] = []
    recorded_paths: list[Path] = []
    speak_calls: list[str] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            pass

        def transcribe_file(self, path, *, language=None):
            recorded_paths.append(path)
            return _FakeTranscriptionResult()

    class FakeSpeechOutput:
        def speak(self, text: str) -> None:
            speak_calls.append(text)

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
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda recorder_kind, *, output_dir, **kwargs: voice_cmd.SilentWavRecorder(
            temp_dir=output_dir,
            sample_rate=8000,
        ),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
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
        lambda *args, **kwargs: FakeSpeechOutput(),
    )

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "mic-run",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--recorder",
            "sounddevice",
            "--adapter",
            "faster-whisper",
            "--agent-id",
            "agent-1",
            "--approve-dispatch",
            "--speak-result",
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
    assert speak_calls == ["done"]
    assert len(recorded_paths) == 1
    assert not recorded_paths[0].exists()
    assert "speech: spoken" in result.output


def test_voice_mic_run_speak_result_requires_dispatch_approval() -> None:
    result = CliRunner().invoke(
        voice_cmd.voice,
        ["mic-run", "--duration", "0.1", "--speak-result"],
    )

    assert result.exit_code != 0
    assert "--speak-result requires --approve-dispatch" in result.output


def test_voice_mic_run_deletes_wav_when_dispatch_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    recorded_paths: list[Path] = []

    class FakeAdapter:
        def __init__(self, *, adapter_id, config):
            pass

        def transcribe_file(self, path, *, language=None):
            recorded_paths.append(path)
            return _FakeTranscriptionResult()

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        if endpoint.endswith("/submit-transcript"):
            return _preview_response()
        raise voice_cmd.click.ClickException(
            "/v1/voice/ptt/dispatch returned HTTP 500: dispatch failed"
        )

    monkeypatch.setattr(voice_cmd, "_sleep", lambda seconds: None)
    monkeypatch.setattr(
        voice_cmd,
        "_build_recorder",
        lambda recorder_kind, *, output_dir, **kwargs: voice_cmd.SilentWavRecorder(
            temp_dir=output_dir,
            sample_rate=8000,
        ),
    )
    monkeypatch.setattr(voice_cmd, "load_config", lambda: _safe_config())
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
            "mic-run",
            "--duration",
            "0.1",
            "--output-dir",
            str(tmp_path),
            "--recorder",
            "sounddevice",
            "--adapter",
            "faster-whisper",
            "--approve-dispatch",
        ],
    )

    assert result.exit_code != 0
    assert "dispatch returned HTTP 500: dispatch failed" in result.output
    assert len(recorded_paths) == 1
    assert not recorded_paths[0].exists()


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
