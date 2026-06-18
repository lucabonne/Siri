from __future__ import annotations

import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from openjarvis.voice.models import VoiceRecordingError
from openjarvis.voice.recorder import SilentWavRecorder, SoundDeviceRecorder


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
