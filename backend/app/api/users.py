from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.schemas.auth import UserResponse, UserRoleUpdate, UserDetailedProfile, UserAnalysisStats
from app.services.user_service import (
    get_users,
    get_user_by_id,
    update_user_role,
    delete_user,
    get_user_analysis_stats
)
from app.services.auth_service import get_current_active_admin, get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/")
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Get all users (admin only)
    Returns list of all registered users with their details
    """
    users = get_users(db, skip=skip, limit=limit)

    # Update is_online status dynamically based on last_login
    # Consider user online if last_login was within last 2 minutes
    now = datetime.utcnow()
    online_threshold = timedelta(minutes=2)

    # Manually format response with proper datetime 'Z' suffix
    users_data = []
    for user in users:
        if user.last_login:
            time_since_login = now - user.last_login
            is_online = time_since_login < online_threshold
        else:
            is_online = False

        users_data.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_online": is_online,
            "created_at": user.created_at.isoformat() + 'Z' if user.created_at else None,
            "last_login": user.last_login.isoformat() + 'Z' if user.last_login else None,
            "previous_login": user.previous_login.isoformat() + 'Z' if user.previous_login else None,
            "session_start": user.session_start.isoformat() + 'Z' if user.session_start else None,
            "total_online_time": user.total_online_time if user.total_online_time else 0
        })

    return users_data


@router.get("/{user_id}/profile", response_model=UserDetailedProfile)
async def get_user_detailed_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Get detailed user profile with activity history and analysis statistics (admin only)
    Returns comprehensive user information including analysis stats
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get analysis statistics
    analysis_stats = get_user_analysis_stats(db, user_id)

    # Create detailed profile response
    user_dict = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "is_online": user.is_online,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "previous_login": user.previous_login,
        "session_start": user.session_start,
        "total_online_time": user.total_online_time if user.total_online_time else 0,
        "analysis_stats": analysis_stats
    }

    return user_dict


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Get user by ID (admin only)
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_role(
    user_id: int,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Update user role (admin only)
    Allows admin to change user's role to admin, analyst, or viewer
    """
    # Prevent admin from changing their own role
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )

    user = update_user_role(db, user_id, role_update.role)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.delete("/{user_id}")
async def delete_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Delete user by ID (admin only)
    Permanently removes user from the system
    """
    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    success = delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {"message": "User deleted successfully"}


# ───────── Notification preferences (per-user, NOT admin-only) ─────────

@router.get("/me/notification-settings")
async def get_my_notification_settings(
    current_user: User = Depends(get_current_user),
):
    """Return the current user's notification preferences, with defaults applied for missing keys."""
    from app.services.notification_settings_service import get_settings
    return get_settings(current_user)


@router.put("/me/notification-settings")
async def update_my_notification_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the current user's notification preferences.

    Body: {"email": true/false, "in_app": true/false, "security": true/false, "analyses": true/false}
    Unknown keys are silently ignored to keep the API stable across future toggle additions.
    """
    from app.services.notification_settings_service import update_settings
    try:
        updated = update_settings(db, current_user, payload or {})
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update settings")
    return updated
