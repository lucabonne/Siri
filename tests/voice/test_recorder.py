from __future__ import annotations

import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from openjarvis.voice.models import VoiceRecordingError
from openjarvis.voice.recorder import (
    SilentWavRecorder,
    SoundDeviceRecorder,
    inspect_wav_file,
    recorder_diagnostics,
)


def test_recorder_diagnostics_are_configuration_only() -> None:
    executable_checks: list[str] = []

    diagnostics = recorder_diagnostics(
        "sounddevice",
        sounddevice_importable=True,
        system_name="Darwin",
        executable_finder=lambda name: executable_checks.append(name) or None,
    )

    assert diagnostics["configured_default"] == "sounddevice"
    assert diagnostics["sounddevice_importable"] is True
    assert diagnostics["microphone_recording_configured"] is True
    assert diagnostics["microphone_configuration_ready"] is True
    assert diagnostics["microphone_permission_checked"] is False
    assert diagnostics["status_check"] == "configuration_only"
    assert (
        "System Settings > Privacy & Security > Microphone"
        in diagnostics["macos_microphone_permission_guidance"]
    )
    assert executable_checks == []


def test_macos_recorder_diagnostics_use_mocked_tool_lookup() -> None:
    diagnostics = recorder_diagnostics(
        "macos",
        sounddevice_importable=False,
        system_name="Darwin",
        executable_finder=lambda name: (
            "/opt/homebrew/bin/ffmpeg" if name == "ffmpeg" else None
        ),
    )

    assert diagnostics["backend_available"] is True
    assert diagnostics["macos_recording_tool"] == "/opt/homebrew/bin/ffmpeg"


def test_silent_wav_recorder_requires_explicit_start_stop(tmp_path: Path) -> None:
    recorder = SilentWavRecorder(temp_dir=tmp_path, sample_rate=8000)

    handle = recorder.start("dev")
    assert not handle.path.exists()

    recorder.stop(handle)

    assert handle.path.exists()
    with wave.open(str(handle.path), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 8000
        assert wav.getnframes() > 0


def test_inspect_wav_file_returns_basic_metadata(tmp_path: Path) -> None:
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 800)

    metadata = inspect_wav_file(path)

    assert metadata == {
        "size_bytes": path.stat().st_size,
        "channels": 1,
        "sample_width_bytes": 2,
        "sample_rate_hz": 8000,
        "frame_count": 800,
        "audio_duration_seconds": 0.1,
    }


def test_inspect_wav_file_rejects_invalid_recording_with_guidance(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.wav"
    path.write_bytes(b"not a wav")

    with pytest.raises(VoiceRecordingError) as exc_info:
        inspect_wav_file(path)

    message = str(exc_info.value)
    assert "readable WAV" in message
    assert "microphone permission" in message
    assert "input device access" in message


def test_sounddevice_recorder_writes_wav_with_mocked_stream(tmp_path: Path) -> None:
    class FakeAudio:
        def copy(self):
            return self

        def tobytes(self):
            return b"\x01\x00" * 160

    class FakeStream:
        def __init__(self, **kwargs):
            self._callback = kwargs["callback"]
            self.started = False
            self.closed = False

        def start(self) -> None:
            self.started = True
            self._callback(FakeAudio(), 160, None, None)

        def stop(self) -> None:
            assert self.started is True

        def close(self) -> None:
            self.closed = True

    fake_module = SimpleNamespace(InputStream=FakeStream)
    recorder = SoundDeviceRecorder(
        temp_dir=tmp_path,
        sample_rate=8000,
        module_loader=lambda name: fake_module,
    )

    handle = recorder.start("mic")
    assert not handle.path.exists()

    recorder.stop(handle)

    assert handle.path.exists()
    with wave.open(str(handle.path), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 8000
        assert wav.getnframes() == 160


def test_sounddevice_recorder_missing_dependency_has_install_guidance(
    tmp_path: Path,
) -> None:
    def missing_module(name: str):
        raise ImportError(name)

    recorder = SoundDeviceRecorder(temp_dir=tmp_path, module_loader=missing_module)

    with pytest.raises(VoiceRecordingError) as exc_info:
        recorder.start("mic")

    assert "uv sync --extra voice-mic" in str(exc_info.value)


def test_sounddevice_recorder_start_failure_has_macos_permission_guidance(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class BrokenStream:
        def __init__(self, **kwargs):
            pass

        def start(self) -> None:
            raise RuntimeError("Input overflowed")

    fake_module = SimpleNamespace(InputStream=BrokenStream)
    recorder = SoundDeviceRecorder(
        temp_dir=tmp_path,
        module_loader=lambda name: fake_module,
    )
    monkeypatch.setattr("openjarvis.voice.recorder.platform.system", lambda: "Darwin")

    with pytest.raises(VoiceRecordingError) as exc_info:
        recorder.start("mic")

    message = str(exc_info.value)
    assert "Microphone access" in message
    assert "System Settings > Privacy & Security > Microphone" in message
