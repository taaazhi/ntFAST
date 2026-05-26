"""Pydantic schemas for the Notification API."""
from datetime import datetime
from typing import Any, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


NotificationKind = Literal[
    "analysis_completed",
    "analysis_failed",
    "analysis_cancelled",
    "new_login",
    "parallel_session",
    "password_changed",
    "system_alert",
    "info",
]

NotificationSeverity = Literal["info", "success", "warning", "error"]


class NotificationResponse(BaseModel):
    """Single notification record as returned by /api/notifications."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: NotificationKind
    severity: NotificationSeverity
    title: str
    body: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    """Paginated notification list."""
    items: list[NotificationResponse]
    total: int
    unread: int


class NotificationCreate(BaseModel):
    """Server-internal schema for creating a notification (not exposed publicly)."""
    user_id: int
    kind: NotificationKind
    severity: NotificationSeverity = "info"
    title: str = Field(..., min_length=1, max_length=255)
    body: Optional[str] = None
    data: Optional[dict[str, Any]] = None
