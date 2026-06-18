"""Local microphone recording for explicit push-to-talk sessions."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time
import wave
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import Callable, Protocol

from openjarvis.voice.models import RecordingHandle, VoiceRecordingError

RECORDER_KINDS = ("dev-silent", "macos", "sounddevice")
MICROPHONE_RECORDER_KINDS = ("macos", "sounddevice")


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
            message = "recording did not produce an audio file"
            if platform.system() == "Darwin":
                message = f"{message}. {macos_microphone_guidance()}"
            raise VoiceRecordingError(message)

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


def macos_microphone_guidance() -> str:
    return (
        "On macOS, grant Microphone access to the terminal app running jarvis "
        "in System Settings > Privacy & Security > Microphone, then restart "
        "that terminal."
    )


def recorder_diagnostics(
    configured_backend: str,
    *,
    sounddevice_importable: bool | None = None,
    system_name: str | None = None,
    executable_finder: Callable[[str], str | None] = shutil.which,
) -> dict[str, object]:
    """Return configuration-only recorder diagnostics without opening a device."""
    if sounddevice_importable is None:
        try:
            sounddevice_importable = find_spec("sounddevice") is not None
        except (ImportError, ValueError):
            sounddevice_importable = False

    system_name = system_name or platform.system()
    recording_tool = ""
    if configured_backend == "macos" and system_name == "Darwin":
        recording_tool = executable_finder("ffmpeg") or executable_finder("rec") or ""

    supported = configured_backend in RECORDER_KINDS
    if configured_backend == "sounddevice":
        backend_available = sounddevice_importable
    elif configured_backend == "macos":
        backend_available = system_name == "Darwin" and bool(recording_tool)
    else:
        backend_available = configured_backend == "dev-silent"

    microphone_configured = configured_backend in MICROPHONE_RECORDER_KINDS
    return {
        "configured_default": configured_backend,
        "supported": supported,
        "backend_available": backend_available,
        "microphone_recording_configured": microphone_configured,
        "microphone_configuration_ready": microphone_configured and backend_available,
        "sounddevice_importable": sounddevice_importable,
        "macos_recording_tool": recording_tool,
        "microphone_permission_checked": False,
        "macos_microphone_permission_guidance": macos_microphone_guidance(),
        "status_check": "configuration_only",
        "requires_explicit_command": True,
    }


class SoundDeviceRecorder:
    """Optional local microphone recorder using the ``sounddevice`` package."""

    def __init__(
        self,
        *,
        temp_dir: str | os.PathLike[str] | None = None,
        input_device: str | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
        module_loader: Callable[[str], ModuleType] = import_module,
    ) -> None:
        self._temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self._input_device = input_device
        self._sample_rate = sample_rate
        self._channels = channels
        self._module_loader = module_loader
        self._frames: list[bytes] = []

    def start(self, recording_id: str) -> RecordingHandle:
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        path = self._temp_dir / f"openjarvis-ptt-{recording_id}.wav"
        try:
            sounddevice = self._module_loader("sounddevice")
        except ImportError as exc:
            raise VoiceRecordingError(
                "sounddevice recorder requires the optional 'sounddevice' "
                "dependency. Install it with `uv sync --extra voice-mic` or "
                "`pip install sounddevice`."
            ) from exc

        self._frames = []

        def callback(indata, frames, time_info, status) -> None:
            del frames, time_info
            if status:
                # PortAudio status flags are diagnostic only; keep recording.
                pass
            self._frames.append(indata.copy().tobytes())

        try:
            stream = sounddevice.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                device=self._input_device,
                callback=callback,
            )
            stream.start()
        except Exception as exc:
            raise VoiceRecordingError(self._format_start_error(exc)) from exc

        return RecordingHandle(
            recording_id=recording_id,
            path=path,
            format="wav",
            process=stream,
            started_at=time.monotonic(),
        )

    def stop(self, handle: RecordingHandle) -> None:
        stream = handle.process
        try:
            if stream is not None:
                stream.stop()
                stream.close()
        except Exception as exc:
            raise VoiceRecordingError(str(exc)) from exc

        handle.path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(handle.path), "wb") as wav:
            wav.setnchannels(self._channels)
            wav.setsampwidth(2)
            wav.setframerate(self._sample_rate)
            wav.writeframes(b"".join(self._frames))

    def _format_start_error(self, exc: Exception) -> str:
        message = f"could not start sounddevice microphone recording: {exc}"
        if platform.system() == "Darwin":
            return f"{message}. {macos_microphone_guidance()}"
        return message


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


__all__ = [
    "LocalMacOSRecorder",
    "Recorder",
    "RECORDER_KINDS",
    "SilentWavRecorder",
    "SoundDeviceRecorder",
]
