"""Local microphone recording for explicit push-to-talk sessions."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Protocol

from openjarvis.voice.models import RecordingHandle, VoiceRecordingError


class Recorder(Protocol):
    """Explicit local recorder boundary used by the voice service and CLI.

    Implementations must only capture between a direct ``start`` call and a
    direct ``stop`` call. Hotkey listeners, wake words, and background capture
    live outside this interface and are intentionally not part of Phase 6.
    """

    def start(self, recording_id: str) -> RecordingHandle:
        """Start local microphone capture."""

    def stop(self, handle: RecordingHandle) -> None:
        """Stop local microphone capture."""


class LocalMacOSRecorder:
    """macOS microphone recorder using local command-line tools."""

    def __init__(
        self,
        *,
        temp_dir: str | os.PathLike[str] | None = None,
        input_device: str = ":0",
        sample_rate: int = 16000,
    ) -> None:
        self._temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self._input_device = input_device
        self._sample_rate = sample_rate

    def start(self, recording_id: str) -> RecordingHandle:
        if platform.system() != "Darwin":
            raise VoiceRecordingError(
                "local microphone recording is supported on macOS"
            )
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        path = self._temp_dir / f"openjarvis-ptt-{recording_id}.wav"
        command = self._record_command(path)
        if not command:
            raise VoiceRecordingError(
                "install ffmpeg or sox to record local microphone audio"
            )
        try:
            process = subprocess.Popen(  # noqa: S603
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise VoiceRecordingError(str(exc)) from exc
        return RecordingHandle(
            recording_id=recording_id,
            path=path,
            format="wav",
            process=process,
            started_at=time.monotonic(),
        )

    def stop(self, handle: RecordingHandle) -> None:
        process = handle.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if not handle.path.exists():
            raise VoiceRecordingError("recording did not produce an audio file")

    def _record_command(self, path: Path) -> list[str]:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "avfoundation",
                "-i",
                self._input_device,
                "-ac",
                "1",
                "-ar",
                str(self._sample_rate),
                "-y",
                str(path),
            ]
        rec = shutil.which("rec")
        if rec:
            return [
                rec,
                "-q",
                str(path),
                "channels",
                "1",
                "rate",
                str(self._sample_rate),
            ]
        return []


class SilentWavRecorder:
    """Development recorder that writes a local silent WAV on explicit stop."""

    def __init__(
        self,
        *,
        temp_dir: str | os.PathLike[str] | None = None,
        sample_rate: int = 16000,
    ) -> None:
        self._temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self._sample_rate = sample_rate

    def start(self, recording_id: str) -> RecordingHandle:
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        path = self._temp_dir / f"openjarvis-ptt-{recording_id}.wav"
        return RecordingHandle(
            recording_id=recording_id,
            path=path,
            format="wav",
            started_at=time.monotonic(),
        )

    def stop(self, handle: RecordingHandle) -> None:
        duration = max(0.01, time.monotonic() - handle.started_at)
        frames = int(self._sample_rate * duration)
        handle.path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(handle.path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self._sample_rate)
            wav.writeframes(b"\x00\x00" * frames)


__all__ = ["LocalMacOSRecorder", "Recorder", "SilentWavRecorder"]
