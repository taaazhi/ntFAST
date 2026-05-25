from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.core.database import get_db
from app.models.transaction import Transaction
from app.models.analysis import Analysis
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionUpdate, TransactionResponse
from app.services.auth_service import get_current_user

router = APIRouter()


def _check_transaction_ownership(db: Session, transaction: Transaction, current_user: User) -> None:
    """Verify the transaction's analysis belongs to the current user (or user is admin).

    Uses the eager-loaded `transaction.analysis` if present (loaded via joinedload),
    falling back to an explicit lookup only when needed.
    """
    if current_user.role == "admin":
        return
    # Prefer eager-loaded relationship to avoid extra round-trip
    analysis = getattr(transaction, "analysis", None)
    if analysis is None:
        analysis = db.query(Analysis).filter(Analysis.id == transaction.analysis_id).first()
    if not analysis or analysis.analyst_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this transaction",
        )


@router.get("/", response_model=List[TransactionResponse])
async def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    subject_id: Optional[int] = None,
    is_suspicious: Optional[bool] = None,
    transaction_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of transactions with optional filters"""
    query = db.query(Transaction)

    # Non-admin users can only see transactions from their own analyses
    if current_user.role != "admin":
        owned_analysis_ids = db.query(Analysis.id).filter(
            Analysis.analyst_id == current_user.id,
        )
        query = query.filter(Transaction.analysis_id.in_(owned_analysis_ids))

    if subject_id:
        query = query.filter(Transaction.subject_id == subject_id)
    if is_suspicious is not None:
        query = query.filter(Transaction.is_suspicious == is_suspicious)
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)

    transactions = query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()
    return transactions


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new transaction"""
    # Verify the target analysis belongs to current user
    if transaction.analysis_id:
        analysis = db.query(Analysis).filter(Analysis.id == transaction.analysis_id).first()
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found",
            )
        if current_user.role != "admin" and analysis.analyst_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to add transactions to this analysis",
            )

    db_transaction = Transaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get transaction by ID"""
    transaction = (
        db.query(Transaction)
        .options(joinedload(Transaction.analysis))
        .filter(Transaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    _check_transaction_ownership(db, transaction, current_user)
    return transaction


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update transaction"""
    db_transaction = (
        db.query(Transaction)
        .options(joinedload(Transaction.analysis))
        .filter(Transaction.id == transaction_id)
        .first()
    )
    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    _check_transaction_ownership(db, db_transaction, current_user)

    update_data = transaction_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_transaction, field, value)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(db_transaction)
    return db_transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete transaction (admin or owner)"""
    db_transaction = (
        db.query(Transaction)
        .options(joinedload(Transaction.analysis))
        .filter(Transaction.id == transaction_id)
        .first()
    )
    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    _check_transaction_ownership(db, db_transaction, current_user)

    try:
        db.delete(db_transaction)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return None
