from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from datetime import datetime
from app.core.database import Base


# Default notification preferences. New users get these on first read if their
# notification_settings column is NULL. Keep aligned with the Settings page toggles.
DEFAULT_NOTIFICATION_SETTINGS = {
    "email": True,         # Send email for important events (new login, password change, etc.)
    "in_app": True,        # Show notifications in the bell-icon dropdown
    "security": True,      # Security-category events (new_login, parallel_session, password_changed)
    "analyses": True,      # Analysis-category events (completed, failed, cancelled)
}


class User(Base):
    """User model for authentication and authorization"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), default="analyst")  # admin, analyst, viewer
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)  # Online status tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)  # ONLY updated on actual login (POST /api/auth/login)
    last_activity = Column(DateTime, nullable=True)  # Updated on ANY user activity (heartbeat, API calls)
    previous_login = Column(DateTime, nullable=True)  # Previous login for security tracking
    session_start = Column(DateTime, nullable=True)  # Current session start time
    total_online_time = Column(Integer, default=0)  # Total time online in seconds

    # Per-user notification preferences (JSON). Schema: see DEFAULT_NOTIFICATION_SETTINGS.
    # Nullable for backward compatibility with users created before this column existed —
    # reads fall back to defaults; writes always store the full dict.
    notification_settings = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
