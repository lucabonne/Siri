"""Disabled macOS hotkey bridge helpers for future push-to-talk integration."""

from __future__ import annotations

import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class MacOSHotkeyBridgeCommand:
    """Formats the safe CLI command an external macOS hotkey tool may call."""

    jarvis_bin: str = "jarvis"
    duration: float = 2.0
    recorder: str = "macos"
    input_device: str = ":0"
    adapter: str | None = None
    language: str | None = None
    base_url: str | None = None
    session_id: str | None = None

    def argv(self) -> list[str]:
        command = [
            self.jarvis_bin,
            "voice",
            "mic-run",
            "--duration",
            f"{self.duration:g}",
            "--recorder",
            self.recorder,
            "--input-device",
            self.input_device,
        ]
        if self.adapter:
            command.extend(["--adapter", self.adapter])
        if self.language:
            command.extend(["--language", self.language])
        if self.base_url:
            command.extend(["--base-url", self.base_url])
        if self.session_id:
            command.extend(["--session-id", self.session_id])
        return command

    def shell_command(self) -> str:
        return shlex.join(self.argv())

    def hammerspoon_snippet(self) -> str:
        command = self.shell_command()
        return f"""-- OpenJarvis voice hotkey bridge example.
-- Preview-only and disabled by default. This example does not request macOS
-- permissions; review them manually before enabling an external helper.
local enable_openjarvis_voice_hotkey = false
local openjarvis_voice_command = {command!r}

if enable_openjarvis_voice_hotkey then
  hs.hotkey.bind({{}}, "F18", function()
    hs.task.new("/bin/zsh", nil, {{"-lc", openjarvis_voice_command}}):start()
  end)
end
"""


class DisabledMacOSHotkeyBridge:
    """Non-listening adapter boundary for future macOS Fn/push-to-talk work."""

    def __init__(self, command: MacOSHotkeyBridgeCommand | None = None) -> None:
        self.command = command or MacOSHotkeyBridgeCommand()

    def start(self) -> None:
        raise NotImplementedError(
            "macOS hotkey capture is disabled by default; use the formatted "
            "bridge command with an explicitly enabled external helper."
        )


__all__ = ["DisabledMacOSHotkeyBridge", "MacOSHotkeyBridgeCommand"]
