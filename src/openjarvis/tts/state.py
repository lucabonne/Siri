"""In-memory state for local voice output."""

from __future__ import annotations

from typing import Any

from openjarvis.tts.models import TTSSpeech


class TTSStateStore:
    """Small state holder for active and latest speech."""

    def __init__(self) -> None:
        self._active_speech: TTSSpeech | None = None
        self._active_handle: Any = None
        self._latest_speech: TTSSpeech | None = None
        self.selected_voice_id: str = ""
        self.selected_engine: str = ""

    @property
    def active_speech(self) -> TTSSpeech | None:
        return self._active_speech

    @property
    def active_handle(self) -> Any:
        return self._active_handle

    @property
    def latest_speech(self) -> TTSSpeech | None:
        return self._latest_speech or self._active_speech

    def begin(self, speech: TTSSpeech, handle: Any) -> None:
        self._active_speech = speech
        self._active_handle = handle
        self._latest_speech = speech
        self.selected_voice_id = speech.voice_id
        self.selected_engine = speech.engine

    def finish_active(self) -> TTSSpeech | None:
        speech = self._active_speech
        self._active_speech = None
        self._active_handle = None
        if speech is not None:
            self._latest_speech = speech
        return speech


__all__ = ["TTSStateStore"]
