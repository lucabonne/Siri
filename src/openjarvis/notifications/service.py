"""Local-only notification queue for Mission Control."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from openjarvis.notifications.models import Notification, NotificationSettings

IMPORTANT_KINDS = {
    "approval_required",
    "workflow_finished",
    "research_completed",
    "build_failed",
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class NotificationService:
    """Persist small local notifications without push delivery or telemetry."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        mode_registry: Any = None,
    ) -> None:
        if db_path is None:
            db_path = Path.home() / ".openjarvis" / "notifications.db"
        self.db_path = Path(db_path).expanduser()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.mode_registry = mode_registry
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._conn.close()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'normal',
                status TEXT NOT NULL DEFAULT 'unread',
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notification_settings (
                id TEXT PRIMARY KEY,
                muted INTEGER NOT NULL DEFAULT 0,
                priority_filters TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def queue(
        self,
        kind: str,
        *,
        title: str = "",
        body: str = "",
        payload: dict[str, Any] | None = None,
        priority: str = "",
    ) -> Notification:
        now = _utc_now()
        notification = Notification(
            id=str(uuid.uuid4()),
            kind=kind,
            title=title or _title_for_kind(kind),
            body=body,
            priority=priority or _priority_for_kind(kind),
            status="unread",
            payload=payload or {},
            created_at=now,
            updated_at=now,
        )
        self._conn.execute(
            """
            INSERT INTO notifications (
                id, kind, title, body, priority, status, payload, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notification.id,
                notification.kind,
                notification.title,
                notification.body,
                notification.priority,
                notification.status,
                _json_dumps(notification.payload),
                notification.created_at,
                notification.updated_at,
            ),
        )
        self._conn.commit()
        return notification

    def list_notifications(self, *, limit: int = 50) -> list[Notification]:
        rows = self._conn.execute(
            """
            SELECT * FROM notifications
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def queue_status(self) -> dict[str, Any]:
        unread = self._conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE status = 'unread'",
        ).fetchone()[0]
        return {
            "unread": int(unread),
            "quiet_mode": self._quiet_mode(),
            "local_only": True,
            "passive_only": True,
            "cloud_push_enabled": False,
            "telemetry_enabled": False,
        }

    def dismiss(self, notification_id: str) -> Notification:
        now = _utc_now()
        self._conn.execute(
            """
            UPDATE notifications
            SET status = 'dismissed', updated_at = ?
            WHERE id = ?
            """,
            (now, notification_id),
        )
        self._conn.commit()
        notification = self.get(notification_id)
        if notification is None:
            raise KeyError(notification_id)
        return notification

    def get(self, notification_id: str) -> Notification | None:
        row = self._conn.execute(
            "SELECT * FROM notifications WHERE id = ?",
            (notification_id,),
        ).fetchone()
        return self._row_to_notification(row) if row else None

    def clear(self) -> int:
        count = self._conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
        self._conn.execute("DELETE FROM notifications")
        self._conn.commit()
        return int(count)

    def settings(self) -> NotificationSettings:
        row = self._conn.execute(
            "SELECT * FROM notification_settings WHERE id = 'default'",
        ).fetchone()
        if row is None:
            return NotificationSettings()
        return NotificationSettings(
            muted=bool(row["muted"]),
            priority_filters=list(_json_loads(row["priority_filters"], [])),
        )

    def update_settings(
        self,
        *,
        muted: bool | None = None,
        priority_filters: list[str] | None = None,
    ) -> NotificationSettings:
        current = self.settings()
        next_settings = NotificationSettings(
            muted=current.muted if muted is None else muted,
            priority_filters=(
                current.priority_filters
                if priority_filters is None
                else list(priority_filters)
            ),
        )
        self._conn.execute(
            """
            INSERT INTO notification_settings (
                id, muted, priority_filters, updated_at
            )
            VALUES ('default', ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                muted = excluded.muted,
                priority_filters = excluded.priority_filters,
                updated_at = excluded.updated_at
            """,
            (
                1 if next_settings.muted else 0,
                _json_dumps(next_settings.priority_filters),
                _utc_now(),
            ),
        )
        self._conn.commit()
        return next_settings

    def mission_control_snapshot(self) -> dict[str, Any]:
        settings = self.settings()
        return {
            "notifications": [
                item.to_dict() for item in self.list_notifications(limit=20)
            ],
            "queue": self.queue_status(),
            "muted_state": settings.muted,
            "priority_filters": list(settings.priority_filters),
            "autonomous_interruptions": False,
            "local_only": True,
            "passive_only": True,
            "cloud_push_enabled": False,
            "telemetry_enabled": False,
        }

    def notify_research_completed(self, session: Any) -> Notification:
        return self.queue(
            "research_completed",
            body=str(getattr(session, "question", "")),
            payload={"research_id": getattr(session, "id", "")},
        )

    def notify_workflow_completed(self, run: Any) -> Notification:
        return self.queue(
            "workflow_finished",
            body=str(getattr(run, "workflow_name", "")),
            payload={"workflow_id": getattr(run, "workflow_id", "")},
        )

    def notify_build_completed(
        self,
        *,
        status: str,
        cwd: str = "",
        privacy_mode: bool = False,
    ) -> Notification:
        return self.queue(
            "build_failed" if status == "failed" else "build_completed",
            body="Build failed" if status == "failed" else "Build succeeded",
            payload={"cwd": cwd if not privacy_mode else "", "status": status},
        )

    def _quiet_mode(self) -> bool:
        if self.mode_registry is None:
            return False
        try:
            return self.mode_registry.get_active_mode().mode.id == "quiet"
        except Exception:
            return False

    def _row_to_notification(self, row: sqlite3.Row) -> Notification:
        return Notification(
            id=row["id"],
            kind=row["kind"],
            title=row["title"],
            body=row["body"],
            priority=row["priority"],
            status=row["status"],
            payload=dict(_json_loads(row["payload"], {})),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _priority_for_kind(kind: str) -> str:
    return "important" if kind in IMPORTANT_KINDS else "normal"


def _title_for_kind(kind: str) -> str:
    return kind.replace("_", " ").strip().title() or "Notification"


__all__ = ["NotificationService"]
