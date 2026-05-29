from __future__ import annotations

import wave
from pathlib import Path

from openjarvis.voice.recorder import SilentWavRecorder


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
