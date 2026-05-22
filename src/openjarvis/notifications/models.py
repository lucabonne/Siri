"""Typed models for local Mission Control notifications."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Notification:
    id: str
    kind: str
    title: str = ""
    body: str = ""
    priority: str = "normal"
    status: str = "unread"
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    local_only: bool = True
    passive_only: bool = True
    cloud_push_enabled: bool = False
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NotificationSettings:
    muted: bool = False
    priority_filters: list[str] = field(default_factory=list)
    local_only: bool = True
    passive_only: bool = True
    cloud_push_enabled: bool = False
    telemetry_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["Notification", "NotificationSettings"]
