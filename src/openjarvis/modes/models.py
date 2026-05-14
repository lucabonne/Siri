"""Typed models for Siri operating modes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ModeConfig:
    """Configuration for one global Siri operating mode."""

    id: str
    display_name: str
    description: str
    verbosity_level: str
    proactive_level: str
    interruption_policy: str
    preferred_agents: list[str]
    memory_behavior: dict[str, Any] = field(default_factory=dict)
    privacy_network_policy: dict[str, Any] = field(default_factory=dict)
    default_model_overrides: dict[str, Any] = field(default_factory=dict)
    ui_theme_metadata: dict[str, Any] = field(default_factory=dict)
    notification_behavior: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ModeConfig":
        return cls(
            id=str(data["id"]),
            display_name=str(data["display_name"]),
            description=str(data["description"]),
            verbosity_level=str(data["verbosity_level"]),
            proactive_level=str(data["proactive_level"]),
            interruption_policy=str(data["interruption_policy"]),
            preferred_agents=list(data.get("preferred_agents", [])),
            memory_behavior=dict(data.get("memory_behavior", {})),
            privacy_network_policy=dict(data.get("privacy_network_policy", {})),
            default_model_overrides=dict(data.get("default_model_overrides", {})),
            ui_theme_metadata=dict(data.get("ui_theme_metadata", {})),
            notification_behavior=dict(data.get("notification_behavior", {})),
        )

    @property
    def cloud_apis_disabled(self) -> bool:
        return self.privacy_network_policy.get("cloud_apis") == "disabled"

    @property
    def remote_mcp_disabled(self) -> bool:
        return self.privacy_network_policy.get("remote_mcp") == "disabled"

    @property
    def localhost_only_network(self) -> bool:
        return self.privacy_network_policy.get("outbound_network") == "localhost_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ActiveModeState:
    """Current active mode response payload."""

    active_mode_id: str
    mode: ModeConfig

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_mode_id": self.active_mode_id,
            "mode": self.mode.to_dict(),
        }


__all__ = ["ActiveModeState", "ModeConfig"]
