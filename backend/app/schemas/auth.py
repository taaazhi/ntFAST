from pydantic import BaseModel, EmailStr, Field, field_serializer, model_serializer
from datetime import datetime, timezone
from typing import Optional, Any


def _to_utc_z_iso(value: Any) -> Optional[str]:
    """Convert a datetime or ISO-string into RFC3339-style ISO with trailing 'Z' (UTC).

    Robust replacement for the previous split-by-dash approach which broke
    on legitimately-formatted timezone offsets (e.g. -05:00) and could
    mangle the date portion.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        # Treat naive datetimes as UTC (the DB stores UTC via datetime.utcnow)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    if isinstance(value, str):
        # Parse → re-normalize. Accept both with and without timezone.
        try:
            # fromisoformat tolerates "2025-11-23T17:26:41.080090+00:00" in py3.11+
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        except (ValueError, TypeError):
            return None
    return None


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)


class UserCreate(BaseModel):
    """Schema for user creation"""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(default="analyst", pattern="^(admin|analyst|viewer)$")


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for user update"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=6, max_length=100)


class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    role: str
    is_active: bool
    is_online: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    previous_login: Optional[datetime] = None  # For security: shows REAL last login before current
    session_start: Optional[datetime] = None  # Current session start time
    total_online_time: Optional[int] = 0  # Total time online in seconds

    # Pydantic v2: serializer to ensure all datetime fields render as UTC 'Z'.
    # Uses _to_utc_z_iso which correctly handles both naive and tz-aware datetimes,
    # without the fragile split-by-dash logic that broke on real timezone offsets.
    @model_serializer(mode='wrap', when_used='json')
    def serialize_model(self, serializer: Any, info: Any) -> Any:
        data = serializer(self)
        for field in ('created_at', 'last_login', 'previous_login', 'session_start'):
            if field in data and data[field] is not None:
                data[field] = _to_utc_z_iso(data[field])
        return data

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    """Schema for updating user role"""
    role: str = Field(..., pattern="^(admin|analyst|viewer)$")


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"
    active_sessions_count: Optional[int] = None  # Number of active sessions
    session_start: Optional[str] = None  # Backend timestamp - single source of truth


class TokenData(BaseModel):
    """Schema for token data"""
    user_id: Optional[int] = None


class PasswordChange(BaseModel):
    """Schema for password change"""
    current_password: str = Field(..., min_length=6, max_length=100)
    new_password: str = Field(..., min_length=6, max_length=100)


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for reset password with code"""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6, max_length=100)


class UserAnalysisStats(BaseModel):
    """Schema for user analysis statistics"""
    total_analyses: int = 0
    pending_analyses: int = 0
    in_progress_analyses: int = 0
    completed_analyses: int = 0
    average_risk_score: Optional[float] = None


class UserDetailedProfile(UserResponse):
    """Schema for detailed user profile with activity history and analysis stats"""
    analysis_stats: UserAnalysisStats

    # Inherits field_serializer from UserResponse
    class Config:
        from_attributes = True
