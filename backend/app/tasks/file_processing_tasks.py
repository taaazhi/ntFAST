"""
Celery Tasks for File Processing
Асинхронные задачи для обработки файлов
"""
import os
import glob
from celery import Task
from typing import Dict, Any
from datetime import datetime, timedelta
import logging

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.analysis import Analysis
from app.models.transaction import Transaction as TransactionModel
from app.services.file_processing_service import FileProcessingService

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """
    Base task with database session management
    Базовая задача с управлением сессией БД
    """
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Close database session after task completes"""
        if self._db is not None:
            self._db.close()
            self._db = None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Close and rollback database session on task failure"""
        if self._db is not None:
            try:
                self._db.rollback()
                self._db.close()
            except Exception:
                pass
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask, name="process_file_task")
def process_file_task(self, analysis_id: int, file_path: str) -> Dict[str, Any]:
    """
    Асинхронная задача для обработки загруженного файла

    Args:
        analysis_id: ID анализа
        file_path: Путь к файлу

    Returns:
        Словарь с результатами обработки
    """
    logger.info(f"Starting file processing for analysis_id={analysis_id}, file_path={file_path}")

    try:
        # Create processing service
        processing_service = FileProcessingService(self.db)

        # Process file
        result = processing_service.process_file(analysis_id, file_path)

        logger.info(f"File processing completed for analysis_id={analysis_id}. Total transactions: {result.get('total_transactions', 0)}")

        return result

    except Exception as e:
        logger.error(f"File processing failed for analysis_id={analysis_id}: {str(e)}", exc_info=True)

        # Update analysis status to failed
        try:
            analysis = self.db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = "failed"
                self.db.commit()
                # Persistent notification so the user sees the failure in the bell icon
                # next time they open the app — Celery runs in background so toast won't fire.
                # i18n keys (frontend renders via t() with `data` params).
                try:
                    from app.services.notification_service import notify
                    err_msg = str(e)[:300] if str(e) else ""
                    notify(
                        self.db,
                        user_id=analysis.analyst_id,
                        kind="analysis_failed",
                        severity="error",
                        title="notifications.kind.analysis_failed.title",
                        body="notifications.kind.analysis_failed.body" if err_msg else None,
                        data={
                            "filename": analysis.file_name or f"#{analysis.id}",
                            "analysis_id": analysis.id,
                            "error": err_msg,
                        },
                    )
                except Exception:
                    pass
        except Exception as db_error:
            logger.error(f"Failed to update analysis status: {str(db_error)}")

        # Re-raise exception for Celery retry mechanism
        raise


@celery_app.task(bind=True, base=DatabaseTask, name="ml_analysis_task")
def ml_analysis_task(self, analysis_id: int) -> Dict[str, Any]:
    """
    Rule-Based антифрод-анализ транзакций через FraudEngine.

    Workflow:
    1. Загрузить Analysis + транзакции из БД
    2. Конвертировать DB Transaction → fraud engine Transaction dataclass
    3. Создать AccountInfo из данных анализа
    4. Запустить FraudEngine.full_analysis()
    5. Сохранить результаты в Analysis
    """
    logger.info(f"Starting fraud analysis for analysis_id={analysis_id}")

    try:
        # 1. Загрузить анализ
        analysis = self.db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        # Загрузить транзакции из БД
        db_transactions = self.db.query(TransactionModel).filter(
            TransactionModel.analysis_id == analysis_id
        ).order_by(TransactionModel.transaction_date).all()

        if not db_transactions:
            logger.warning(f"No transactions found for analysis_id={analysis_id}")
            analysis.ml_processed = True
            analysis.ml_results = {"message": "No transactions to analyze"}
            self.db.commit()
            return {"success": True, "analysis_id": analysis_id, "message": "No transactions"}

        # Обновить статус
        analysis.status = "analyzing"
        self.db.commit()

        # 2. Конвертировать DB транзакции → fraud engine Transaction dataclass
        from app.services.bank_analyzer.base_parser import (
            Transaction as FraudTransaction,
            TransactionType,
            CounterpartyType,
            AccountInfo,
        )

        # Маппинг типов транзакций из БД в enum
        TX_TYPE_MAP = {
            "incoming": TransactionType.INCOME,
            "outgoing": TransactionType.EXPENSE,
            "transfer": TransactionType.TRANSFER_OUT,
            "transfer_in": TransactionType.TRANSFER_IN,
            "transfer_out": TransactionType.TRANSFER_OUT,
            "income": TransactionType.INCOME,
            "expense": TransactionType.EXPENSE,
            "withdrawal": TransactionType.WITHDRAWAL,
            "deposit": TransactionType.DEPOSIT,
            "fee": TransactionType.FEE,
            "refund": TransactionType.REFUND,
            "crypto_buy": TransactionType.CRYPTO_BUY,
            "crypto_sell": TransactionType.CRYPTO_SELL,
        }

        CP_TYPE_MAP = {
            "person": CounterpartyType.PERSON,
            "merchant": CounterpartyType.MERCHANT,
            "bank": CounterpartyType.BANK,
            "atm": CounterpartyType.ATM,
            "government": CounterpartyType.GOVERNMENT,
        }

        fraud_transactions = []
        for t in db_transactions:
            tx_type = TX_TYPE_MAP.get(
                (t.transaction_type or "").lower(),
                TransactionType.OTHER
            )
            cp_type = CP_TYPE_MAP.get(
                (t.counterparty_type or "").lower(),
                CounterpartyType.UNKNOWN
            )

            fraud_transactions.append(FraudTransaction(
                date=t.transaction_date or datetime.now(),
                amount=float(t.amount or 0),
                type=tx_type,
                description=t.description or "",
                category=t.category or "",
                subcategory=t.subcategory or "",
                currency=t.currency or "KZT",
                original_amount=float(t.original_amount) if t.original_amount else None,
                original_currency=t.original_currency,
                exchange_rate=t.exchange_rate,
                counterparty=t.counterparty_name,
                counterparty_type=cp_type,
                merchant_name=t.merchant_name,
                merchant_type=t.merchant_type,
                is_blocked=bool(t.is_blocked),
                is_deposit_operation=bool(t.is_deposit_operation),
                is_pension_benefit=bool(t.is_pension_benefit),
                is_bank_transfer=bool(t.is_bank_transfer),
                is_atm=bool(t.is_atm),
                is_salary=bool(t.is_salary),
                is_cash_operation=bool(t.is_cash_operation),
                source_row=t.source_row,
            ))

        # 3. Создать AccountInfo
        account_info = AccountInfo(
            owner=analysis.account_owner or "",
            account_number=analysis.account_number or "",
            currency=analysis.account_currency or "KZT",
            bank_name=analysis.bank_name or "",
            period_start=analysis.period_start,
            period_end=analysis.period_end,
            balance_start=float(analysis.balance_start) if analysis.balance_start else 0.0,
            balance_end=float(analysis.balance_end) if analysis.balance_end else 0.0,
        )

        # 4. Запустить FraudEngine
        from app.services.fraud.engine import FraudEngine

        engine = FraudEngine()
        report = engine.full_analysis(fraud_transactions, account_info)

        # 5. Сохранить результаты
        analysis.fraud_composite_score = report.composite_score
        analysis.fraud_risk_level = report.risk_level
        analysis.fraud_report = report.to_dict()
        analysis.fraud_red_flags = report.red_flags
        analysis.fraud_recommendations = report.recommendations

        # Сохранить результаты отдельных модулей
        analysis.velocity_result = report.velocity.to_dict()
        analysis.graph_result = report.graph.to_dict()
        analysis.behavioral_result = report.behavioral.to_dict()
        analysis.structuring_result = report.structuring.to_dict()
        analysis.cross_reference_result = report.cross_reference.to_dict()
        analysis.merchant_risk_result = report.merchant_risk.to_dict()

        # Сохранить результаты новых модулей v4
        if report.night_transactions:
            analysis.night_transactions_result = report.night_transactions.to_dict()
        if report.duplicate_payments:
            analysis.duplicate_payments_result = report.duplicate_payments.to_dict()
        if report.round_amounts:
            analysis.round_amounts_result = report.round_amounts.to_dict()
        if report.profile_mismatch:
            analysis.profile_mismatch_result = report.profile_mismatch.to_dict()

        # Обновить risk_score (0-10 шкала, как в bank_analysis.py)
        analysis.risk_score = min(10, int(report.composite_score / 10))
        analysis.ml_processed = True
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()

        # Обновить suspicious_count на основе результатов
        analysis.suspicious_count = len(report.red_flags)

        self.db.commit()

        logger.info(
            f"Fraud analysis completed for analysis_id={analysis_id}: "
            f"score={report.composite_score:.1f}, level={report.risk_level}, "
            f"flags={len(report.red_flags)}"
        )

        return {
            "success": True,
            "analysis_id": analysis_id,
            "composite_score": report.composite_score,
            "risk_level": report.risk_level,
            "red_flags_count": len(report.red_flags),
        }

    except Exception as e:
        logger.error(f"Fraud analysis failed for analysis_id={analysis_id}: {str(e)}", exc_info=True)

        # Обновить статус на failed
        try:
            analysis = self.db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.ml_results = {"error": str(e)}
                self.db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update analysis status: {str(db_error)}")

        raise


@celery_app.task(name="cleanup_old_files_task")
def cleanup_old_files_task(max_age_days: int = 30) -> Dict[str, Any]:
    """
    Периодическая задача для очистки старых загруженных файлов.

    Удаляет файлы из uploads/ старше max_age_days дней
    и обновляет записи в БД (убирает file_path).
    """
    logger.info(f"Starting cleanup of files older than {max_age_days} days")

    from app.core.config import settings

    upload_dir = settings.UPLOAD_DIR
    if not os.path.exists(upload_dir):
        return {"success": True, "message": "Upload directory does not exist", "deleted": 0}

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted_count = 0
    errors = []

    # Найти все файлы в uploads/
    for filepath in glob.glob(os.path.join(upload_dir, "**", "*"), recursive=True):
        if not os.path.isfile(filepath):
            continue

        try:
            file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if file_mtime < cutoff:
                os.remove(filepath)
                deleted_count += 1
                logger.info(f"Deleted old file: {filepath} (modified: {file_mtime})")
        except OSError as e:
            errors.append(f"{filepath}: {e}")
            logger.warning(f"Failed to delete {filepath}: {e}")

    # Очистить пустые подпапки
    for dirpath, dirnames, filenames in os.walk(upload_dir, topdown=False):
        if dirpath != upload_dir and not filenames and not dirnames:
            try:
                os.rmdir(dirpath)
            except OSError:
                pass

    logger.info(f"Cleanup completed: deleted {deleted_count} files, {len(errors)} errors")

    return {
        "success": True,
        "deleted": deleted_count,
        "errors": errors[:10],  # Максимум 10 ошибок в ответе
        "cutoff_date": cutoff.isoformat(),
    }
