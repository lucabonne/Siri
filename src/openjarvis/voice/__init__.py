"""Explicit push-to-talk voice capture support."""

from openjarvis.voice.models import (
    RecordingHandle,
    TranscriptionUnavailableError,
    VoiceIntentPreview,
    VoicePermissionDecision,
    VoicePermissionError,
    VoiceRecordingError,
    VoiceSession,
)
from openjarvis.voice.recorder import LocalMacOSRecorder, SilentWavRecorder
from openjarvis.voice.service import VoicePushToTalkService
from openjarvis.voice.session_fsm import (
    VoiceSessionFSM,
    VoiceSessionFSMError,
    VoiceSessionState,
)
from openjarvis.voice.speech_output import (
    LocalSpeechOutput,
    MacOSSaySpeechOutput,
    SpeechOutputUnavailableError,
)
from openjarvis.voice.transcription import (
    LocalTranscriptionAdapter,
    LocalVoiceTranscriber,
    SpeechBackendLocalTranscriptionAdapter,
)

__all__ = [
    "LocalMacOSRecorder",
    "LocalSpeechOutput",
    "LocalTranscriptionAdapter",
    "LocalVoiceTranscriber",
    "MacOSSaySpeechOutput",
    "RecordingHandle",
    "SpeechOutputUnavailableError",
    "TranscriptionUnavailableError",
    "VoiceIntentPreview",
    "VoicePermissionDecision",
    "VoicePermissionError",
    "VoicePushToTalkService",
    "VoiceRecordingError",
    "VoiceSession",
    "VoiceSessionFSM",
    "VoiceSessionFSMError",
    "VoiceSessionState",
    "SpeechBackendLocalTranscriptionAdapter",
    "SilentWavRecorder",
]
