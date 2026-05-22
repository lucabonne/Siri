"""Explicit push-to-talk session state machine.

States
------
idle              No session active.
listening         PTT key held; recorder is capturing audio (deferred).
transcribing      Audio captured; local transcription running (deferred).
awaiting_approval Transcript ready; waiting for explicit user approval.
dispatching       Approved transcript is being sent to the orchestrator.
completed         Orchestrator accepted the transcript.
failed            Any unrecoverable error in the above states.

Valid transitions
-----------------
idle              → listening        (PTT key pressed / /start called)
listening         → transcribing     (PTT key released / /stop + /transcribe-latest)
listening         → failed           (recorder error)
transcribing      → awaiting_approval (transcript ready)
transcribing      → failed           (transcription error)
awaiting_approval → dispatching      (user approves / /dispatch approved=true)
awaiting_approval → idle             (user cancels)
dispatching       → completed        (AgentSendTool success)
dispatching       → failed           (AgentSendTool error)
completed         → idle             (session reset)
failed            → idle             (session reset)

Deferred: the actual transitions from idle→listening and listening→transcribing
are not wired to real audio capture yet.  The FSM is used by the API layer to
validate and surface state without requiring a live microphone.
"""

from __future__ import annotations

from enum import Enum


class VoiceSessionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    AWAITING_APPROVAL = "awaiting_approval"
    DISPATCHING = "dispatching"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[VoiceSessionState, frozenset[VoiceSessionState]] = {
    VoiceSessionState.IDLE: frozenset({VoiceSessionState.LISTENING}),
    VoiceSessionState.LISTENING: frozenset(
        {VoiceSessionState.TRANSCRIBING, VoiceSessionState.FAILED}
    ),
    VoiceSessionState.TRANSCRIBING: frozenset(
        {VoiceSessionState.AWAITING_APPROVAL, VoiceSessionState.FAILED}
    ),
    VoiceSessionState.AWAITING_APPROVAL: frozenset(
        {VoiceSessionState.DISPATCHING, VoiceSessionState.IDLE}
    ),
    VoiceSessionState.DISPATCHING: frozenset(
        {VoiceSessionState.COMPLETED, VoiceSessionState.FAILED}
    ),
    VoiceSessionState.COMPLETED: frozenset({VoiceSessionState.IDLE}),
    VoiceSessionState.FAILED: frozenset({VoiceSessionState.IDLE}),
}


class VoiceSessionFSMError(RuntimeError):
    """Raised when an invalid state transition is attempted."""


class VoiceSessionFSM:
    """Lightweight state machine for a single PTT voice session.

    Not thread-safe; callers are expected to use a single async task or hold
    an external lock when sharing across coroutines.
    """

    def __init__(self, initial: VoiceSessionState = VoiceSessionState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> VoiceSessionState:
        return self._state

    def transition(self, target: VoiceSessionState) -> VoiceSessionState:
        """Move to *target* and return the new state, or raise."""
        allowed = _VALID_TRANSITIONS.get(self._state, frozenset())
        if target not in allowed:
            raise VoiceSessionFSMError(
                f"invalid transition {self._state.value!r} → {target.value!r}; "
                f"allowed: {sorted(s.value for s in allowed)}"
            )
        self._state = target
        return self._state

    def can_transition(self, target: VoiceSessionState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def reset(self) -> None:
        """Force back to idle without validation (use for error recovery)."""
        self._state = VoiceSessionState.IDLE


__all__ = ["VoiceSessionFSM", "VoiceSessionFSMError", "VoiceSessionState"]
