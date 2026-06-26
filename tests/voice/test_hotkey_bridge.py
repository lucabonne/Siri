"""Tests for the disabled macOS hotkey bridge boundary."""

from __future__ import annotations

import pytest

from openjarvis.hotkeys.macos_bridge import (
    DisabledMacOSHotkeyBridge,
    MacOSHotkeyBridgeCommand,
    validate_hammerspoon_bridge,
)


def test_macos_hotkey_bridge_formats_preview_only_mic_run_command() -> None:
    bridge = MacOSHotkeyBridgeCommand(
        duration=1.5,
        recorder="macos",
        adapter="faster-whisper",
        language="en",
        base_url="http://127.0.0.1:8000",
        session_id="fn-preview",
    )

    argv = bridge.argv()

    assert argv[:3] == ["jarvis", "voice", "mic-run"]
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
    assert "jarvis voice mic-run" in snippet
    assert "--adapter faster-whisper" in snippet
    active_command = next(
        line
        for line in snippet.splitlines()
        if line.startswith("local openjarvis_voice_command =")
    )
    assert "--approve-dispatch" not in active_command
    assert "--speak-result" not in active_command
    assert "-- local openjarvis_voice_command" in snippet
    assert "--approve-dispatch" in snippet
    assert "--speak-result" in snippet
    assert validate_hammerspoon_bridge(snippet).valid is True


@pytest.mark.parametrize(
    ("active_line", "expected_error"),
    [
        (
            "local install_path = '~/.hammerspoon/init.lua'",
            "Hammerspoon install path",
        ),
        (
            "local launch_agent = '~/Library/LaunchAgents/openjarvis.plist'",
            "LaunchAgent creation",
        ),
    ],
)
def test_hammerspoon_validation_rejects_install_mutation_markers(
    active_line: str, expected_error: str
) -> None:
    snippet = MacOSHotkeyBridgeCommand().hammerspoon_snippet() + active_line

    result = validate_hammerspoon_bridge(snippet)

    assert result.valid is False
    assert any(expected_error in error for error in result.errors)


def test_disabled_macos_hotkey_bridge_does_not_start_capture() -> None:
    bridge = DisabledMacOSHotkeyBridge()

    with pytest.raises(NotImplementedError, match="disabled by default"):
        bridge.start()
