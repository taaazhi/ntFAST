from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime
from typing import Optional


class SubjectBase(BaseModel):
    """Base subject schema"""
    name: str = Field(..., min_length=1, max_length=200)
    iin_bin: Optional[str] = Field(None, min_length=12, max_length=12, pattern="^[0-9]{12}$")
    type: str = Field(..., pattern="^(individual|legal_entity|account_owner)$")
    phone_number: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(None, max_length=500)


class SubjectCreate(SubjectBase):
    """Schema for subject creation"""
    risk_level: int = Field(default=0, ge=0, le=10)
    status: str = Field(default="active", pattern="^(active|suspended|blocked)$")


class SubjectUpdate(BaseModel):
    """Schema for subject update"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[str] = Field(None, pattern="^(individual|legal_entity)$")
    risk_level: Optional[int] = Field(None, ge=0, le=10)
    status: Optional[str] = Field(None, pattern="^(active|suspended|blocked)$")
    phone_number: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(None, max_length=500)


class SubjectResponse(SubjectBase):
    """Schema for subject response"""
    id: int
    risk_level: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
