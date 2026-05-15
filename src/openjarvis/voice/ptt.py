"""Compatibility imports for the modular voice subsystem."""

from openjarvis.voice.models import (
    RecordingHandle,
    TranscriptionUnavailableError,
    VoiceIntentPreview,
    VoicePermissionDecision,
    VoicePermissionError,
    VoiceRecordingError,
    VoiceSession,
)
from openjarvis.voice.recorder import LocalMacOSRecorder, Recorder
from openjarvis.voice.service import VoicePushToTalkService
from openjarvis.voice.transcription import LocalVoiceTranscriber

__all__ = [
    "LocalMacOSRecorder",
    "LocalVoiceTranscriber",
    "Recorder",
    "RecordingHandle",
    "TranscriptionUnavailableError",
    "VoiceIntentPreview",
    "VoicePermissionDecision",
    "VoicePermissionError",
    "VoicePushToTalkService",
    "VoiceRecordingError",
    "VoiceSession",
]
