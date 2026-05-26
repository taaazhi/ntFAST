"""Notification service — single entry point for creating user-facing notifications.

Usage:
    from app.services.notification_service import notify
    notify(db, user_id=user.id, kind="new_login", title="Новый вход", body="...", data={"ip": "1.2.3.4"})

This writes a row to `notifications` and best-effort broadcasts a WebSocket
message to the user's open tabs so the bell badge updates in real-time.
"""
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification

logger = logging.getLogger(__name__)


def notify(
    db: Session,
    *,
    user_id: int,
    kind: str,
    title: str,
    body: Optional[str] = None,
    data: Optional[dict[str, Any]] = None,
    severity: str = "info",
    broadcast: bool = True,
) -> Optional[Notification]:
    """Create a Notification row and (optionally) push a WS event.

    Returns the created Notification or None on failure (failure is logged
    but never raised — notification creation must NEVER break the caller's
    primary flow, e.g. login or analysis completion).
    """
    try:
        n = Notification(
            user_id=user_id,
            kind=kind,
            severity=severity,
            title=title[:255],
            body=body,
            data=data,
        )
        db.add(n)
        db.commit()
        db.refresh(n)
    except Exception as e:
        logger.error(f"notify(): failed to create notification: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return None

    if broadcast:
        try:
            # Lazy import to avoid circular dependencies (api.websocket → services → models)
            import asyncio
            from app.api.websocket import manager

            payload = {
                "type": "notification_new",
                "user_id": user_id,
                "notification": {
                    "id": n.id,
                    "kind": n.kind,
                    "severity": n.severity,
                    "title": n.title,
                    "body": n.body,
                    "data": n.data,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() + "Z" if n.created_at else None,
                },
            }
            # We're usually called from sync code (API handler / Celery task);
            # schedule the async broadcast on the running event loop if one exists.
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.broadcast(payload))
            except RuntimeError:
                # No running loop — silently skip the broadcast (the notification
                # is still persisted; client will get it on next poll/refresh).
                logger.debug("notify(): no running loop, skipping WS broadcast")
        except Exception as e:
            logger.debug(f"notify(): WS broadcast failed (non-fatal): {e}")

    return n
