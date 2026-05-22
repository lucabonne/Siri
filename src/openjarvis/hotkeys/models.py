"""Models for explicit global voice hotkey activation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class HotkeyError(RuntimeError):
    """Base error for global hotkey failures."""


class HotkeyPermissionError(HotkeyError):
    """Raised when a hotkey action is blocked by policy."""


class HotkeyListenerUnavailableError(HotkeyError):
    """Raised when the platform listener cannot be started."""


@dataclass(slots=True)
class HotkeyBinding:
    """A hold-style binding for explicit voice activation."""

    kind: str = "fn_hold"
    keys: list[str] = field(default_factory=lambda: ["fn"])
    fallback_keys: list[str] = field(default_factory=lambda: ["ctrl", "space"])
    display_name: str = "Fn hold"
    fallback_display_name: str = "Ctrl+Space"

    @classmethod
    def from_config(cls, config: Any = None) -> "HotkeyBinding":
        speech = getattr(config, "speech", None)
        binding = str(getattr(speech, "global_voice_trigger_binding", "fn")).strip()
        fallback = str(
            getattr(speech, "global_voice_trigger_fallback", "ctrl+space")
        ).strip()
        keys = _split_keys(binding or "fn")
        fallback_keys = _split_keys(fallback or "ctrl+space")
        return cls(
            kind="fn_hold" if keys == ["fn"] else "hotkey_hold",
            keys=keys,
            fallback_keys=fallback_keys,
            display_name=_display(keys),
            fallback_display_name=_display(fallback_keys),
        )

    def matches(self, pressed_keys: set[str]) -> bool:
        return _matches(self.keys, pressed_keys) or _matches(
            self.fallback_keys,
            pressed_keys,
        )

    def matched_display_name(self, pressed_keys: set[str]) -> str:
        if _matches(self.keys, pressed_keys):
            return self.display_name
        if _matches(self.fallback_keys, pressed_keys):
            return self.fallback_display_name
        return ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HotkeyTriggerEvent:
    """Metadata for the latest trigger event."""

    source: str
    phase: str
    binding: str
    timestamp: float
    active: bool = False
    approved: bool = True
    test: bool = False
    blocked: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HotkeyStatus:
    """Mission Control status for the global trigger."""

    enabled: bool
    effective_enabled: bool
    listener_running: bool
    active: bool
    binding: HotkeyBinding
    privacy_mode: bool
    approval_required: bool
    last_trigger: HotkeyTriggerEvent | None = None
    voice_status: dict[str, Any] = field(default_factory=dict)
    tts_status: dict[str, Any] = field(default_factory=dict)
    desktop_status: dict[str, Any] = field(default_factory=dict)
    push_to_talk_only: bool = True
    wake_word_enabled: bool = False
    background_transcription: bool = False
    always_listening: bool = False
    autonomous_speech: bool = False
    local_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["binding"] = self.binding.to_dict()
        data["last_trigger"] = (
            self.last_trigger.to_dict() if self.last_trigger is not None else None
        )
        return data


def _split_keys(value: str) -> list[str]:
    keys = [
        part.strip().lower().replace("control", "ctrl")
        for part in value.replace("-", "+").split("+")
        if part.strip()
    ]
    return keys or ["fn"]


def _matches(expected: list[str], pressed: set[str]) -> bool:
    return bool(expected) and all(key in pressed for key in expected)


def _display(keys: list[str]) -> str:
    labels = {"ctrl": "Ctrl", "cmd": "Cmd", "alt": "Option", "fn": "Fn"}
    return "+".join(labels.get(key, key.title()) for key in keys)


__all__ = [
    "HotkeyBinding",
    "HotkeyError",
    "HotkeyListenerUnavailableError",
    "HotkeyPermissionError",
    "HotkeyStatus",
    "HotkeyTriggerEvent",
]
