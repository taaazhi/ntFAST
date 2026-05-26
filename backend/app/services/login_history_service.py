from sqlalchemy.orm import Session
from app.models.login_history import LoginHistory
from datetime import datetime, timezone, timedelta
from typing import List, Optional

# Session is auto-closed after this many days without any login activity.
# Tied to JWT exp (30 days) loosely — but 7 days is a sensible inactivity threshold.
SESSION_INACTIVITY_DAYS = 7


def create_login_record(
    db: Session,
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    location: Optional[str] = None
) -> LoginHistory:
    """
    Create a new login history record

    Args:
        db: Database session
        user_id: ID of the user logging in
        ip_address: IP address of the login (optional)
        user_agent: User agent string (browser/device info) (optional)
        location: Geographic location (optional)

    Returns:
        Created LoginHistory record
    """
    login_record = LoginHistory(
        user_id=user_id,
        login_time=datetime.now(timezone.utc).replace(tzinfo=None),
        ip_address=ip_address,
        user_agent=user_agent,
        location=location,
        is_suspicious=False
    )

    db.add(login_record)
    db.commit()
    db.refresh(login_record)

    return login_record


def update_logout_time(
    db: Session,
    login_record_id: int,
    logout_time: Optional[datetime] = None
) -> Optional[LoginHistory]:
    """
    Update logout time for a login record

    Args:
        db: Database session
        login_record_id: ID of the login record
        logout_time: Logout time (defaults to current UTC time)

    Returns:
        Updated LoginHistory record or None if not found
    """
    record = db.query(LoginHistory).filter(LoginHistory.id == login_record_id).first()

    if record:
        if logout_time is None:
            logout_time = datetime.now(timezone.utc).replace(tzinfo=None)

        record.logout_time = logout_time

        # Calculate session duration
        if record.login_time:
            duration = (logout_time - record.login_time).total_seconds()
            record.session_duration = int(duration)

        db.commit()
        db.refresh(record)

    return record


def get_user_login_history(
    db: Session,
    user_id: int,
    limit: int = 10
) -> List[LoginHistory]:
    """
    Get login history for a specific user

    Args:
        db: Database session
        user_id: ID of the user
        limit: Maximum number of records to return

    Returns:
        List of LoginHistory records ordered by login time (newest first)
    """
    return db.query(LoginHistory)\
        .filter(LoginHistory.user_id == user_id)\
        .order_by(LoginHistory.login_time.desc())\
        .limit(limit)\
        .all()


def expire_stale_sessions(db: Session, user_id: int, inactivity_days: int = SESSION_INACTIVITY_DAYS) -> int:
    """Lazy cleanup: close any LoginHistory rows older than `inactivity_days`.

    Called from `get_active_sessions` so the active-sessions API never returns
    sessions older than the inactivity threshold. Returns count of rows closed.

    Why lazy: avoids a background scheduler — runs at most once per /active-sessions
    request and operates on at most a handful of rows per user.
    """
    cutoff = datetime.utcnow() - timedelta(days=inactivity_days)
    stale = (
        db.query(LoginHistory)
        .filter(
            LoginHistory.user_id == user_id,
            LoginHistory.logout_time.is_(None),
            LoginHistory.login_time < cutoff,
        )
        .all()
    )
    if not stale:
        return 0
    now = datetime.utcnow()
    for record in stale:
        record.logout_time = now
        if record.login_time:
            record.session_duration = int((now - record.login_time).total_seconds())
    try:
        db.commit()
    except Exception:
        db.rollback()
        return 0
    return len(stale)


def get_active_sessions(db: Session, user_id: int) -> List[LoginHistory]:
    """
    Get all active (not logged out) sessions for a user.

    Side effect: closes sessions inactive for > SESSION_INACTIVITY_DAYS days
    before returning, so callers never see ancient stale rows.
    """
    # Lazy cleanup of expired sessions
    expire_stale_sessions(db, user_id)

    return db.query(LoginHistory)\
        .filter(
            LoginHistory.user_id == user_id,
            LoginHistory.logout_time == None  # noqa: E711
        )\
        .order_by(LoginHistory.login_time.desc())\
        .all()


def mark_as_suspicious(
    db: Session,
    login_record_id: int,
    suspicious: bool = True
) -> Optional[LoginHistory]:
    """
    Mark a login record as suspicious or not

    Args:
        db: Database session
        login_record_id: ID of the login record
        suspicious: Whether to mark as suspicious

    Returns:
        Updated LoginHistory record or None if not found
    """
    record = db.query(LoginHistory).filter(LoginHistory.id == login_record_id).first()

    if record:
        record.is_suspicious = suspicious
        db.commit()
        db.refresh(record)

    return record


def get_latest_login(db: Session, user_id: int) -> Optional[LoginHistory]:
    """
    Get the most recent login record for a user

    Args:
        db: Database session
        user_id: ID of the user

    Returns:
        Latest LoginHistory record or None
    """
    return db.query(LoginHistory)\
        .filter(LoginHistory.user_id == user_id)\
        .order_by(LoginHistory.login_time.desc())\
        .first()


def close_all_sessions(db: Session, user_id: int) -> int:
    """
    Close all active sessions for a user (logout all devices)

    Args:
        db: Database session
        user_id: ID of the user

    Returns:
        Number of sessions closed
    """
    active_sessions = get_active_sessions(db, user_id)
    current_time = datetime.now(timezone.utc).replace(tzinfo=None)

    count = 0
    for session in active_sessions:
        session.logout_time = current_time

        # Calculate session duration
        if session.login_time:
            duration = (current_time - session.login_time).total_seconds()
            session.session_duration = int(duration)

        count += 1

    db.commit()
    return count
