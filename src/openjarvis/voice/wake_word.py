"""Wake word detection service."""

from __future__ import annotations

import logging
from typing import Any

from openjarvis.core.config import JarvisConfig
from openjarvis.voice.permissions import VoicePermissionError

logger = logging.getLogger(__name__)


class WakeWordService:
    """Coordinate local-only wake word detection."""

    def __init__(
        self,
        *,
        config: JarvisConfig | None = None,
        voice_service: Any = None,
        mode_registry: Any = None,
        permission_middleware: Any = None,
    ) -> None:
        self._config = config or JarvisConfig()
        self._voice_service = voice_service
        self._mode_registry = mode_registry
        self._permission_middleware = permission_middleware
        self._enabled = False

    def _active_mode(self) -> Any:
        if self._mode_registry is None:
            return type("Mode", (), {"id": "default"})()
        try:
            return self._mode_registry.get_active_mode().mode
        except Exception:
            return type("Mode", (), {"id": "default"})()

    def _is_privacy_mode(self) -> bool:
        return getattr(self._active_mode(), "id", "") == "privacy"

    def status(self) -> dict[str, Any]:
        """Return the current status of the wake word service."""
        privacy_mode = self._is_privacy_mode()
        # Ensure it is disabled in privacy mode
        if privacy_mode and self._enabled:
            self._enabled = False

        return {
            "enabled": self._enabled,
            "privacy_mode": privacy_mode,
            "local_only": True,
            "cloud_audio": False,
        }

    def enable(self, *, explicit_approval: bool = False) -> dict[str, Any]:
        """Enable wake word detection."""
        if self._is_privacy_mode():
            raise VoicePermissionError(
                "Wake word detection is disabled in Privacy Mode."
            )

        if not explicit_approval:
            raise VoicePermissionError(
                "Explicit approval required to enable wake word."
            )

        self._enabled = True
        return self.status()

    def disable(self) -> dict[str, Any]:
        """Disable wake word detection."""
        self._enabled = False
        return self.status()

    def test_trigger(self, *, explicit_approval: bool = False) -> dict[str, Any]:
        """Simulate a wake word detection and start recording."""
        if not self._enabled:
            raise VoicePermissionError("Wake word detection is not enabled.")

        if self._is_privacy_mode():
            raise VoicePermissionError(
                "Wake word detection is disabled in Privacy Mode."
            )

        if self._voice_service is None:
            raise RuntimeError("Voice service is not connected.")

        # Trigger the voice service to start recording
        try:
            session = self._voice_service.start_recording(
                explicit_approval=explicit_approval,
            )
            return {
                "status": "triggered",
                "session": (
                    session.to_dict() if hasattr(session, "to_dict") else str(session)
                ),
            }
        except Exception as e:
            logger.error("Failed to trigger voice recording from wake word: %s", e)
            raise
