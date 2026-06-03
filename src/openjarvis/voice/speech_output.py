"""Explicit local speech-output adapters for voice commands."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Protocol


class SpeechOutputUnavailableError(RuntimeError):
    """Raised when a requested local speech-output adapter cannot run."""


class LocalSpeechOutput(Protocol):
    """Boundary for explicit local speech playback.

    Implementations must only speak when ``speak`` is called directly.
    """

    adapter_id: str

    def is_available(self) -> bool:
        """Return whether this adapter can speak on the current system."""

    def speak(self, text: str) -> None:
        """Speak text locally."""


@dataclass(slots=True)
class MacOSSaySpeechOutput:
    """Local speech output using the macOS ``say`` command."""

    voice: str = ""
    rate: int | None = None
    executable: str | None = None

    adapter_id: str = "macos-say"

    def _executable_path(self) -> str | None:
        return self.executable or shutil.which("say")

    def is_available(self) -> bool:
        return sys.platform == "darwin" and bool(self._executable_path())

    def speak(self, text: str) -> None:
        normalized = text.strip()
        if not normalized:
            raise ValueError("text must not be empty")

        executable = self._executable_path()
        if sys.platform != "darwin" or not executable:
            raise SpeechOutputUnavailableError(
                "macOS say speech output is unavailable on this system"
            )

        command = [executable]
        if self.voice:
            command.extend(["-v", self.voice])
        if self.rate is not None:
            command.extend(["-r", str(self.rate)])

        try:
            subprocess.run(
                command,
                input=normalized,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SpeechOutputUnavailableError(
                f"macOS say speech output failed: {exc}"
            ) from exc


LOCAL_SPEECH_OUTPUT_ADAPTERS = ("macos-say",)


def build_local_speech_output(
    adapter_id: str,
    *,
    voice: str = "",
    rate: int | None = None,
) -> LocalSpeechOutput:
    """Build an explicit local speech-output adapter."""
    if adapter_id == "macos-say":
        return MacOSSaySpeechOutput(voice=voice, rate=rate)
    raise ValueError(f"unknown local speech-output adapter: {adapter_id}")


__all__ = [
    "LOCAL_SPEECH_OUTPUT_ADAPTERS",
    "LocalSpeechOutput",
    "MacOSSaySpeechOutput",
    "SpeechOutputUnavailableError",
    "build_local_speech_output",
]
