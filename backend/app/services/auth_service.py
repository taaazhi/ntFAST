from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.models.user import User
from app.core.security import verify_password, create_access_token, decode_access_token
from app.core.database import get_db
from app.services.user_service import get_user_by_email, get_user_by_id
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user by email and password (username parameter accepts email)"""
    # Always treat as email
    user = get_user_by_email(db, username)

    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None

    # SECURITY: DO NOT update last_login here!
    # It will be updated in /api/auth/login endpoint AFTER authentication
    # This prevents double-update of previous_login
    # update_last_login(db, user.id)  # REMOVED - causes double update

    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return user


async def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user with admin role"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def ensure_writable(
    current_user: User = Depends(get_current_user)
) -> User:
    """Запретить запись учёткам read-only demo.

    Стенд показывает предзагруженные анализы всем, но менять их гость не должен:
    иначе один посетитель испортит витрину для остальных или сожжёт триал
    загрузками. Список демо-почт задаётся `DEMO_READONLY_EMAILS`; пусто —
    проверка ничего не блокирует, и обычные учётки работают как прежде.
    """
    from app.core.config import settings
    if current_user.email.lower() in settings.demo_readonly_email_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Демо-режим: только просмотр. Загрузка и изменения отключены.",
        )
    return current_user
