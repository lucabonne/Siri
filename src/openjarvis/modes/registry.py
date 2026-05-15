"""Central registry and local state persistence for Siri operating modes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from openjarvis.modes.defaults import DEFAULT_ACTIVE_MODE_ID, DEFAULT_MODE_CONFIGS
from openjarvis.modes.models import ActiveModeState, ModeConfig


def default_mode_state_path() -> Path:
    return Path.home() / ".openjarvis" / "state" / "current_mode.json"


class ModeRegistry:
    """Configuration-backed registry for global Siri operating modes."""

    def __init__(
        self,
        configs: Iterable[dict[str, Any] | ModeConfig] | None = None,
        *,
        active_mode_id: str = DEFAULT_ACTIVE_MODE_ID,
        state_path: str | Path | None = None,
        persist: bool = True,
    ) -> None:
        source = configs if configs is not None else DEFAULT_MODE_CONFIGS
        modes: dict[str, ModeConfig] = {}
        for item in source:
            config = (
                item
                if isinstance(item, ModeConfig)
                else ModeConfig.from_mapping(item)
            )
            if config.id in modes:
                raise ValueError(f"duplicate mode id: {config.id}")
            modes[config.id] = config
        if not modes:
            raise ValueError("mode registry requires at least one mode")

        self._modes = modes
        self._state_path = (
            Path(state_path).expanduser()
            if state_path is not None
            else default_mode_state_path()
        )
        self._persist = persist
        saved_mode_id = self._read_saved_mode_id() if persist else ""
        resolved = saved_mode_id or active_mode_id
        self._active_mode_id = resolved if resolved in modes else DEFAULT_ACTIVE_MODE_ID
        if self._active_mode_id not in modes:
            self._active_mode_id = next(iter(modes))

    @property
    def state_path(self) -> Path:
        return self._state_path

    def list_modes(self) -> list[ModeConfig]:
        return sorted(self._modes.values(), key=lambda mode: mode.id.lower())

    def get_mode(self, mode_id: str) -> ModeConfig:
        try:
            return self._modes[mode_id]
        except KeyError as exc:
            raise KeyError(f"unknown mode: {mode_id}") from exc

    def get_active_mode(self) -> ActiveModeState:
        mode = self.get_mode(self._active_mode_id)
        return ActiveModeState(active_mode_id=mode.id, mode=mode)

    def switch_mode(self, mode_id: str) -> ActiveModeState:
        mode = self.get_mode(mode_id)
        self._active_mode_id = mode.id
        if self._persist:
            self._write_state(mode)
        return self.get_active_mode()

    def preferred_agents_for_active_mode(self) -> list[str]:
        return list(self.get_active_mode().mode.preferred_agents)

    def cloud_apis_allowed(self) -> bool:
        return not self.get_active_mode().mode.cloud_apis_disabled

    def remote_mcp_allowed(self) -> bool:
        return not self.get_active_mode().mode.remote_mcp_disabled

    def outbound_network_requires_localhost(self) -> bool:
        return self.get_active_mode().mode.localhost_only_network

    def _read_saved_mode_id(self) -> str:
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        return str(data.get("active_mode_id", "")).strip()

    def _write_state(self, mode: ModeConfig) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "active_mode_id": mode.id,
            "mode": {
                "id": mode.id,
                "display_name": mode.display_name,
            },
        }
        self._state_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


__all__ = ["ModeRegistry", "default_mode_state_path"]
