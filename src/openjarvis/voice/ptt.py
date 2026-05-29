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
from openjarvis.voice.recorder import LocalMacOSRecorder, Recorder, SilentWavRecorder
from openjarvis.voice.service import VoicePushToTalkService
from openjarvis.voice.transcription import (
    LocalTranscriptionAdapter,
    LocalVoiceTranscriber,
    SpeechBackendLocalTranscriptionAdapter,
)

__all__ = [
    "LocalMacOSRecorder",
    "LocalTranscriptionAdapter",
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
    "SpeechBackendLocalTranscriptionAdapter",
    "SilentWavRecorder",
]
