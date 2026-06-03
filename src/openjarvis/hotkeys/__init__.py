"""Hotkey listener stubs for future push-to-talk activation.

Phase 1 — interface only. Actual macOS Fn / CGEvent listener is deferred.
Phase 4 adds ``jarvis voice submit`` as the typed/mock transcript bridge that
future Hammerspoon/Fn automation can call after it obtains a transcript.
Phase 11 adds a disabled macOS bridge formatter that can show the
``jarvis voice run-local`` command an explicitly enabled helper may call later.

Intended flow when implemented:
    Fn key down  → FnKeyPushToTalkListener.on_press()
                     → POST /v1/voice/ptt/start
    Fn key up    → FnKeyPushToTalkListener.on_release()
                     → POST /v1/voice/ptt/stop
                     → POST /v1/voice/ptt/transcribe-latest
                     → POST /v1/voice/ptt/dispatch

Typed/mock bridge available before recorder work:
    external transcript  → jarvis voice submit "..." [--approve-dispatch]
                         → POST /v1/voice/ptt/submit-transcript
                         → optional approved POST /v1/voice/ptt/dispatch

Deferred work:
- CGEventTap / pynput listener for macOS Fn key (requires Accessibility permission)
- Hammerspoon/Swift helper enablement for real hotkey capture
- Hotkey configuration (user-settable key combo)
- Cross-platform support
- Permission prompting on first launch
- Voice-only mode
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from openjarvis.hotkeys.macos_bridge import (
    DisabledMacOSHotkeyBridge,
    MacOSHotkeyBridgeCommand,
)


class HotkeyListener(ABC):
    """Abstract base for push-to-talk hotkey listeners."""

    @abstractmethod
    def start(self) -> None:
        """Begin listening for the configured hotkey."""

    @abstractmethod
    def stop(self) -> None:
        """Stop listening."""

    @abstractmethod
    def on_press(self) -> None:
        """Called when the hotkey is pressed."""

    @abstractmethod
    def on_release(self) -> None:
        """Called when the hotkey is released."""


class FnKeyPushToTalkListener(HotkeyListener):
    """Placeholder for the macOS Fn push-to-talk listener.

    Not yet implemented. Raises NotImplementedError on start().
    Exists so the rest of the codebase can import and type-hint against it.
    """

    def start(self) -> None:
        raise NotImplementedError(
            "FnKeyPushToTalkListener is not yet implemented. "
            "See openjarvis/hotkeys/__init__.py for the deferred work list."
        )

    def stop(self) -> None:
        pass

    def on_press(self) -> None:
        pass

    def on_release(self) -> None:
        pass


__all__ = [
    "DisabledMacOSHotkeyBridge",
    "FnKeyPushToTalkListener",
    "HotkeyListener",
    "MacOSHotkeyBridgeCommand",
]
