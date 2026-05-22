"""Local notification API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from openjarvis.notifications import NotificationService

notification_router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


class NotificationRequest(BaseModel):
    kind: str
    title: str = ""
    body: str = ""
    payload: dict[str, Any] = {}
    priority: str = ""


class NotificationSettingsRequest(BaseModel):
    muted: bool | None = None
    priority_filters: list[str] | None = None


def get_notification_service(request: Request) -> NotificationService:
    service = getattr(request.app.state, "notification_service", None)
    if service is None:
        service = NotificationService(
            mode_registry=getattr(request.app.state, "mode_registry", None),
        )
        request.app.state.notification_service = service
    return service


@notification_router.post("")
async def queue_notification(body: NotificationRequest, request: Request):
    notification = get_notification_service(request).queue(
        body.kind,
        title=body.title,
        body=body.body,
        payload=body.payload,
        priority=body.priority,
    )
    return {"notification": notification.to_dict()}


@notification_router.get("")
async def list_notifications(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
):
    notifications = get_notification_service(request).list_notifications(limit=limit)
    return {
        "notifications": [item.to_dict() for item in notifications],
        "local_only": True,
        "passive_only": True,
        "cloud_push_enabled": False,
    }


@notification_router.get("/queue")
async def notification_queue_status(request: Request):
    return get_notification_service(request).queue_status()


@notification_router.post("/{notification_id}/dismiss")
async def dismiss_notification(notification_id: str, request: Request):
    try:
        notification = get_notification_service(request).dismiss(notification_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc
    return {"notification": notification.to_dict()}


@notification_router.post("/clear")
async def clear_notifications(request: Request):
    count = get_notification_service(request).clear()
    return {"cleared": count, "local_only": True}


@notification_router.patch("/settings")
async def update_notification_settings(
    body: NotificationSettingsRequest,
    request: Request,
):
    return (
        get_notification_service(request)
        .update_settings(
            muted=body.muted,
            priority_filters=body.priority_filters,
        )
        .to_dict()
    )


@notification_router.get("/settings")
async def notification_settings(request: Request):
    return get_notification_service(request).settings().to_dict()


@notification_router.get("/mission-control")
async def notification_mission_control(request: Request):
    return get_notification_service(request).mission_control_snapshot()


__all__ = ["get_notification_service", "notification_router"]
