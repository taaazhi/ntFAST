from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session, defer
from typing import List, Optional
import os
import shutil
from datetime import datetime
from pathlib import Path
from app.core.database import get_db
from app.core.config import settings
from app.models.analysis import Analysis
from app.models.user import User
from app.schemas.analysis import AnalysisCreate, AnalysisUpdate, AnalysisResponse, AnalysisListItem, AnalysisFileUploadResponse
from app.services.auth_service import get_current_user

router = APIRouter()


# IMPORTANT: Specific routes MUST come BEFORE parametrized routes like /{analysis_id}
# Otherwise FastAPI treats "upload" as an analysis_id
@router.post("/upload", response_model=AnalysisFileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file_for_analysis(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a bank statement file (PDF, CSV, XLSX, XLS) for ML analysis
    Creates a new Analysis and triggers file parsing
    """
    # Validate file extension
    file_extension = file.filename.split(".")[-1].lower()
    if file_extension not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_extension}' not allowed. Allowed types: {', '.join(settings.ALLOWED_FILE_TYPES)}"
        )

    # Read file to check size
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size ({file_size} bytes) exceeds maximum allowed size ({settings.MAX_FILE_SIZE} bytes)"
        )

    # Reset file pointer
    await file.seek(0)

    # Create uploads directory if it doesn't exist
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = upload_dir / safe_filename

    # Save file to disk
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    # Create Analysis record in database
    db_analysis = Analysis(
        analyst_id=current_user.id,
        file_name=file.filename,
        file_path=str(file_path),
        file_type=file_extension,
        file_size=file_size,
        status="pending"  # Will change to 'parsing' when Celery task starts
    )

    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)

    # Queue file processing task asynchronously
    from app.tasks.file_processing_tasks import process_file_task

    try:
        # Submit task to Celery queue
        task = process_file_task.delay(db_analysis.id, str(file_path))

        return AnalysisFileUploadResponse(
            id=db_analysis.id,
            file_name=db_analysis.file_name,
            file_type=db_analysis.file_type,
            file_size=db_analysis.file_size,
            status=db_analysis.status,
            message=f"File uploaded successfully. Processing started. Task ID: {task.id}"
        )
    except Exception as e:
        # If task submission fails, update status and return error
        db_analysis.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File uploaded but task submission failed: {str(e)}"
        )


@router.get("/")
async def get_analyses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = None,
    subject_id: Optional[int] = None,
    sort_by: Optional[str] = Query("created_at", pattern="^(created_at|risk_score|status|id|total_transactions)$"),
    sort_order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of analyses with filters, sorting and search.
    Heavy JSON columns (fraud_report, analytics_result, fraud_red_flags, fraud_recommendations)
    are deferred to avoid transferring ~500KB per record."""
    query = db.query(Analysis).options(
        defer(Analysis.fraud_report),
        defer(Analysis.analytics_result),
        defer(Analysis.fraud_red_flags),
        defer(Analysis.fraud_recommendations),
        defer(Analysis.parsed_account_info),
        defer(Analysis.ai_narrative),
        defer(Analysis.ai_risk_assessment),
        defer(Analysis.ml_results),
    )

    if status_filter:
        query = query.filter(Analysis.status == status_filter)
    if subject_id:
        query = query.filter(Analysis.subject_id == subject_id)

    # Risk level filter
    if risk_level == "low":
        query = query.filter(Analysis.risk_score <= 3)
    elif risk_level == "medium":
        query = query.filter(Analysis.risk_score > 3, Analysis.risk_score <= 6)
    elif risk_level == "high":
        query = query.filter(Analysis.risk_score > 6)

    # Date range filter
    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.filter(Analysis.created_at >= from_date)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid date_from format: '{date_from}'. Use ISO format: YYYY-MM-DD")
    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to)
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.filter(Analysis.created_at <= to_date)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid date_to format: '{date_to}'. Use ISO format: YYYY-MM-DD")

    # Search by file_name or account_owner
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Analysis.file_name.ilike(search_term)) |
            (Analysis.account_owner.ilike(search_term))
        )

    # Analysts can only see their own analyses
    if current_user.role == "analyst":
        query = query.filter(Analysis.analyst_id == current_user.id)

    # Sorting
    sort_column = getattr(Analysis, sort_by, Analysis.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    analyses = query.offset(skip).limit(limit).all()
    # Return lightweight dicts — exclude heavy JSON fields (fraud_report ~400KB, analytics_result ~100KB)
    return [
        {
            "id": a.id, "subject_id": a.subject_id, "analyst_id": a.analyst_id,
            "status": a.status, "risk_score": a.risk_score,
            "analyst_notes": a.analyst_notes, "conclusion": a.conclusion,
            "file_name": a.file_name, "file_type": a.file_type, "file_size": a.file_size,
            "bank_type": a.bank_type, "bank_name": a.bank_name, "bank_confidence": a.bank_confidence,
            "account_owner": a.account_owner, "account_number": a.account_number,
            "account_currency": a.account_currency or "KZT",
            "total_transactions": a.total_transactions or 0,
            "total_income": a.total_income, "total_expense": a.total_expense,
            "suspicious_count": a.suspicious_count or 0,
            "fraud_composite_score": a.fraud_composite_score,
            "fraud_risk_level": a.fraud_risk_level,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        }
        for a in analyses
    ]


@router.post("/", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    analysis: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new analysis"""
    db_analysis = Analysis(
        **analysis.model_dump(),
        analyst_id=current_user.id
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    return db_analysis


@router.get("/stats")
async def get_overall_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall system statistics for dashboard"""
    from app.models.transaction import Transaction
    from app.models.subject import Subject
    from sqlalchemy import func

    # Get analyses count and stats
    query = db.query(Analysis)

    # Analysts can only see their own analyses
    if current_user.role == "analyst":
        query = query.filter(Analysis.analyst_id == current_user.id)

    total_analyses = query.count()
    completed_analyses = query.filter(Analysis.status == "completed").count()

    completion_rate = (completed_analyses / total_analyses * 100) if total_analyses > 0 else 0

    # Get subjects count
    total_subjects = db.query(Subject).count()

    # Enhanced stats: financial aggregates using fraud_composite_score (0-100)
    base_query = db.query(Analysis)
    if current_user.role == "analyst":
        base_query = base_query.filter(Analysis.analyst_id == current_user.id)

    financial = base_query.with_entities(
        func.avg(Analysis.fraud_composite_score).label('avg_composite'),
        func.avg(Analysis.risk_score).label('avg_risk'),
        func.sum(Analysis.total_income).label('sum_income'),
        func.sum(Analysis.total_expense).label('sum_expense'),
        func.sum(Analysis.total_transactions).label('sum_transactions'),
    ).first()

    # Risk counts based on fraud_composite_score (0-100%)
    # Low: 0-30, Medium: 30-60, High: 60+
    completed_query = base_query.filter(Analysis.status == "completed")
    low_risk_count = completed_query.filter(
        (Analysis.fraud_composite_score <= 30) | (Analysis.fraud_composite_score.is_(None))
    ).count()
    medium_risk_count = completed_query.filter(
        Analysis.fraud_composite_score > 30, Analysis.fraud_composite_score <= 60
    ).count()
    high_risk_count = completed_query.filter(
        Analysis.fraud_composite_score > 60
    ).count()

    failed_count = base_query.filter(Analysis.status == "failed").count()
    pending_count = base_query.filter(Analysis.status == "pending").count()
    in_progress_count = base_query.filter(
        Analysis.status.in_(["parsing", "analyzing", "in_progress"])
    ).count()

    success_rate = round(completed_analyses / total_analyses * 100, 1) if total_analyses > 0 else 0

    # Monthly breakdown for chart (last 6 months)
    from sqlalchemy import extract, case
    six_months_ago = datetime.utcnow().replace(day=1) - __import__('datetime').timedelta(days=180)

    monthly_raw = base_query.filter(
        Analysis.created_at >= six_months_ago
    ).with_entities(
        func.date_trunc('month', Analysis.created_at).label('month'),
        func.count(Analysis.id).label('total'),
        func.count(case(
            (Analysis.status == 'completed', 1),
        )).label('completed'),
        func.count(case(
            (Analysis.fraud_composite_score > 60, 1),
        )).label('high_risk'),
        func.avg(Analysis.fraud_composite_score).label('avg_risk'),
    ).group_by('month').order_by('month').all()

    monthly_chart = []
    for row in monthly_raw:
        month_dt = row.month
        if month_dt:
            monthly_chart.append({
                "month": month_dt.strftime("%Y-%m"),
                "month_label": month_dt.strftime("%b %Y"),
                "total": row.total,
                "completed": row.completed,
                "high_risk": row.high_risk,
                "avg_risk": round(float(row.avg_risk or 0), 1),
            })

    return {
        "total_analyses": total_analyses,
        "completed_analyses": completed_analyses,
        "high_risk_count": high_risk_count,
        "medium_risk_count": medium_risk_count,
        "low_risk_count": low_risk_count,
        "completion_rate": round(completion_rate, 2),
        "total_subjects": total_subjects,
        "stats_generated_at": datetime.utcnow().isoformat(),
        # Enhanced fields
        "avg_risk_score": round(float(financial.avg_composite or financial.avg_risk or 0), 1),
        "total_income_sum": float(financial.sum_income or 0),
        "total_expense_sum": float(financial.sum_expense or 0),
        "total_transactions_sum": int(financial.sum_transactions or 0),
        "failed_count": failed_count,
        "pending_count": pending_count,
        "in_progress_count": in_progress_count,
        "success_rate": success_rate,
        "monthly_chart": monthly_chart,
    }


@router.post("/batch-delete", status_code=status.HTTP_200_OK)
async def batch_delete_analyses(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete multiple analyses at once (admin or owner)"""
    ids = payload.get("ids", [])
    if not ids or not isinstance(ids, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide a list of analysis IDs in 'ids' field"
        )

    deleted = 0
    errors = []
    for analysis_id in ids:
        db_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not db_analysis:
            errors.append(f"Analysis {analysis_id} not found")
            continue
        if current_user.role != "admin" and db_analysis.analyst_id != current_user.id:
            errors.append(f"Not authorized to delete analysis {analysis_id}")
            continue
        try:
            db.delete(db_analysis)
            db.flush()
            deleted += 1
        except Exception as e:
            db.rollback()
            errors.append(f"Failed to delete analysis {analysis_id}: {str(e)}")

    if deleted > 0:
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to commit batch delete: {str(e)}"
            )
    return {"deleted": deleted, "errors": errors}


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get analysis by ID"""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    # Analysts can only view their own analyses
    if current_user.role == "analyst" and analysis.analyst_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this analysis"
        )

    return analysis


@router.put("/{analysis_id}", response_model=AnalysisResponse)
async def update_analysis(
    analysis_id: int,
    analysis_update: AnalysisUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update analysis"""
    db_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not db_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    # Analysts can only update their own analyses
    if current_user.role == "analyst" and db_analysis.analyst_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this analysis"
        )

    update_data = analysis_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_analysis, field, value)

    db.commit()
    db.refresh(db_analysis)
    return db_analysis


@router.delete("/{analysis_id}", status_code=status.HTTP_200_OK)
async def delete_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete analysis (admin or owner)"""
    import traceback

    db_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not db_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    # Allow admin or the analyst who created the analysis
    if current_user.role != "admin" and db_analysis.analyst_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own analyses"
        )

    try:
        # Cascade handles transaction deletion via relationship config
        db.delete(db_analysis)
        db.commit()
        return {"ok": True, "deleted_id": analysis_id}
    except Exception as e:
        db.rollback()
        error_detail = traceback.format_exc()
        print(f"[DELETE ERROR] Analysis {analysis_id}: {error_detail}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete analysis: {str(e)}"
        )


@router.get("/{analysis_id}/transactions")
async def get_analysis_transactions(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all transactions for an analysis"""
    from app.models.transaction import Transaction
    from app.services.file_processing_service import FileProcessingService

    # Check if analysis exists and user has access
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    # Analysts can only view their own analyses
    if current_user.role == "analyst" and analysis.analyst_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this analysis"
        )

    # Get transactions
    processing_service = FileProcessingService(db)
    transactions = processing_service.get_transactions_by_analysis(analysis_id)

    # Serialize SQLAlchemy objects to dicts
    tx_list = []
    for tx in transactions:
        tx_list.append({
            "id": tx.id,
            "transaction_date": tx.transaction_date.isoformat() if tx.transaction_date else None,
            "amount": float(tx.amount) if tx.amount is not None else 0,
            "transaction_type": tx.transaction_type,
            "description": tx.description,
            "category": tx.category,
            "subcategory": tx.subcategory,
            "currency": tx.currency or "KZT",
            "original_amount": float(tx.original_amount) if tx.original_amount is not None else None,
            "original_currency": tx.original_currency,
            "counterparty_name": tx.counterparty_name,
            "is_suspicious": tx.is_suspicious,
            "risk_score": tx.risk_score,
        })

    return {
        "analysis_id": analysis_id,
        "total_transactions": len(tx_list),
        "transactions": tx_list
    }


@router.get("/{analysis_id}/stats")
async def get_analysis_stats(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get transaction statistics for an analysis"""
    from app.services.file_processing_service import FileProcessingService

    # Check if analysis exists and user has access
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    # Analysts can only view their own analyses
    if current_user.role == "analyst" and analysis.analyst_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this analysis"
        )

    # Get stats
    processing_service = FileProcessingService(db)
    stats = processing_service.get_transaction_stats(analysis_id)

    return stats


@router.get("/task/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of a Celery task"""
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app

    task = AsyncResult(task_id, app=celery_app)

    return {
        "task_id": task_id,
        "status": task.state,
        "result": task.result if task.ready() else None,
        "info": task.info
    }
