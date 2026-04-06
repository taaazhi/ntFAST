from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class AnalysisBase(BaseModel):
    """Base analysis schema"""
    analyst_notes: Optional[str] = None
    conclusion: Optional[str] = None


class AnalysisCreate(BaseModel):
    """
    Schema for analysis creation (from file upload)
    subject_id is optional - will be auto-generated from transactions
    """
    subject_id: Optional[int] = Field(None, description="Subject ID (optional, auto-generated)")
    analyst_notes: Optional[str] = None


class AnalysisUpdate(BaseModel):
    """Schema for analysis update"""
    subject_id: Optional[int] = None
    status: Optional[str] = Field(None, pattern="^(pending|parsing|analyzing|completed|failed)$")
    risk_score: Optional[int] = Field(None, ge=0, le=100)
    analyst_notes: Optional[str] = None
    conclusion: Optional[str] = None


class AnalysisFileUploadResponse(BaseModel):
    """Schema for file upload response"""
    id: int
    file_name: str
    file_type: str
    file_size: int
    status: str
    message: str

    class Config:
        from_attributes = True


class AnalysisListItem(AnalysisBase):
    """Lightweight schema for analysis list — NO heavy JSON fields (fraud_report, analytics_result).
    This reduces /analyses/ response from ~800KB to ~5KB for typical datasets."""
    id: int
    subject_id: Optional[int] = None
    analyst_id: int
    status: str
    risk_score: int

    # File information
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None

    # Bank info
    bank_type: Optional[str] = None
    bank_name: Optional[str] = None
    bank_confidence: Optional[float] = None
    account_owner: Optional[str] = None
    account_number: Optional[str] = None
    account_currency: Optional[str] = "KZT"

    # Statistics
    total_transactions: int = 0
    total_income: Optional[float] = None
    total_expense: Optional[float] = None
    suspicious_count: int = 0

    # Fraud summary (lightweight — score + level only, no full report)
    fraud_composite_score: Optional[float] = None
    fraud_risk_level: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalysisResponse(AnalysisBase):
    """Full schema for single analysis detail view — includes all heavy JSON fields."""
    id: int
    subject_id: Optional[int] = None
    analyst_id: int
    status: str
    risk_score: int

    # File information
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None

    # Bank info
    bank_type: Optional[str] = None
    bank_name: Optional[str] = None
    bank_confidence: Optional[float] = None
    account_owner: Optional[str] = None
    account_number: Optional[str] = None
    account_currency: Optional[str] = "KZT"

    # Statistics
    total_transactions: int = 0
    total_amount: int = 0
    total_income: Optional[float] = None
    total_expense: Optional[float] = None
    suspicious_count: int = 0
    anomaly_count: int = 0
    high_risk_count: int = 0

    # Fraud results (FULL)
    fraud_composite_score: Optional[float] = None
    fraud_risk_level: Optional[str] = None
    fraud_report: Optional[Dict[str, Any]] = None
    fraud_red_flags: Optional[list] = None
    fraud_recommendations: Optional[list] = None

    # Full report data (for reconstructing BankAnalysisReport from DB)
    analytics_result: Optional[Dict[str, Any]] = None
    parsed_account_info: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalysisListResponse(BaseModel):
    """Schema for paginated analysis list"""
    analyses: list[AnalysisResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AnalysisStatsResponse(BaseModel):
    """Schema for analysis statistics"""
    total_analyses: int
    pending_count: int
    parsing_count: int
    analyzing_count: int
    completed_count: int
    failed_count: int
    avg_risk_score: float
    total_transactions_analyzed: int
    total_suspicious: int
    total_anomalies: int
