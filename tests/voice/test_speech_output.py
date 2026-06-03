"""Tests for explicit local speech-output adapters."""

from __future__ import annotations

import pytest

from openjarvis.voice import speech_output
from openjarvis.voice.speech_output import (
    MacOSSaySpeechOutput,
    SpeechOutputUnavailableError,
    build_local_speech_output,
)


def test_macos_say_uses_stdin_for_spoken_text(monkeypatch) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(command, *, input, text, check):
        calls.append((command, input))
        assert text is True
        assert check is True

    monkeypatch.setattr(speech_output.sys, "platform", "darwin")
    monkeypatch.setattr(speech_output.shutil, "which", lambda name: "/usr/bin/say")
    monkeypatch.setattr(speech_output.subprocess, "run", fake_run)

    adapter = MacOSSaySpeechOutput(voice="Alex", rate=180)
    adapter.speak("-v Victoria hello")

    assert calls == [(["/usr/bin/say", "-v", "Alex", "-r", "180"], "-v Victoria hello")]


def test_macos_say_requires_macos_and_say_binary(monkeypatch) -> None:
    run_calls: list[str] = []

    monkeypatch.setattr(speech_output.sys, "platform", "linux")
    monkeypatch.setattr(speech_output.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        speech_output.subprocess,
        "run",
        lambda *args, **kwargs: run_calls.append("run"),
    )

    adapter = MacOSSaySpeechOutput()

    assert adapter.is_available() is False
    with pytest.raises(SpeechOutputUnavailableError):
        adapter.speak("hello")
    assert run_calls == []


def test_build_local_speech_output_rejects_unknown_adapter() -> None:
    with pytest.raises(ValueError):
        build_local_speech_output("piper")
