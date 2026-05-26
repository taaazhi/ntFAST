"""Notification endpoints.

GET    /api/notifications/          — list current user's notifications (paginated)
POST   /api/notifications/{id}/read — mark single notification as read
POST   /api/notifications/read-all  — mark all of current user's notifications as read
DELETE /api/notifications/{id}      — delete one notification
DELETE /api/notifications/          — delete ALL notifications for current user

Auth: all endpoints require authenticated user. Users can only access their own
notifications (admins are no exception — there's no admin browsing of user inboxes).
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services.auth_service import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current user's notifications, newest first.

    Always returns `total` and `unread` counters alongside the page so the
    bell icon badge stays accurate without a separate count endpoint.
    """
    base = db.query(Notification).filter(Notification.user_id == current_user.id)

    total = base.count()
    unread = base.filter(Notification.is_read == False).count()  # noqa: E712

    query = base
    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712

    items = (
        query.order_by(desc(Notification.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    return NotificationListResponse(items=items, total=total, unread=unread)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read. Idempotent."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.utcnow()
        try:
            db.commit()
            db.refresh(notif)
        except Exception:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update notification")
    return notif


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark every unread notification of the current user as read in one query."""
    now = datetime.utcnow()
    try:
        updated = (
            db.query(Notification)
            .filter(Notification.user_id == current_user.id, Notification.is_read == False)  # noqa: E712
            .update({Notification.is_read: True, Notification.read_at: now}, synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to mark notifications as read")
    return {"updated": updated}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete one notification."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    try:
        db.delete(notif)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete notification")
    return None


@router.delete("/", status_code=status.HTTP_200_OK)
async def delete_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete every notification for the current user (clears the inbox)."""
    try:
        deleted = (
            db.query(Notification)
            .filter(Notification.user_id == current_user.id)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to clear notifications")
    return {"deleted": deleted}
