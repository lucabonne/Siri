from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from openjarvis.voice.event_log import (
    VoiceEventLogger,
    read_voice_events,
    redact_transcript_preview,
    voice_log_settings_from_config,
)


def _config(path: Path, *, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        voice_control=SimpleNamespace(
            voice_logs_enabled=enabled,
            voice_logs_path=str(path),
            voice_logs_include_full_transcripts=False,
            voice_logs_preview_chars=80,
        )
    )


def test_redacts_transcript_preview() -> None:
    preview = redact_transcript_preview(
        "email luca@example.com with token sk-1234567890abcdef at +1 415 555 1212"
    )

    assert "luca@example.com" not in preview
    assert "sk-1234567890abcdef" not in preview
    assert "415 555 1212" not in preview
    assert "[email]" in preview
    assert "[secret]" in preview
    assert "[phone]" in preview


def test_writes_local_structured_log_without_full_transcript(tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    logger = VoiceEventLogger(voice_log_settings_from_config(_config(log_path)))

    logger.record(
        command="submit",
        event="preview_result",
        transcript="open notes for luca@example.com",
        details={"approved": False},
    )

    events = read_voice_events(log_path, limit=10)
    assert len(events) == 1
    event = events[0]
    assert event["command"] == "submit"
    assert event["event"] == "preview_result"
    assert event["details"] == {"approved": False}
    assert event["transcript"]["length"] == len("open notes for luca@example.com")
    assert len(event["transcript"]["sha256"]) == 64
    assert event["transcript"]["preview"] == "open notes for [email]"
    assert "text" not in event["transcript"]
    assert "luca@example.com" not in log_path.read_text(encoding="utf-8")


def test_disabled_logging_does_not_create_file(tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    logger = VoiceEventLogger(
        voice_log_settings_from_config(_config(log_path, enabled=False))
    )

    logger.record(command="status", event="status_result")

    assert not log_path.exists()


def test_read_voice_events_skips_invalid_json(tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    log_path.write_text(
        "not-json\n" + json.dumps({"command": "status", "event": "status_result"}),
        encoding="utf-8",
    )

    assert read_voice_events(log_path, limit=5) == [
        {"command": "status", "event": "status_result"}
    ]
