"""In-memory state for passive push-to-talk voice sessions."""

from __future__ import annotations

from pathlib import Path

from openjarvis.voice.models import RecordingHandle, VoiceSession


class VoiceStateStore:
    """Small state holder for the active and latest voice sessions."""

    def __init__(self) -> None:
        self._active_handle: RecordingHandle | None = None
        self._active_session: VoiceSession | None = None
        self._latest_session: VoiceSession | None = None

    @property
    def active_handle(self) -> RecordingHandle | None:
        return self._active_handle

    @property
    def active_session(self) -> VoiceSession | None:
        return self._active_session

    @property
    def latest_session(self) -> VoiceSession | None:
        return self._latest_session or self._active_session

    def begin(self, session: VoiceSession, handle: RecordingHandle) -> None:
        self._active_session = session
        self._active_handle = handle
        self._latest_session = session

    def finish_active(self) -> VoiceSession | None:
        session = self._active_session
        self._active_session = None
        self._active_handle = None
        if session is not None:
            self._latest_session = session
        return session

    def clear_audio_if_needed(self, *, persist_raw_audio: bool) -> None:
        session = self._latest_session
        if session is None or persist_raw_audio or not session.audio_path:
            return
        try:
            Path(session.audio_path).unlink(missing_ok=True)
        except OSError:
            pass
        session.audio_path = ""
        session.raw_audio_available = False


__all__ = ["VoiceStateStore"]
