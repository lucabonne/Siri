"""Global voice trigger service for explicit hold-to-talk activation."""

from __future__ import annotations

import time
from typing import Any

from openjarvis.core.config import JarvisConfig
from openjarvis.hotkeys.listener import GlobalHotkeyListener
from openjarvis.hotkeys.models import (
    HotkeyBinding,
    HotkeyPermissionError,
    HotkeyStatus,
    HotkeyTriggerEvent,
)
from openjarvis.hotkeys.permissions import HotkeyPermissionGate
from openjarvis.hotkeys.state import HotkeyStateStore


class GlobalVoiceHotkeyService:
    """Coordinate explicit system-level hotkeys with voice PTT capture."""

    def __init__(
        self,
        *,
        config: JarvisConfig | None = None,
        voice_service: Any = None,
        tts_service: Any = None,
        permission_middleware: Any = None,
        mode_registry: Any = None,
        desktop_service: Any = None,
        listener: Any = None,
        state_store: HotkeyStateStore | None = None,
    ) -> None:
        self._config = config or JarvisConfig()
        self._voice_service = voice_service
        self._tts_service = tts_service
        self._mode_registry = mode_registry
        self._desktop_service = desktop_service
        if permission_middleware is None:
            from openjarvis.security.permissions import PermissionMiddleware

            permission_middleware = PermissionMiddleware(mode_registry=mode_registry)
        self._permission_gate = HotkeyPermissionGate(
            permission_middleware=permission_middleware
        )
        self._state = state_store or HotkeyStateStore(
            binding=HotkeyBinding.from_config(self._config)
        )
        self._listener = listener or GlobalHotkeyListener(
            binding=self._state.binding,
            on_press=self.handle_press,
            on_release=self.handle_release,
        )
        if bool(
            getattr(
                getattr(self._config, "speech", None),
                "global_voice_trigger_enabled",
                False,
            )
        ):
            self._state.set_enabled(True)

    def enable(
        self,
        *,
        binding: HotkeyBinding | None = None,
        explicit_approval: bool = True,
    ) -> dict[str, Any]:
        """Enable keyboard-level trigger listening, subject to mode policy."""
        next_binding = binding or self._state.binding
        active_mode = self._active_mode()
        self._permission_gate.check_enable(
            active_mode=active_mode,
            explicit_approval=explicit_approval,
            binding=next_binding.to_dict(),
        )
        self._state.set_binding(next_binding)
        self._listener.update_binding(next_binding)
        self._state.set_enabled(True)
        self._sync_listener_policy()
        return self.status()

    def disable(self) -> dict[str, Any]:
        """Disable the global listener and end any active hotkey capture."""
        if self._state.active:
            self.handle_release("disabled")
        self._state.set_enabled(False)
        self._listener.stop()
        return self.status()

    def current_binding(self) -> dict[str, Any]:
        return self._state.binding.to_dict()

    def status(self) -> dict[str, Any]:
        self._sync_listener_policy()
        active_mode = self._active_mode()
        privacy_mode = getattr(active_mode, "id", "") == "privacy"
        status = HotkeyStatus(
            enabled=self._state.enabled,
            effective_enabled=self._state.enabled and not privacy_mode,
            listener_running=bool(getattr(self._listener, "running", False)),
            active=self._state.active,
            binding=self._state.binding,
            privacy_mode=privacy_mode,
            approval_required=privacy_mode,
            last_trigger=self._state.last_trigger,
            voice_status=self._voice_status(),
            tts_status=self._tts_status(),
            desktop_status=self._desktop_status(privacy_mode=privacy_mode),
        )
        return status.to_dict()

    def test_trigger(self, *, explicit_approval: bool = True) -> dict[str, Any]:
        """Record a dry test trigger without opening the microphone."""
        active_mode = self._active_mode()
        self._permission_gate.check_trigger(
            active_mode=active_mode,
            explicit_approval=explicit_approval,
            binding=self._state.binding.to_dict(),
            test=True,
        )
        event = HotkeyTriggerEvent(
            source="test_trigger",
            phase="tested",
            binding=self._state.binding.display_name,
            timestamp=time.time(),
            test=True,
            active=False,
        )
        self._state.record_trigger(event)
        return {"status": self.status(), "trigger": event.to_dict()}

    def handle_press(self, binding_label: str = "") -> None:
        """Start voice capture for a matching hotkey press."""
        if not self.status()["effective_enabled"] or self._state.active:
            return
        binding = binding_label or self._state.binding.display_name
        try:
            self._permission_gate.check_trigger(
                active_mode=self._active_mode(),
                explicit_approval=True,
                binding=self._state.binding.to_dict(),
            )
            self._voice().start_recording(
                explicit_approval=True,
                agent_id=self._active_agent_id(),
            )
        except Exception as exc:
            event = HotkeyTriggerEvent(
                source="global_hotkey",
                phase="press",
                binding=binding,
                timestamp=time.time(),
                blocked=True,
                reason=str(exc),
            )
            self._state.record_trigger(event)
            if isinstance(exc, HotkeyPermissionError):
                return
            return
        self._state.mark_active(True)
        self._state.record_trigger(
            HotkeyTriggerEvent(
                source="global_hotkey",
                phase="press",
                binding=binding,
                timestamp=time.time(),
                active=True,
            )
        )

    def handle_release(self, binding_label: str = "") -> None:
        """Stop voice capture for a matching hotkey release."""
        if not self._state.active:
            return
        binding = binding_label or self._state.binding.display_name
        try:
            self._voice().stop_recording()
        except Exception as exc:
            self._state.record_trigger(
                HotkeyTriggerEvent(
                    source="global_hotkey",
                    phase="release",
                    binding=binding,
                    timestamp=time.time(),
                    blocked=True,
                    reason=str(exc),
                )
            )
        finally:
            self._state.mark_active(False)
        self._state.record_trigger(
            HotkeyTriggerEvent(
                source="global_hotkey",
                phase="release",
                binding=binding,
                timestamp=time.time(),
                active=False,
            )
        )

    def _sync_listener_policy(self) -> None:
        privacy_mode = getattr(self._active_mode(), "id", "") == "privacy"
        if not self._state.enabled or privacy_mode:
            if getattr(self._listener, "running", False):
                self._listener.stop()
            return
        if not getattr(self._listener, "running", False):
            try:
                self._listener.start()
            except Exception as exc:
                self._state.record_trigger(
                    HotkeyTriggerEvent(
                        source="global_hotkey",
                        phase="listener_unavailable",
                        binding=self._state.binding.display_name,
                        timestamp=time.time(),
                        blocked=True,
                        reason=str(exc),
                    )
                )

    def _voice(self) -> Any:
        if self._voice_service is None:
            from openjarvis.voice import VoicePushToTalkService

            self._voice_service = VoicePushToTalkService(
                config=self._config,
                mode_registry=self._mode_registry,
            )
        return self._voice_service

    def _active_mode(self) -> Any:
        if self._mode_registry is None:
            return None
        try:
            return self._mode_registry.get_active_mode().mode
        except Exception:
            return None

    def _active_agent_id(self) -> str:
        voice_status = self._voice_status()
        return str(voice_status.get("active_agent_id", ""))

    def _voice_status(self) -> dict[str, Any]:
        try:
            return dict(self._voice().status())
        except Exception:
            return {}

    def _tts_status(self) -> dict[str, Any]:
        if self._tts_service is None:
            return {}
        try:
            return dict(self._tts_service.status())
        except Exception:
            return {}

    def _desktop_status(self, *, privacy_mode: bool) -> dict[str, Any]:
        if self._desktop_service is None:
            return {}
        try:
            status = self._desktop_service.status(privacy_mode=privacy_mode)
            return status.to_dict() if hasattr(status, "to_dict") else dict(status)
        except Exception:
            return {}


__all__ = ["GlobalVoiceHotkeyService"]
