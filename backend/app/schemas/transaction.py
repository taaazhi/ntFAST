from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal


class TransactionBase(BaseModel):
    """Base transaction schema"""
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(default="KZT", max_length=3, description="Currency code (KZT, USD, EUR, etc.)")
    transaction_type: str = Field(..., pattern="^(incoming|outgoing|transfer)$", description="Transaction type")
    transaction_date: datetime = Field(..., description="Transaction date and time")

    # Counterparty information
    counterparty_name: Optional[str] = Field(None, max_length=500, description="Counterparty name")
    counterparty_account: Optional[str] = Field(None, max_length=100, description="Counterparty account number")
    counterparty_bank: Optional[str] = Field(None, max_length=200, description="Counterparty bank name")
    counterparty_iin_bin: Optional[str] = Field(None, max_length=12, description="Counterparty IIN/BIN")

    # Description and category
    description: Optional[str] = Field(None, description="Full transaction description")
    category: Optional[str] = Field(None, max_length=50, description="Transaction category")
    payment_purpose: Optional[str] = Field(None, description="Payment purpose/details")


class TransactionCreate(TransactionBase):
    """Schema for creating a transaction (from file upload)"""
    analysis_id: int = Field(..., description="Analysis ID this transaction belongs to")
    subject_id: Optional[int] = Field(None, description="Subject ID (can be null until auto-generated)")

    # Source tracking
    source_file: Optional[str] = Field(None, max_length=255, description="Source file name")
    source_row: Optional[int] = Field(None, description="Row number in source file")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw data from source file (for re-analysis)")

    # Initial flags
    is_suspicious: bool = Field(default=False, description="Manual suspicious flag")


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction"""
    subject_id: Optional[int] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=3)
    transaction_type: Optional[str] = Field(None, pattern="^(incoming|outgoing|transfer)$")
    transaction_date: Optional[datetime] = None

    # Counterparty updates
    counterparty_name: Optional[str] = Field(None, max_length=500)
    counterparty_account: Optional[str] = Field(None, max_length=100)
    counterparty_bank: Optional[str] = Field(None, max_length=200)
    counterparty_iin_bin: Optional[str] = Field(None, max_length=12)

    # Description updates
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    payment_purpose: Optional[str] = None

    # Manual flags
    is_suspicious: Optional[bool] = None


class TransactionResponse(BaseModel):
    """
    Schema for transaction response.
    NOTE: Does NOT inherit from TransactionBase to avoid validation issues
    (e.g. `amount > 0` constraint causing ResponseValidationError on zero-amount rows).
    All fields are optional with defaults so that missing DB columns never cause CORS-masked errors.
    """
    id: int
    analysis_id: Optional[int] = None
    subject_id: Optional[int] = None

    # Core transaction fields
    amount: Optional[Decimal] = None
    currency: Optional[str] = "KZT"
    transaction_type: Optional[str] = None
    transaction_date: Optional[datetime] = None

    # Multicurrency
    original_amount: Optional[Decimal] = None
    original_currency: Optional[str] = None
    exchange_rate: Optional[float] = None

    # Counterparty
    counterparty_name: Optional[str] = None
    counterparty_account: Optional[str] = None
    counterparty_bank: Optional[str] = None
    counterparty_iin_bin: Optional[str] = None
    counterparty_type: Optional[str] = None

    # Description / category
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    payment_purpose: Optional[str] = None

    # Merchant
    merchant_name: Optional[str] = None
    merchant_type: Optional[str] = None
    merchant_risk_level: Optional[str] = None

    # Transaction flags
    is_blocked: bool = False
    is_deposit_operation: bool = False
    is_pension_benefit: bool = False
    is_bank_transfer: bool = False
    is_atm: bool = False
    is_salary: bool = False
    is_cash_operation: bool = False

    # Flags
    is_suspicious: bool = False
    is_anomaly: bool = False

    # Risk analysis results
    anomaly_score: Optional[float] = None
    risk_score: int = 0
    risk_factors: Optional[Dict[str, Any]] = None

    # Source tracking
    source_file: Optional[str] = None
    source_page: Optional[int] = None
    source_row: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    """Schema for paginated transaction list"""
    transactions: list[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TransactionFilterParams(BaseModel):
    """Schema for filtering transactions"""
    analysis_id: Optional[int] = None
    subject_id: Optional[int] = None
    transaction_type: Optional[str] = Field(None, pattern="^(incoming|outgoing|transfer)$")
    is_suspicious: Optional[bool] = None
    is_anomaly: Optional[bool] = None
    min_amount: Optional[Decimal] = Field(None, ge=0)
    max_amount: Optional[Decimal] = Field(None, ge=0)
    min_risk_score: Optional[int] = Field(None, ge=0, le=100)
    max_risk_score: Optional[int] = Field(None, ge=0, le=100)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    category: Optional[str] = None
    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=1000)

    # Sorting
    sort_by: str = Field(default="transaction_date", pattern="^(transaction_date|amount|risk_score|created_at)$")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class TransactionStatsResponse(BaseModel):
    """Schema for transaction statistics"""
    total_transactions: int
    total_amount: Decimal
    incoming_count: int
    outgoing_count: int
    transfer_count: int
    suspicious_count: int
    anomaly_count: int
    avg_risk_score: float
    high_risk_count: int  # risk_score >= 70
    medium_risk_count: int  # 30 <= risk_score < 70
    low_risk_count: int  # risk_score < 30
