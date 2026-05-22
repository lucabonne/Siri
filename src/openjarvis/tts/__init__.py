"""Local-only voice output support."""

from openjarvis.tts.engines import LocalTTSEngine, MacOSSayEngine, PiperEngine
from openjarvis.tts.models import (
    TTSError,
    TTSPermissionError,
    TTSSpeakRequest,
    TTSSpeech,
    TTSUnavailableError,
    TTSVoice,
)
from openjarvis.tts.service import LocalTTSService

__all__ = [
    "LocalTTSEngine",
    "LocalTTSService",
    "MacOSSayEngine",
    "PiperEngine",
    "TTSError",
    "TTSPermissionError",
    "TTSSpeakRequest",
    "TTSSpeech",
    "TTSUnavailableError",
    "TTSVoice",
]
