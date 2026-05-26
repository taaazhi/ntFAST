import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.auth import UserCreate, UserResponse, Token, UserLogin, PasswordChange, ForgotPasswordRequest, ResetPasswordRequest
from app.services.user_service import create_user, get_user_by_email, update_online_status, change_user_password
from app.services.auth_service import authenticate_user, get_current_user
from app.models.user import User
from user_agents import parse as parse_user_agent

logger = logging.getLogger(__name__)
router = APIRouter()


def _safe_create_task(coro, *, name: str = "background_task"):
    """Schedule an async background task that logs failures instead of swallowing them.

    Fire-and-forget tasks created via asyncio.create_task() have their exceptions
    silently dropped unless explicitly retrieved. This wrapper attaches a done-callback
    that logs any unhandled exception so SMTP/WS failures stay visible in logs.
    """
    task = asyncio.create_task(coro, name=name)

    def _log_exception(t: "asyncio.Task") -> None:
        try:
            exc = t.exception()
        except (asyncio.CancelledError, asyncio.InvalidStateError):
            return
        if exc is not None:
            logger.error(f"Background task '{t.get_name()}' failed: {exc}", exc_info=exc)

    task.add_done_callback(_log_exception)
    return task


def get_device_info(user_agent_string: str) -> str:
    """Parse user agent to get readable device info"""
    try:
        ua = parse_user_agent(user_agent_string)
        browser = f"{ua.browser.family} {ua.browser.version_string}"
        os = f"{ua.os.family} {ua.os.version_string}".strip()
        if ua.is_mobile:
            device_type = "Mobile"
        elif ua.is_tablet:
            device_type = "Tablet"
        else:
            device_type = "Desktop"
        return f"{browser}, {os} ({device_type})"
    except (ValueError, AttributeError):
        return user_agent_string[:50] if user_agent_string else "Unknown Device"


def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    # Check for forwarded headers (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "Unknown"


@router.get("/registration-config")
async def registration_config():
    """Return registration configuration for frontend (e.g., whether email verification is required)."""
    from app.core.config import settings
    return {
        "require_email_verification": settings.REQUIRE_EMAIL_VERIFICATION,
    }


@router.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Step 1: Check user data and send verification code
    User will be created ONLY after email verification (if enabled)
    """
    from app.core.config import settings

    # Check if email exists
    db_user = get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # If email verification is disabled, create user immediately
    if not settings.REQUIRE_EMAIL_VERIFICATION:
        new_user = create_user(db, user)
        logger.info(f"User registered without email verification: {user.email}")
        return {"message": "Registration successful", "verification_required": False}

    # Do NOT create user yet - just return success
    # User will be created after email verification
    return {"message": "Registration data validated. Please verify your email.", "verification_required": True}


@router.post("/complete-registration", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def complete_registration(user: UserCreate, db: Session = Depends(get_db)):
    """
    Step 2: Create user after email verification
    This endpoint is called after successful email verification
    """
    # Check if email exists (again, for safety)
    db_user = get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Now create the user
    return create_user(db, user)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access token"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"User logged in: ID={user.id}, email={user.email}")

    # SECURITY: Record login in history BEFORE updating user timestamps
    from app.services.login_history_service import create_login_record
    client_ip = get_client_ip(request)
    user_agent_raw = request.headers.get("User-Agent", "")
    device_info = get_device_info(user_agent_raw)
    login_record = create_login_record(
        db,
        user_id=user.id,
        ip_address=client_ip,
        user_agent=device_info,
        location=None     # Can be determined from IP using geolocation API
    )
    logger.info(f"Created login history record ID={login_record.id} for user {user.id}")

    # Update last login time and online status (returns UTC timestamp)
    # IMPORTANT: This saves current last_login as previous_login BEFORE updating
    from app.services.user_service import update_last_login
    from datetime import datetime
    before_update = user.last_login
    updated_timestamp = update_last_login(db, user.id)

    # Refresh user to see updated value
    db.refresh(user)
    logger.debug(f"Updated last_login for user {user.id}: {before_update} -> {user.last_login}")
    logger.debug(f"Previous login for user {user.id}: {user.previous_login}")

    # Broadcast login status to all WebSocket clients
    from app.api.websocket import manager
    # Use the returned UTC timestamp (guaranteed to be accurate)
    # Add 'Z' suffix to indicate UTC timezone for JavaScript (ISO 8601 format)
    timestamp_to_broadcast = updated_timestamp.isoformat() + 'Z'
    _safe_create_task(manager.broadcast({
        "type": "status_update",
        "user_id": user.id,
        "is_online": True,
        "last_login": timestamp_to_broadcast,
        "last_activity": timestamp_to_broadcast
    }), name="ws_status_update")

    # SECURITY: Broadcast new login notification
    # This allows users to see if someone logged into their account
    _safe_create_task(manager.broadcast({
        "type": "new_login",
        "user_id": user.id,
        "login_time": timestamp_to_broadcast,
        "login_record_id": login_record.id
    }), name="ws_new_login")
    logger.debug(f"Broadcasting status update for user {user.id}")

    # SECURITY: Detect parallel sessions (multiple devices logged in simultaneously)
    from app.services.login_history_service import get_active_sessions
    from app.services.notification_service import notify

    active_sessions = get_active_sessions(db, user.id)
    if len(active_sessions) > 1:  # More than 1 means user is logged in from multiple devices
        logger.warning(f"Parallel session detected for user {user.id}: {len(active_sessions)} active sessions")
        # Broadcast warning about parallel session
        _safe_create_task(manager.broadcast({
            "type": "parallel_session_detected",
            "user_id": user.id,
            "session_count": len(active_sessions),
            "latest_session_id": login_record.id
        }), name="ws_parallel_session")
        # Persist as a notification so the user sees it in the bell next time they open the app.
        # Title/body are i18n KEYS — frontend resolves them via t(key, data) so the same row
        # renders in whatever language the viewer currently uses.
        notify(
            db,
            user_id=user.id,
            kind="parallel_session",
            severity="warning",
            title="notifications.kind.parallel_session.title",
            body="notifications.kind.parallel_session.body",
            data={"count": len(active_sessions), "latest_session_id": login_record.id},
        )

    # Persistent notification for the login itself (separate from the transient WS broadcast)
    try:
        ip = get_client_ip(request)
        device = get_device_info(request.headers.get("user-agent", ""))
        notify(
            db,
            user_id=user.id,
            kind="new_login",
            severity="info",
            title="notifications.kind.new_login.title",
            body="notifications.kind.new_login.body",
            data={
                "device": device,
                "ip": ip,
                "user_agent": request.headers.get("user-agent", ""),
                "login_record_id": login_record.id,
            },
        )
    except Exception as e:
        logger.debug(f"new_login notify failed (non-fatal): {e}")

    access_token = create_access_token(data={"sub": str(user.id)})

    # SECURITY: Return session_start from backend (single source of truth)
    # Frontend MUST use this timestamp, NOT create its own with new Date()
    session_start_iso = user.session_start.isoformat() + 'Z' if user.session_start else None
    logger.debug(f"Sending session_start to frontend: {session_start_iso}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "active_sessions_count": len(active_sessions),  # Inform user about parallel sessions
        "session_start": session_start_iso  # Backend is single source of truth for session time
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout and update online status"""
    logger.info(f"User logging out: ID={current_user.id}, email={current_user.email}")

    # SECURITY: Close active login session in history
    from app.services.login_history_service import get_active_sessions, update_logout_time
    from datetime import datetime, timezone

    active_sessions = get_active_sessions(db, current_user.id)
    if active_sessions:
        # Close the most recent active session
        latest_session = active_sessions[0]
        update_logout_time(db, latest_session.id)
        logger.info(f"Closed login session ID={latest_session.id} for user {current_user.id}")

    update_online_status(db, current_user.id, False)

    # Broadcast logout status to all WebSocket clients
    from app.api.websocket import manager
    _safe_create_task(manager.broadcast({
        "type": "user_offline",
        "user_id": current_user.id,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }), name="ws_user_offline")
    logger.debug(f"Broadcasting offline status for user {current_user.id}")

    return {"message": "Successfully logged out"}


@router.post("/heartbeat")
async def heartbeat(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's last activity timestamp and online status"""
    from app.services.user_service import update_last_activity

    # SECURITY: Update ONLY last_activity, NOT last_login
    # last_login should ONLY be updated on actual authentication (POST /login)
    # Returns accurate UTC timestamp
    updated_timestamp = update_last_activity(db, current_user.id)

    # Return the exact timestamp that was stored in database
    return {
        "message": "Activity updated",
        "user_id": current_user.id,
        "timestamp": updated_timestamp.isoformat() + 'Z',
        "is_online": True
    }


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user's password"""
    success = change_user_password(
        db,
        current_user.id,
        password_data.current_password,
        password_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(
    request_data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Request password reset - sends verification code to email.

    SECURITY: timing-attack defence.
    The previous implementation awaited SecurityInfoCollector.collect_security_info
    which performs httpx network calls (public IP lookup + geolocation, up to 5s).
    That made the "real user" branch ~1.8s while the "fake email" branch was ~11ms,
    leaking which emails are registered.

    Fix: capture only request-local data (UA, IP from headers) synchronously, then
    dispatch ALL slow work (geolocation, code generation, SMTP send) to a background
    thread. The HTTP response always returns in <100ms regardless of whether the
    email exists, so an attacker can't enumerate users by timing.
    """
    from app.services.email_service import EmailService
    from app.utils.security_info import SecurityInfoCollector

    GENERIC_RESPONSE = {"message": "If the email exists, a reset code has been sent"}

    # Look up user — fast DB query, runs for both branches
    user = get_user_by_email(db, request_data.email)
    if not user:
        logger.info("Password reset requested for non-existent email (suppressed)")
        return GENERIC_RESPONSE

    # Capture request data synchronously (no network calls) — needed because the
    # Request object isn't safe to use across the response boundary.
    user_id = user.id
    user_email = request_data.email
    user_full_name = user.full_name
    request_headers = dict(request.headers)
    request_ip = get_client_ip(request)

    async def _do_reset_work() -> None:
        """Do everything slow in the background: code gen + geo lookup + SMTP."""
        from app.core.database import SessionLocal
        bg_db = SessionLocal()
        try:
            # Generate + persist verification code
            code = EmailService.create_verification_code(bg_db, user_email)

            # Build a minimal fake Request-like object for SecurityInfoCollector
            # (it only reads .headers and .client.host)
            class _ReqStub:
                def __init__(self, headers, ip):
                    self.headers = headers
                    class _Client:
                        def __init__(self, host): self.host = host
                    self.client = _Client(ip)

            stub_req = _ReqStub(request_headers, request_ip)
            security_info = await SecurityInfoCollector.collect_security_info(
                request=stub_req,
                user_name=user_full_name,
                code=code,
                timezone="Asia/Almaty",
            )

            loc = security_info["location"]
            if loc["city"] != "Unknown" and loc["country_code"]:
                location_str = f"{loc['city']}, {loc['country_code']} ({loc['ip']})"
            else:
                location_str = loc["ip"]

            # SMTP send is blocking — run in a thread
            await asyncio.to_thread(
                EmailService.send_password_reset_code,
                user_email,
                code,
                security_info["user"]["display_name"],
                security_info["device"]["formatted"],
                location_str,
                security_info["time"]["formatted"],
            )
            logger.info(f"Password reset email delivered to {user_email}")
        except Exception as e:
            logger.error(f"Password reset background work failed for user {user_id}: {e}", exc_info=True)
        finally:
            bg_db.close()

    _safe_create_task(_do_reset_work(), name="password_reset_background")

    return GENERIC_RESPONSE


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using verification code from email
    """
    from app.services.email_service import EmailService
    from app.core.security import get_password_hash

    # Verify the code
    if not EmailService.verify_code(db, request.email, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code"
        )

    # Get user
    user = get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update password
    user.password_hash = get_password_hash(request.new_password)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Password reset commit failed for {request.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        )

    logger.info(f"Password successfully reset for {request.email}")

    # Persistent notification — alerts the user that their password was changed,
    # so an unauthorized reset is visible after the fact.
    try:
        from app.services.notification_service import notify
        notify(
            db,
            user_id=user.id,
            kind="password_changed",
            severity="warning",
            title="notifications.kind.password_changed.title",
            body="notifications.kind.password_changed.body",
        )
    except Exception as e:
        logger.debug(f"password_changed notify failed (non-fatal): {e}")

    return {"message": "Password has been reset successfully"}


@router.get("/login-history")
async def get_login_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get login history for current user
    Returns list of login records with timestamps and session info
    """
    from app.services.login_history_service import get_user_login_history

    history = get_user_login_history(db, current_user.id, limit=limit)

    # Format response
    history_data = [
        {
            "id": record.id,
            "login_time": record.login_time.isoformat() + 'Z' if record.login_time else None,
            "logout_time": record.logout_time.isoformat() + 'Z' if record.logout_time else None,
            "session_duration": record.session_duration,
            "ip_address": record.ip_address,
            "user_agent": record.user_agent,
            "location": record.location,
            "is_suspicious": bool(record.is_suspicious)
        }
        for record in history
    ]

    return {
        "user_id": current_user.id,
        "history": history_data,
        "total": len(history_data)
    }


@router.get("/active-sessions")
async def get_active_sessions_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all active (not logged out) sessions for current user.

    Marks ONE session as `is_current` by matching the requesting user-agent + IP
    against each LoginHistory row. Picks the most-recent match — handles the case
    where the same browser logged in multiple times (older login is no longer current).

    Stale sessions (> SESSION_INACTIVITY_DAYS without activity) are auto-closed
    by `get_active_sessions` before this endpoint sees them.
    """
    from app.services.login_history_service import get_active_sessions

    sessions = get_active_sessions(db, current_user.id)

    # Identify which row represents THIS request
    current_ua = request.headers.get("user-agent", "") or ""
    current_ip = get_client_ip(request) or ""
    # Pick the most-recent session whose UA+IP match — sessions list is already
    # ordered newest-first by service, so first match wins.
    current_session_id: Optional[int] = None
    for r in sessions:
        if (r.user_agent or "") == current_ua and (r.ip_address or "") == current_ip:
            current_session_id = r.id
            break
    # Fallback: if no exact match (e.g. proxy stripped UA), mark the newest one
    if current_session_id is None and sessions:
        current_session_id = sessions[0].id

    sessions_data = [
        {
            "id": record.id,
            "login_time": record.login_time.isoformat() + 'Z' if record.login_time else None,
            "ip_address": record.ip_address,
            "user_agent": record.user_agent,
            "location": record.location,
            "is_suspicious": bool(record.is_suspicious),
            # New: server-decided "is this the request that just asked?"
            "is_current": record.id == current_session_id,
        }
        for record in sessions
    ]

    return {
        "user_id": current_user.id,
        "active_sessions": sessions_data,
        "count": len(sessions_data),
    }


@router.post("/close-all-sessions")
async def close_all_sessions_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Close all active sessions (logout from all devices)
    Security feature to terminate all other sessions
    """
    from app.services.login_history_service import close_all_sessions

    count = close_all_sessions(db, current_user.id)

    # Also set user as offline
    update_online_status(db, current_user.id, False)

    # Broadcast offline status
    from app.api.websocket import manager
    from datetime import datetime, timezone
    _safe_create_task(manager.broadcast({
        "type": "user_offline",
        "user_id": current_user.id,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }), name="ws_close_all_sessions")

    return {
        "message": f"Closed {count} active session(s)",
        "sessions_closed": count
    }
