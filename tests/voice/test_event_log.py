from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from openjarvis.voice.event_log import (
    VoiceEventLogger,
    cleanup_voice_events,
    query_voice_events,
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


def test_query_voice_events_filters_after_reading_local_log(tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    records = [
        {"command": "status", "event": "status_result", "status": "ok"},
        {
            "command": "submit",
            "event": "preview_result",
            "status": "ok",
            "details": {"approval_required": True, "approved": False},
        },
        {
            "command": "submit",
            "event": "dispatch_decision",
            "status": "skipped",
            "details": {"approved": False, "attempted": False},
        },
        {
            "command": "run-local",
            "event": "dispatch_result",
            "status": "ok",
            "details": {"has_error": True},
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )

    assert [
        event["event"]
        for event in query_voice_events(
            log_path,
            limit=10,
            event_types=("dispatch_result",),
        )
    ] == ["dispatch_result"]
    assert [
        event["event"]
        for event in query_voice_events(log_path, limit=10, statuses=("skipped",))
    ] == ["dispatch_decision"]
    assert [
        event["event"] for event in query_voice_events(log_path, limit=10, success=True)
    ] == ["status_result", "preview_result"]
    assert [
        event["event"]
        for event in query_voice_events(log_path, limit=10, success=False)
    ] == ["dispatch_result"]
    assert [
        event["event"]
        for event in query_voice_events(
            log_path,
            limit=2,
            approval_dispatch_only=True,
        )
    ] == ["dispatch_decision", "dispatch_result"]


def test_query_voice_events_empty_log_behavior(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.jsonl"
    empty_path = tmp_path / "empty.jsonl"
    empty_path.write_text("", encoding="utf-8")

    assert query_voice_events(missing_path, limit=10) == []
    assert query_voice_events(empty_path, limit=10) == []


def test_query_voice_events_preserves_redacted_transcript_summary(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    logger = VoiceEventLogger(voice_log_settings_from_config(_config(log_path)))

    logger.record(
        command="submit",
        event="preview_result",
        transcript="email luca@example.com token sk-1234567890abcdef",
    )

    events = query_voice_events(log_path, limit=1, event_types=("preview_result",))
    assert len(events) == 1
    transcript = events[0]["transcript"]
    assert transcript["preview"] == "email [email] token [secret]"
    assert "text" not in transcript


def test_cleanup_voice_events_dry_run_keeps_local_log(tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2025-12-31T23:59:59Z",
                        "command": "submit",
                        "event": "preview_result",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:00Z",
                        "command": "status",
                        "event": "status_result",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cleanup_voice_events(
        log_path,
        clear_before=datetime(2026, 1, 1),
        dry_run=True,
    )

    assert result.deleted_count == 1
    assert result.kept_count == 1
    assert result.changed is False
    assert "preview_result" in log_path.read_text(encoding="utf-8")


def test_cleanup_voice_events_confirmed_clear_truncates_log(tmp_path: Path) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    log_path.write_text(
        json.dumps({"command": "status", "event": "status_result"}) + "\n",
        encoding="utf-8",
    )

    result = cleanup_voice_events(log_path, clear_all=True, dry_run=False)

    assert result.deleted_count == 1
    assert result.kept_count == 0
    assert result.changed is True
    assert log_path.read_text(encoding="utf-8") == ""


def test_cleanup_voice_events_clear_before_retains_new_and_undated_lines(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "voice-events.jsonl"
    old = {"timestamp": "2025-12-31T23:59:59Z", "event": "old"}
    new = {"timestamp": "2026-01-01T00:00:00Z", "event": "new"}
    undated = {"event": "undated"}
    log_path.write_text(
        "\n".join(json.dumps(item) for item in [old, new, undated]) + "\n",
        encoding="utf-8",
    )

    result = cleanup_voice_events(
        log_path,
        clear_before=datetime(2026, 1, 1),
        dry_run=False,
    )

    remaining = log_path.read_text(encoding="utf-8")
    assert result.deleted_count == 1
    assert '"event": "old"' not in remaining
    assert '"event": "new"' in remaining
    assert '"event": "undated"' in remaining


def test_cleanup_voice_events_empty_log_behavior(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.jsonl"
    empty_path = tmp_path / "empty.jsonl"
    empty_path.write_text("", encoding="utf-8")

    missing_result = cleanup_voice_events(missing_path, clear_all=True, dry_run=False)
    empty_result = cleanup_voice_events(empty_path, clear_all=True, dry_run=False)

    assert missing_result.exists is False
    assert missing_result.deleted_count == 0
    assert not missing_path.exists()
    assert empty_result.exists is True
    assert empty_result.deleted_count == 0
    assert empty_path.read_text(encoding="utf-8") == ""
