"""In-memory state for global voice hotkey activation."""

from __future__ import annotations

from threading import RLock

from openjarvis.hotkeys.models import HotkeyBinding, HotkeyTriggerEvent


class HotkeyStateStore:
    """Small synchronized state holder for the hotkey service."""

    def __init__(self, *, binding: HotkeyBinding | None = None) -> None:
        self._lock = RLock()
        self._enabled = False
        self._active = False
        self._binding = binding or HotkeyBinding()
        self._last_trigger: HotkeyTriggerEvent | None = None

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def binding(self) -> HotkeyBinding:
        with self._lock:
            return self._binding

    @property
    def last_trigger(self) -> HotkeyTriggerEvent | None:
        with self._lock:
            return self._last_trigger

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled
            if not enabled:
                self._active = False

    def set_binding(self, binding: HotkeyBinding) -> None:
        with self._lock:
            self._binding = binding

    def mark_active(self, active: bool) -> None:
        with self._lock:
            self._active = active

    def record_trigger(self, event: HotkeyTriggerEvent) -> None:
        with self._lock:
            self._last_trigger = event


__all__ = ["HotkeyStateStore"]
