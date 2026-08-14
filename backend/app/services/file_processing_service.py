"""
File Processing Service
Сервис для обработки загруженных банковских выписок
"""
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.transaction import Transaction
from app.services.analysis_persistence import get_file_extension, save_analysis_to_db
from app.services.bank_analyzer.analyzer import BankAnalyzer
from app.services.bank_analyzer.base_parser import StatementParsingError

logger = logging.getLogger(__name__)


class FileProcessingService:
    """
    Service for processing uploaded bank statement files
    Парсинг файлов и сохранение транзакций в БД
    """

    def __init__(self, db: Session):
        self.db = db

    def process_file(
        self,
        analysis_id: int,
        file_path: str,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Разобрать загруженный файл и сохранить полный результат анализа.

        Args:
            analysis_id: ID уже созданной записи Analysis
            file_path: путь к файлу
            on_progress: колбэк прогресса (step, percent, message, detail)

        Returns:
            Словарь с итогами обработки

        Raises:
            StatementParsingError: файл прочитан, но транзакций в нём не найдено
            ValueError: прочие ошибки обработки
        """
        # Get analysis from DB
        analysis = self.db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise ValueError(f"Analysis with ID {analysis_id} not found")

        # Update status to parsing
        analysis.status = "parsing"
        self.db.commit()

        analyst_id = analysis.analyst_id
        file_name = analysis.file_name or os.path.basename(file_path)
        file_ext = get_file_extension(file_name) or get_file_extension(file_path)
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = analysis.file_size or 0

        try:
            # Единый конвейер для всех форматов: определение банка → парсер →
            # категоризация → аналитика → антифрод. Раньше здесь была развилка
            # (CSV шёл через SmartBankStatementParser, остальное через
            # ParserFactory), и эти ветки давали разный набор полей и разный
            # результат для одного и того же файла.
            logger.info(f"Analysing {file_ext or '?'} file through BankAnalyzer: {file_path}")
            analyzer = BankAnalyzer(file_path, on_progress=on_progress)
            result = analyzer.analyze()

            saved_id = save_analysis_to_db(
                db=self.db,
                result=result,
                filename=file_name,
                file_ext=file_ext,
                file_size=file_size,
                user_id=analyst_id,
                analysis_id=analysis_id,
            )
            if saved_id is None:
                raise ValueError("Не удалось сохранить результат анализа")

            summary = result.get("summary", {})
            fraud = result.get("fraud_report") or {}
            return {
                "success": True,
                "analysis_id": analysis_id,
                "total_transactions": summary.get("total_transactions", 0),
                "risk_level": fraud.get("risk_level"),
                "composite_score": fraud.get("composite_score"),
                "message": f"Successfully parsed {summary.get('total_transactions', 0)} transactions",
            }

        except StatementParsingError as e:
            # Файл прочитан, но извлечь из него нечего. Пользователю нужна
            # причина, а не «processing failed».
            analysis.status = "failed"
            analysis.conclusion = str(e)
            self.db.commit()
            raise

        except Exception as e:
            analysis.status = "failed"
            self.db.commit()
            raise ValueError(f"Failed to process file: {str(e)}")

    def get_transactions_by_analysis(self, analysis_id: int) -> List[Transaction]:
        """
        Get all transactions for an analysis

        Args:
            analysis_id: Analysis ID

        Returns:
            List of Transaction objects
        """
        return self.db.query(Transaction).filter(
            Transaction.analysis_id == analysis_id
        ).all()

    def get_transaction_stats(self, analysis_id: int) -> Dict[str, Any]:
        """
        Get transaction statistics for an analysis

        Args:
            analysis_id: Analysis ID

        Returns:
            Dictionary with statistics
        """
        transactions = self.get_transactions_by_analysis(analysis_id)

        incoming_count = sum(1 for t in transactions if t.transaction_type == "incoming")
        outgoing_count = sum(1 for t in transactions if t.transaction_type == "outgoing")
        transfer_count = sum(1 for t in transactions if t.transaction_type == "transfer")

        incoming_amount = sum(t.amount for t in transactions if t.transaction_type == "incoming")
        outgoing_amount = sum(t.amount for t in transactions if t.transaction_type == "outgoing")

        return {
            "total_transactions": len(transactions),
            "incoming_count": incoming_count,
            "outgoing_count": outgoing_count,
            "transfer_count": transfer_count,
            "incoming_amount": float(incoming_amount),
            "outgoing_amount": float(outgoing_amount),
            "net_amount": float(incoming_amount - outgoing_amount),
            "avg_transaction_amount": float(sum(t.amount for t in transactions) / len(transactions)) if transactions else 0,
            "suspicious_count": sum(1 for t in transactions if t.is_suspicious),
            "anomaly_count": sum(1 for t in transactions if t.is_anomaly),
        }
