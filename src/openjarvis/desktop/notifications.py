"""User-triggered local desktop notifications."""

from __future__ import annotations

from openjarvis.desktop.config import ALLOWED_NOTIFICATION_KINDS
from openjarvis.desktop.models import DesktopNotification, DesktopNotificationState
from openjarvis.desktop.sessions import DesktopSessionStore, utc_now


class NotificationCenter:
    """Record lightweight notifications without background delivery loops."""

    def __init__(
        self,
        *,
        session_store: DesktopSessionStore,
        allowed_kinds: list[str] | None = None,
    ) -> None:
        self._session_store = session_store
        self._allowed_kinds = list(allowed_kinds or ALLOWED_NOTIFICATION_KINDS)

    def state(self) -> DesktopNotificationState:
        session = self._session_store.load()
        last = (
            session.recent_notifications[0].created_at
            if session.recent_notifications
            else ""
        )
        return DesktopNotificationState(
            recent=session.recent_notifications,
            allowed_kinds=list(self._allowed_kinds),
            last_notification_at=last,
            enabled=True,
            autonomous_notifications=False,
            local_only=True,
            passive_only=True,
            telemetry_enabled=False,
        )

    def notify(
        self,
        kind: str,
        title: str,
        body: str = "",
        *,
        user_triggered: bool = True,
        delivered: bool = False,
    ) -> DesktopNotification:
        if kind not in self._allowed_kinds:
            return DesktopNotification(
                kind=kind,
                title=title,
                body=body,
                status="blocked",
                created_at=utc_now(),
                user_triggered=user_triggered,
                delivered=False,
            )
        if not user_triggered:
            return DesktopNotification(
                kind=kind,
                title=title,
                body=body,
                status="suppressed",
                created_at=utc_now(),
                user_triggered=False,
                delivered=False,
                autonomous=True,
            )
        notification = DesktopNotification(
            kind=kind,
            title=title,
            body=body,
            status="ready",
            created_at=utc_now(),
            user_triggered=True,
            delivered=delivered,
        )
        self._session_store.record_notification(notification)
        return notification


__all__ = ["NotificationCenter"]
