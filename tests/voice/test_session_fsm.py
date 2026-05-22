"""Tests for the VoiceSessionFSM state machine."""

from __future__ import annotations

import pytest

from openjarvis.voice.session_fsm import (
    VoiceSessionFSM,
    VoiceSessionFSMError,
    VoiceSessionState,
)

S = VoiceSessionState


def test_initial_state_is_idle():
    fsm = VoiceSessionFSM()
    assert fsm.state is S.IDLE


def test_idle_to_listening():
    fsm = VoiceSessionFSM()
    fsm.transition(S.LISTENING)
    assert fsm.state is S.LISTENING


def test_full_happy_path():
    fsm = VoiceSessionFSM()
    for target in (
        S.LISTENING,
        S.TRANSCRIBING,
        S.AWAITING_APPROVAL,
        S.DISPATCHING,
        S.COMPLETED,
        S.IDLE,
    ):
        fsm.transition(target)
    assert fsm.state is S.IDLE


def test_cancel_from_awaiting_approval_goes_to_idle():
    fsm = VoiceSessionFSM()
    fsm.transition(S.LISTENING)
    fsm.transition(S.TRANSCRIBING)
    fsm.transition(S.AWAITING_APPROVAL)
    fsm.transition(S.IDLE)
    assert fsm.state is S.IDLE


def test_error_path_from_listening():
    fsm = VoiceSessionFSM()
    fsm.transition(S.LISTENING)
    fsm.transition(S.FAILED)
    assert fsm.state is S.FAILED
    fsm.transition(S.IDLE)
    assert fsm.state is S.IDLE


def test_invalid_transition_raises():
    fsm = VoiceSessionFSM()
    with pytest.raises(VoiceSessionFSMError):
        fsm.transition(S.COMPLETED)


def test_idle_cannot_skip_to_transcribing():
    fsm = VoiceSessionFSM()
    with pytest.raises(VoiceSessionFSMError):
        fsm.transition(S.TRANSCRIBING)


def test_dispatching_cannot_go_to_listening():
    fsm = VoiceSessionFSM()
    fsm.transition(S.LISTENING)
    fsm.transition(S.TRANSCRIBING)
    fsm.transition(S.AWAITING_APPROVAL)
    fsm.transition(S.DISPATCHING)
    with pytest.raises(VoiceSessionFSMError):
        fsm.transition(S.LISTENING)


def test_can_transition_returns_bool():
    fsm = VoiceSessionFSM()
    assert fsm.can_transition(S.LISTENING) is True
    assert fsm.can_transition(S.COMPLETED) is False


def test_reset_returns_to_idle_from_any_state():
    fsm = VoiceSessionFSM()
    fsm.transition(S.LISTENING)
    fsm.transition(S.TRANSCRIBING)
    fsm.reset()
    assert fsm.state is S.IDLE


def test_state_values_are_strings():
    for s in VoiceSessionState:
        assert isinstance(s.value, str)
