"""Tests for the hotkeys placeholder module."""

from __future__ import annotations

import pytest

from openjarvis.hotkeys import FnKeyPushToTalkListener, HotkeyListener


def test_fn_listener_is_hotkey_listener():
    assert issubclass(FnKeyPushToTalkListener, HotkeyListener)


def test_fn_listener_start_raises():
    listener = FnKeyPushToTalkListener()
    with pytest.raises(NotImplementedError):
        listener.start()


def test_fn_listener_stop_and_callbacks_are_noops():
    listener = FnKeyPushToTalkListener()
    listener.stop()
    listener.on_press()
    listener.on_release()
