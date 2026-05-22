"""Keyboard listener adapter for explicit hold-to-talk activation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openjarvis.hotkeys.models import HotkeyBinding, HotkeyListenerUnavailableError

KeyCallback = Callable[[str], None]


class GlobalHotkeyListener:
    """Optional global keyboard listener.

    The listener watches key state only. It never opens the microphone and never
    transcribes audio; the service starts capture only after a matching press.
    """

    def __init__(
        self,
        *,
        binding: HotkeyBinding,
        on_press: KeyCallback,
        on_release: KeyCallback,
    ) -> None:
        self._binding = binding
        self._on_press_callback = on_press
        self._on_release_callback = on_release
        self._pressed: set[str] = set()
        self._matched = False
        self._listener: Any = None

    @property
    def running(self) -> bool:
        return self._listener is not None

    def start(self) -> None:
        if self._listener is not None:
            return
        try:
            from pynput import keyboard  # type: ignore
        except Exception as exc:  # pragma: no cover - environment dependent
            raise HotkeyListenerUnavailableError(
                "global hotkey listener backend is unavailable"
            ) from exc

        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        self._pressed.clear()
        self._matched = False
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def update_binding(self, binding: HotkeyBinding) -> None:
        self._binding = binding
        self._pressed.clear()
        self._matched = False

    def _handle_press(self, key: Any) -> None:
        normalized = normalize_key(key)
        if not normalized:
            return
        self._pressed.add(normalized)
        if not self._matched and self._binding.matches(self._pressed):
            self._matched = True
            self._on_press_callback(
                self._binding.matched_display_name(self._pressed)
            )

    def _handle_release(self, key: Any) -> None:
        normalized = normalize_key(key)
        if normalized in self._pressed:
            self._pressed.remove(normalized)
        if self._matched and not self._binding.matches(self._pressed):
            self._matched = False
            self._on_release_callback(self._binding.display_name)


class NullHotkeyListener:
    """No-op listener used in tests and when global capture is unavailable."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def update_binding(self, binding: HotkeyBinding) -> None:
        return None


def normalize_key(key: Any) -> str:
    """Normalize pynput key objects and test strings to binding keys."""
    if isinstance(key, str):
        raw = key
    else:
        raw = getattr(key, "char", None) or getattr(key, "name", None) or str(key)
    raw = str(raw).lower().replace("key.", "").strip("'")
    aliases = {
        "ctrl_l": "ctrl",
        "ctrl_r": "ctrl",
        "control": "ctrl",
        "cmd_l": "cmd",
        "cmd_r": "cmd",
        "command": "cmd",
        "alt_l": "alt",
        "alt_r": "alt",
        "option": "alt",
        "space": "space",
        "fn": "fn",
    }
    return aliases.get(raw, raw)


__all__ = ["GlobalHotkeyListener", "NullHotkeyListener", "normalize_key"]
