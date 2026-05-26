"""Per-user notification preferences — read/write/check helpers.

Used by:
  - GET/PUT /api/users/me/notification-settings (the Settings page)
  - notify() in notification_service to filter out notifications the user disabled
  - Future email-sender to skip email when prefs.email == False
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User, DEFAULT_NOTIFICATION_SETTINGS

# Allowed keys; anything else is silently ignored on write to keep the API stable.
ALLOWED_KEYS = set(DEFAULT_NOTIFICATION_SETTINGS.keys())

# Map notification kind → category. Used to decide if a notify() call should
# be suppressed based on user prefs ("security" / "analyses" toggles).
KIND_TO_CATEGORY = {
    "new_login": "security",
    "parallel_session": "security",
    "password_changed": "security",
    "analysis_completed": "analyses",
    "analysis_failed": "analyses",
    "analysis_cancelled": "analyses",
    "system_alert": "in_app",   # treat as always-show unless user fully disabled in_app
    "info": "in_app",
}


def get_settings(user: User) -> dict:
    """Return the user's notification settings, falling back to defaults for missing keys."""
    stored = user.notification_settings or {}
    merged = {**DEFAULT_NOTIFICATION_SETTINGS, **{k: v for k, v in stored.items() if k in ALLOWED_KEYS}}
    return merged


def update_settings(db: Session, user: User, patch: dict) -> dict:
    """Patch the user's settings. Unknown keys are ignored. Returns the new full dict."""
    current = get_settings(user)
    for k, v in patch.items():
        if k in ALLOWED_KEYS:
            current[k] = bool(v)
    user.notification_settings = current
    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise
    return current


def should_create_in_app(user: User, kind: str) -> bool:
    """Should notify() create an in-app (bell) notification for this kind?

    Returns False if either:
      - user disabled in_app entirely
      - the category for this kind is disabled
    """
    if user is None:
        return True  # Defensive: if we can't load the user, default to delivering
    settings = get_settings(user)
    if not settings.get("in_app", True):
        return False
    category = KIND_TO_CATEGORY.get(kind)
    if category and category in settings and not settings.get(category, True):
        return False
    return True


def should_send_email(user: User, kind: Optional[str] = None) -> bool:
    """Should we send an email for this notification kind?"""
    if user is None:
        return False
    settings = get_settings(user)
    if not settings.get("email", True):
        return False
    if kind:
        category = KIND_TO_CATEGORY.get(kind)
        if category and category in settings and not settings.get(category, True):
            return False
    return True
