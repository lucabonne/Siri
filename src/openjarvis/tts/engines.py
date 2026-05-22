"""Local text-to-speech engine adapters."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from openjarvis.tts.models import TTSUnavailableError, TTSVoice


class LocalTTSEngine(Protocol):
    """Protocol implemented by local TTS process adapters."""

    engine_id: str

    def available(self) -> bool:
        """Return whether the engine is available on this machine."""

    def voices(self) -> list[TTSVoice]:
        """Return local voices known to this engine."""

    def speak(self, text: str, *, voice_id: str = "", speed: float = 1.0):
        """Start speaking text and return a process-like handle."""

    def stop(self, handle) -> None:
        """Stop a handle previously returned by ``speak``."""


class MacOSSayEngine:
    """Local macOS ``say`` engine."""

    engine_id = "macos_say"

    def __init__(self, *, say_path: str | None = None) -> None:
        self._say_path = say_path or shutil.which("say") or "say"

    def available(self) -> bool:
        return (
            platform.system() == "Darwin"
            and shutil.which(self._say_path) is not None
        )

    def voices(self) -> list[TTSVoice]:
        if not self.available():
            return []
        try:
            result = subprocess.run(
                [self._say_path, "-v", "?"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return []
        voices: list[TTSVoice] = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if not parts:
                continue
            voice_id = parts[0]
            locale = parts[1] if len(parts) > 1 and "_" in parts[1] else ""
            voices.append(
                TTSVoice(
                    id=voice_id,
                    name=voice_id,
                    engine=self.engine_id,
                    locale=locale,
                )
            )
        return voices

    def speak(self, text: str, *, voice_id: str = "", speed: float = 1.0):
        if not self.available():
            raise TTSUnavailableError("macOS say is not available")
        cmd = [self._say_path]
        if voice_id:
            cmd.extend(["-v", voice_id])
        if speed and speed > 0:
            cmd.extend(["-r", str(max(80, min(450, int(200 * speed))))])
        cmd.append(text)
        return subprocess.Popen(cmd)

    def stop(self, handle) -> None:
        _terminate_process(handle)


class PiperEngine:
    """Optional local Piper engine.

    Piper is enabled only when the ``piper`` binary is installed and a local
    model path is supplied through ``OPENJARVIS_PIPER_MODEL``.
    """

    engine_id = "piper"

    def __init__(
        self,
        *,
        piper_path: str | None = None,
        model_path: str | None = None,
        player_path: str | None = None,
    ) -> None:
        self._piper_path = piper_path or shutil.which("piper") or "piper"
        self._model_path = model_path or os.getenv("OPENJARVIS_PIPER_MODEL", "")
        self._player_path = (
            player_path or shutil.which("afplay") or shutil.which("aplay")
        )

    def available(self) -> bool:
        return (
            shutil.which(self._piper_path) is not None
            and bool(self._model_path)
            and Path(self._model_path).expanduser().exists()
            and self._player_path is not None
        )

    def voices(self) -> list[TTSVoice]:
        if not self.available():
            return []
        model = Path(self._model_path).expanduser()
        return [
            TTSVoice(
                id=str(model),
                name=model.stem,
                engine=self.engine_id,
                metadata={"model_path": str(model)},
            )
        ]

    def speak(self, text: str, *, voice_id: str = "", speed: float = 1.0):
        if not self.available():
            raise TTSUnavailableError(
                "Piper is not installed or no local model is configured"
            )
        model = Path(voice_id or self._model_path).expanduser()
        wav = Path(tempfile.mkstemp(prefix="openjarvis-piper-", suffix=".wav")[1])
        synth = subprocess.run(
            [self._piper_path, "--model", str(model), "--output_file", str(wav)],
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
        if synth.returncode != 0:
            try:
                wav.unlink(missing_ok=True)
            except OSError:
                pass
            raise TTSUnavailableError(synth.stderr.strip() or "Piper synthesis failed")
        return subprocess.Popen([str(self._player_path), str(wav)])

    def stop(self, handle) -> None:
        _terminate_process(handle)


def _terminate_process(handle) -> None:
    if handle is None:
        return
    poll = getattr(handle, "poll", None)
    if callable(poll) and poll() is not None:
        return
    terminate = getattr(handle, "terminate", None)
    wait = getattr(handle, "wait", None)
    kill = getattr(handle, "kill", None)
    try:
        if callable(terminate):
            terminate()
        if callable(wait):
            wait(timeout=1)
    except Exception:
        try:
            if callable(kill):
                kill()
        except Exception:
            pass


def default_local_engines() -> list[LocalTTSEngine]:
    """Return local engines in preferred order."""
    return [MacOSSayEngine(), PiperEngine()]


__all__ = [
    "LocalTTSEngine",
    "MacOSSayEngine",
    "PiperEngine",
    "default_local_engines",
]
