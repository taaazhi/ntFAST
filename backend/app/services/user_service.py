from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from datetime import datetime
from typing import Optional, List


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()



def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Get list of users"""
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user: UserCreate) -> User:
    """Create new user"""
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
    """Update user"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None

    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user


def update_last_login(db: Session, user_id: int) -> datetime:
    """
    SECURITY: Update last_login ONLY on actual authentication (POST /api/auth/login).
    This function should NEVER be called from heartbeat or activity tracking!

    Updates:
    - previous_login: saves current last_login value
    - last_login: updates to current time
    - last_activity: updates to current time
    - session_start: starts new session
    - is_online: sets to True

    Returns the updated last_login timestamp in UTC (timezone-naive for SQLite).
    """
    from datetime import timezone
    db_user = get_user_by_id(db, user_id)
    if db_user:
        # ALWAYS use UTC for consistency across all timezones
        current_time = datetime.now(timezone.utc).replace(tzinfo=None)

        # SECURITY: Save current last_login as previous_login BEFORE updating
        # This allows users to see when they REALLY last logged in (not the current login)
        db_user.previous_login = db_user.last_login

        # Update to current login time (UTC, timezone-naive for SQLite)
        db_user.last_login = current_time
        db_user.last_activity = current_time  # Also update activity on login

        # Start new session
        db_user.session_start = current_time
        db_user.is_online = True

        db.commit()
        return current_time
    return datetime.now(timezone.utc).replace(tzinfo=None)


def update_last_activity(db: Session, user_id: int) -> datetime:
    """
    Update ONLY last_activity timestamp for user activity tracking.

    This function is called from:
    - Heartbeat endpoint (keeps session alive)
    - API middleware (tracks any user action)
    - WebSocket messages

    IMPORTANT: This does NOT update last_login! Only last_activity.

    Returns the updated last_activity timestamp in UTC (timezone-naive for SQLite).
    """
    from datetime import timezone
    db_user = get_user_by_id(db, user_id)
    if db_user:
        # Update ONLY last_activity, NOT last_login
        current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        db_user.last_activity = current_time
        db_user.is_online = True  # Keep online status

        db.commit()
        return current_time
    return datetime.now(timezone.utc).replace(tzinfo=None)


def update_user_role(db: Session, user_id: int, role: str) -> Optional[User]:
    """Update user's role (admin only)"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None

    db_user.role = role
    db.commit()
    db.refresh(db_user)
    return db_user


class UserHasAnalyses(Exception):
    """У аналитика есть проведённые анализы, и удалять его нельзя.

    Не техническое ограничение, а решение по существу: анализ выписки —
    материал по делу, а не собственность сотрудника. Уволенный аналитик
    уходит, его заключения остаются. Учётную запись в таком случае
    отключают (`is_active = false`), а не стирают.
    """

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"у пользователя {count} анализов")


def delete_user(db: Session, user_id: int) -> bool:
    """Удалить пользователя. Служебные записи чистятся, анализы — нет.

    Уведомления и история входов принадлежат самой учётной записи и уходят
    вместе с ней. Чистятся явно, а не каскадом: у `login_history` внешний
    ключ создан без `ON DELETE CASCADE`, и `db.delete()` падал нарушением
    ограничения, которое наверх приходило как 500 без объяснения.

    Поднимает `UserHasAnalyses`, если у пользователя есть анализы.
    """
    from app.models.analysis import Analysis
    from app.models.login_history import LoginHistory
    from app.models.notification import Notification

    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return False

    analyses = db.query(Analysis).filter(Analysis.analyst_id == user_id).count()
    if analyses:
        raise UserHasAnalyses(analyses)

    db.query(Notification).filter(Notification.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(LoginHistory).filter(LoginHistory.user_id == user_id).delete(
        synchronize_session=False
    )
    db.delete(db_user)
    db.commit()
    return True


def update_online_status(db: Session, user_id: int, is_online: bool) -> None:
    """Update user's online status and calculate session time"""
    from datetime import timezone
    db_user = get_user_by_id(db, user_id)
    if db_user:
        # If going offline and has an active session, calculate session duration
        if not is_online and db_user.session_start:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            session_duration = int((current_time - db_user.session_start).total_seconds())

            # Add to total online time
            if db_user.total_online_time is None:
                db_user.total_online_time = 0
            db_user.total_online_time += session_duration

            # Clear session start
            db_user.session_start = None

        db_user.is_online = is_online
        db.commit()


def change_user_password(db: Session, user_id: int, current_password: str, new_password: str) -> bool:
    """Change user's password after verifying current password"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return False

    # Verify current password
    if not verify_password(current_password, db_user.password_hash):
        return False

    # Update to new password
    db_user.password_hash = get_password_hash(new_password)
    db.commit()
    return True


def get_user_analysis_stats(db: Session, user_id: int) -> dict:
    """Get analysis statistics for a specific user"""
    from app.models.analysis import Analysis
    from sqlalchemy import func

    # Get total count by status
    total = db.query(Analysis).filter(Analysis.analyst_id == user_id).count()
    pending = db.query(Analysis).filter(
        Analysis.analyst_id == user_id,
        Analysis.status == "pending"
    ).count()
    in_progress = db.query(Analysis).filter(
        Analysis.analyst_id == user_id,
        Analysis.status == "in_progress"
    ).count()
    completed = db.query(Analysis).filter(
        Analysis.analyst_id == user_id,
        Analysis.status == "completed"
    ).count()

    # Calculate average risk score for completed analyses
    avg_risk = db.query(func.avg(Analysis.risk_score)).filter(
        Analysis.analyst_id == user_id,
        Analysis.status == "completed"
    ).scalar()

    return {
        "total_analyses": total,
        "pending_analyses": pending,
        "in_progress_analyses": in_progress,
        "completed_analyses": completed,
        "average_risk_score": round(float(avg_risk), 2) if avg_risk else None
    }
