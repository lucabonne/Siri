"""Local structured event logging for explicit voice CLI actions."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
_URL_RE = re.compile(r"\bhttps?://\S+")
_TOKEN_RE = re.compile(r"\b(?:sk|pk|api|token|key)-[A-Za-z0-9_-]{8,}\b", re.I)
_LONG_SECRET_RE = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")


@dataclass(frozen=True, slots=True)
class VoiceLogSettings:
    enabled: bool
    path: Path
    include_full_transcripts: bool
    preview_chars: int = 80


def voice_log_settings_from_config(config: Any) -> VoiceLogSettings:
    voice_control = getattr(config, "voice_control", None)
    enabled = bool(getattr(voice_control, "voice_logs_enabled", False))
    raw_path = getattr(voice_control, "voice_logs_path", "")
    has_path = bool(str(raw_path).strip())
    path = Path(str(raw_path)).expanduser() if has_path else Path()
    include_full = bool(
        getattr(voice_control, "voice_logs_include_full_transcripts", False)
    )
    raw_preview_chars = getattr(voice_control, "voice_logs_preview_chars", 80) or 80
    try:
        preview_chars = max(0, int(raw_preview_chars))
    except (TypeError, ValueError):
        preview_chars = 80
    return VoiceLogSettings(
        enabled=enabled and has_path,
        path=path,
        include_full_transcripts=include_full,
        preview_chars=preview_chars,
    )


def redact_transcript_preview(text: str, *, limit: int = 80) -> str:
    redacted = _URL_RE.sub("[url]", text)
    redacted = _EMAIL_RE.sub("[email]", redacted)
    redacted = _TOKEN_RE.sub("[secret]", redacted)
    redacted = _LONG_SECRET_RE.sub("[secret]", redacted)
    redacted = _PHONE_RE.sub("[phone]", redacted)
    redacted = " ".join(redacted.split())
    return redacted[:limit] if limit >= 0 else redacted


def transcript_summary(
    text: str,
    *,
    include_full: bool,
    preview_chars: int,
) -> dict[str, Any]:
    encoded = text.encode("utf-8")
    summary: dict[str, Any] = {
        "length": len(text),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }
    if include_full:
        summary["text"] = text
    else:
        summary["preview"] = redact_transcript_preview(text, limit=preview_chars)
    return summary


class VoiceEventLogger:
    def __init__(self, settings: VoiceLogSettings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    @property
    def path(self) -> Path:
        return self.settings.path

    def record(
        self,
        *,
        command: str,
        event: str,
        status: str = "ok",
        transcript: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return

        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "command": command,
            "event": event,
            "status": status,
        }
        if transcript is not None:
            payload["transcript"] = transcript_summary(
                transcript,
                include_full=self.settings.include_full_transcripts,
                preview_chars=self.settings.preview_chars,
            )
        if details:
            payload["details"] = details

        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
            fd = os.open(
                self.path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            return


def read_voice_events(path: Path, *, limit: int) -> list[dict[str, Any]]:
    return query_voice_events(path, limit=limit)


def query_voice_events(
    path: Path,
    *,
    limit: int,
    event_types: tuple[str, ...] = (),
    statuses: tuple[str, ...] = (),
    success: bool | None = None,
    approval_dispatch_only: bool = False,
) -> list[dict[str, Any]]:
    if limit <= 0 or not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and _matches_voice_event(
            item,
            event_types=event_types,
            statuses=statuses,
            success=success,
            approval_dispatch_only=approval_dispatch_only,
        ):
            events.append(item)
    return events[-limit:]


def _matches_voice_event(
    event: dict[str, Any],
    *,
    event_types: tuple[str, ...],
    statuses: tuple[str, ...],
    success: bool | None,
    approval_dispatch_only: bool,
) -> bool:
    event_type = str(event.get("event", ""))
    if event_types and event_type not in event_types:
        return False

    status = str(event.get("status", "ok"))
    if statuses and status not in statuses:
        return False
    if success is True and (status != "ok" or _is_failure_event(event, status)):
        return False
    if success is False and not _is_failure_event(event, status):
        return False
    return not approval_dispatch_only or is_approval_dispatch_event(event)


def _is_failure_event(event: dict[str, Any], status: str) -> bool:
    if status in {"error", "failed", "failure"}:
        return True
    details = event.get("details")
    return isinstance(details, dict) and bool(details.get("has_error"))


def is_approval_dispatch_event(event: dict[str, Any]) -> bool:
    event_type = str(event.get("event", ""))
    if "approval" in event_type or "dispatch" in event_type:
        return True
    details = event.get("details")
    return isinstance(details, dict) and any(
        key in details
        for key in ("approval_required", "approved", "dispatched", "dispatch_status")
    )


__all__ = [
    "VoiceEventLogger",
    "VoiceLogSettings",
    "is_approval_dispatch_event",
    "query_voice_events",
    "read_voice_events",
    "redact_transcript_preview",
    "transcript_summary",
    "voice_log_settings_from_config",
]
