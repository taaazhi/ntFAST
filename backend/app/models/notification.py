"""
Notification model — persistent user-facing notifications.

Drives the bell icon + dropdown in the frontend. Created by various services
(auth on login, analysis on completion, etc.) and consumed via /api/notifications.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Index, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


# Allowed notification kinds — kept in sync with frontend NotificationKind type.
NOTIFICATION_KINDS = (
    "analysis_completed",
    "analysis_failed",
    "analysis_cancelled",
    "new_login",
    "parallel_session",
    "password_changed",
    "system_alert",
    "info",
)

NOTIFICATION_SEVERITIES = ("info", "success", "warning", "error")


class Notification(Base):
    """A single notification record for one user.

    `data` is a free-form JSON payload (e.g. {"analysis_id": 42, "risk_score": 73})
    that the frontend uses to render the notification body and deep-link to the
    relevant page.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
        CheckConstraint(
            "kind IN ('analysis_completed','analysis_failed','analysis_cancelled',"
            "'new_login','parallel_session','password_changed','system_alert','info')",
            name="ck_notifications_kind_valid",
        ),
        CheckConstraint(
            "severity IN ('info','success','warning','error')",
            name="ck_notifications_severity_valid",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    kind = Column(String(40), nullable=False)
    severity = Column(String(10), nullable=False, default="info")

    # Free-text title (already translated by the producer) and optional body
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)

    # Structured payload — analysis_id, etc. Used by FE to render context and deep-link.
    data = Column(JSON, nullable=True)

    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)

    # Optional relationship — handy for joins in admin views.
    user = relationship("User", backref="notifications", passive_deletes=True)

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, kind={self.kind}, is_read={self.is_read})>"
