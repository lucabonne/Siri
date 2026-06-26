"""Disabled macOS hotkey bridge helpers for future push-to-talk integration."""

from __future__ import annotations

import ast
import re
import shlex
from dataclasses import dataclass

HAMMERSPOON_MIN_DURATION_SECONDS = 0.1
HAMMERSPOON_MAX_DURATION_SECONDS = 30.0
HAMMERSPOON_RECORDER_KINDS = ("macos", "sounddevice")


@dataclass(frozen=True)
class HammerspoonBridgeValidation:
    """Static validation result for a generated Hammerspoon bridge file."""

    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def _strip_lua_comments(content: str) -> str:
    """Remove Lua comments while preserving quoted string contents."""
    output: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(content):
        char = content[index]
        if quote is not None:
            output.append(char)
            if char == "\\" and index + 1 < len(content):
                index += 1
                output.append(content[index])
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            output.append(char)
            index += 1
            continue
        if content.startswith("--[[", index):
            end = content.find("]]", index + 4)
            comment = content[index:] if end < 0 else content[index : end + 2]
            output.extend("\n" for char in comment if char == "\n")
            index = len(content) if end < 0 else end + 2
            continue
        if content.startswith("--", index):
            end = content.find("\n", index + 2)
            if end < 0:
                break
            output.append("\n")
            index = end + 1
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _strip_disabled_hotkey_guard(content: str) -> str:
    return re.sub(
        r"(?ms)^\s*if\s+enable_openjarvis_voice_hotkey\s+then\b.*?^\s*end\s*$",
        "",
        content,
        count=1,
    )


def _command_option(argv: list[str], option: str) -> str | None:
    positions = [index for index, value in enumerate(argv) if value == option]
    if len(positions) != 1:
        return None
    position = positions[0]
    if position + 1 >= len(argv):
        return None
    return argv[position + 1]


def validate_hammerspoon_bridge(content: str) -> HammerspoonBridgeValidation:
    """Validate bridge Lua as text without evaluating Lua or running commands."""
    active = _strip_lua_comments(content)
    errors: list[str] = []

    enable_values = re.findall(
        r"\blocal\s+enable_openjarvis_voice_hotkey\s*=\s*(true|false)\b", active
    )
    if enable_values != ["false"]:
        errors.append("hotkey capture is not explicitly disabled by default")

    for unsafe_flag in ("--approve-dispatch", "--speak-result"):
        if unsafe_flag in active:
            errors.append(f"active content contains unsafe {unsafe_flag}")

    active_lower = active.lower()
    if ".hammerspoon/init.lua" in active_lower:
        errors.append("active content references the Hammerspoon install path")
    if any(
        marker in active_lower
        for marker in ("launchagents", "launchagent", "launchctl", "hs.plist")
    ):
        errors.append("active content references LaunchAgent creation")

    active_outside_disabled_guard = _strip_disabled_hotkey_guard(active).lower()
    immediate_execution_markers = (
        "os.execute",
        "io.popen",
        "hs.execute",
        "hs.task.new",
        ":start(",
        "dofile(",
        "loadfile(",
        "require(",
    )
    if any(
        marker in active_outside_disabled_guard
        for marker in immediate_execution_markers
    ):
        errors.append(
            "active content outside the disabled hotkey guard contains "
            "execution or loading markers"
        )

    command_matches = list(
        re.finditer(
            r"\blocal\s+openjarvis_voice_command\s*=\s*"
            r"(?P<literal>'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")",
            active,
        )
    )
    argv: list[str] | None = None
    if len(command_matches) != 1:
        errors.append("exactly one active preview command is required")
    else:
        try:
            command = ast.literal_eval(command_matches[0].group("literal"))
            argv = shlex.split(command)
        except (SyntaxError, ValueError):
            errors.append("active preview command is not a supported literal")

    if argv is not None:
        if len(argv) < 3 or argv[1:3] != ["voice", "mic-run"]:
            errors.append("active command must use jarvis voice mic-run")

        duration_value = _command_option(argv, "--duration")
        if duration_value is None:
            errors.append("active mic-run command requires exactly one duration")
        else:
            try:
                duration = float(duration_value)
            except ValueError:
                errors.append("active mic-run duration must be numeric")
            else:
                if not (
                    HAMMERSPOON_MIN_DURATION_SECONDS
                    <= duration
                    <= HAMMERSPOON_MAX_DURATION_SECONDS
                ):
                    errors.append("active mic-run duration must be between 0.1 and 30")

        recorder = _command_option(argv, "--recorder")
        if recorder not in HAMMERSPOON_RECORDER_KINDS:
            errors.append(
                "active mic-run command requires recorder macos or sounddevice"
            )

    return HammerspoonBridgeValidation(errors=tuple(errors))


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
        dispatch_command = f"{command} --approve-dispatch"
        speech_command = f"{dispatch_command} --speak-result"
        return f"""-- OpenJarvis voice hotkey bridge example.
-- Preview-only and disabled by default. This example does not request macOS
-- permissions; review them manually before enabling an external helper.
local enable_openjarvis_voice_hotkey = false
local openjarvis_voice_command = {command!r}

-- Manual opt-in examples only. Keep these commented unless you explicitly
-- want approved dispatch or approved dispatch followed by result speech.
-- local openjarvis_voice_command = {dispatch_command!r}
-- local openjarvis_voice_command = {speech_command!r}

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


__all__ = [
    "DisabledMacOSHotkeyBridge",
    "HammerspoonBridgeValidation",
    "MacOSHotkeyBridgeCommand",
    "validate_hammerspoon_bridge",
]
