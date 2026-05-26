"""Notification service — single entry point for creating user-facing notifications.

Usage:
    from app.services.notification_service import notify
    notify(db, user_id=user.id, kind="new_login", title="Новый вход", body="...", data={"ip": "1.2.3.4"})

This writes a row to `notifications` and best-effort broadcasts a WebSocket
message to the user's open tabs so the bell badge updates in real-time.

Auto-cleanup (social-media-style):
  * Read notifications older than NOTIFICATION_RETENTION_DAYS are deleted lazily
  * A per-user soft cap of MAX_NOTIFICATIONS_PER_USER is enforced — oldest
    notifications drop off when the cap is exceeded.

Both cleanups run when `notify()` creates a new row, so there's no scheduler.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.notification import Notification

logger = logging.getLogger(__name__)


# Auto-cleanup tuning. Conservative defaults — read notifications hang around
# for a month, after which they self-delete; total cap is generous so a power
# user won't lose recent context.
NOTIFICATION_RETENTION_DAYS = 30
MAX_NOTIFICATIONS_PER_USER = 100


def _auto_cleanup(db: Session, user_id: int) -> None:
    """Lazy housekeeping for a user's notification inbox.

    1) Delete READ notifications older than NOTIFICATION_RETENTION_DAYS.
    2) If total count still > MAX_NOTIFICATIONS_PER_USER, delete the oldest
       ones (read OR unread) until under the cap.

    Runs best-effort: failure here must never break the caller (notify())
    or the user-facing endpoint.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=NOTIFICATION_RETENTION_DAYS)

        # (1) Delete old read notifications
        old_read_deleted = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read == True,  # noqa: E712
                Notification.created_at < cutoff,
            )
            .delete(synchronize_session=False)
        )

        # (2) Enforce per-user cap. Count first to avoid expensive query if not needed.
        total = (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .count()
        )
        excess_deleted = 0
        if total > MAX_NOTIFICATIONS_PER_USER:
            # Find IDs of the oldest excess rows and delete by ID set (safer than
            # raw OFFSET in a delete query — works across SQLAlchemy dialects).
            excess = total - MAX_NOTIFICATIONS_PER_USER
            oldest_ids = [
                row.id for row in (
                    db.query(Notification.id)
                    .filter(Notification.user_id == user_id)
                    .order_by(Notification.created_at.asc())
                    .limit(excess)
                    .all()
                )
            ]
            if oldest_ids:
                excess_deleted = (
                    db.query(Notification)
                    .filter(Notification.id.in_(oldest_ids))
                    .delete(synchronize_session=False)
                )

        if old_read_deleted or excess_deleted:
            db.commit()
            logger.debug(
                f"_auto_cleanup: user={user_id} removed "
                f"{old_read_deleted} old-read + {excess_deleted} over-cap"
            )
    except Exception as e:
        logger.debug(f"_auto_cleanup failed (non-fatal): {e}")
        try:
            db.rollback()
        except Exception:
            pass


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
    force: bool = False,
) -> Optional[Notification]:
    """Create a Notification row and (optionally) push a WS event.

    Honours per-user notification settings: if the user has disabled the relevant
    category (security/analyses) OR in_app entirely, no row is created. Pass
    `force=True` to bypass preferences (use only for safety-critical alerts).

    Returns the created Notification or None on failure / suppression (suppression
    is logged at debug level only — it's expected behavior, not an error).
    """
    # Check user preferences before doing any DB work
    if not force:
        try:
            from app.models.user import User
            from app.services.notification_settings_service import should_create_in_app
            user = db.query(User).filter(User.id == user_id).first()
            if user and not should_create_in_app(user, kind):
                logger.debug(
                    f"notify(): suppressed kind={kind} for user={user_id} (user prefs)"
                )
                return None
        except Exception as e:
            # Preferences lookup failed — fall through and deliver the notification
            # (better to over-deliver than to drop important events silently).
            logger.debug(f"notify(): prefs check failed, delivering anyway: {e}")

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

    # Lazy auto-cleanup after successful insert: removes old read notifications
    # and enforces per-user cap. Runs only when we actually add a row, so cost
    # is amortized and doesn't slow down list-views.
    _auto_cleanup(db, user_id)

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
