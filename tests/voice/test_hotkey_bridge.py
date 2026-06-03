"""Tests for the disabled macOS hotkey bridge boundary."""

from __future__ import annotations

import pytest

from openjarvis.hotkeys.macos_bridge import (
    DisabledMacOSHotkeyBridge,
    MacOSHotkeyBridgeCommand,
)


def test_macos_hotkey_bridge_formats_preview_only_run_local_command() -> None:
    bridge = MacOSHotkeyBridgeCommand(
        duration=1.5,
        recorder="macos",
        adapter="faster-whisper",
        language="en",
        base_url="http://127.0.0.1:8000",
        session_id="fn-preview",
    )

    argv = bridge.argv()

    assert argv[:3] == ["jarvis", "voice", "run-local"]
    assert "--duration" in argv
    assert "--recorder" in argv
    assert "--adapter" in argv
    assert "--base-url" in argv
    assert "--session-id" in argv
    assert "--approve-dispatch" not in argv
    assert "--speak-result" not in argv


def test_macos_hotkey_bridge_hammerspoon_example_is_disabled() -> None:
    snippet = MacOSHotkeyBridgeCommand(adapter="faster-whisper").hammerspoon_snippet()

    assert "local enable_openjarvis_voice_hotkey = false" in snippet
    assert "hs.hotkey.bind" in snippet
    assert "jarvis voice run-local" in snippet
    assert "--adapter faster-whisper" in snippet
    assert "--approve-dispatch" not in snippet
    assert "--speak-result" not in snippet


def test_disabled_macos_hotkey_bridge_does_not_start_capture() -> None:
    bridge = DisabledMacOSHotkeyBridge()

    with pytest.raises(NotImplementedError, match="disabled by default"):
        bridge.start()
