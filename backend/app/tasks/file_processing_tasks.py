"""
Celery Tasks for File Processing
Асинхронные задачи для обработки файлов
"""
import glob
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from celery import Task

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.analysis import Analysis
from app.models.transaction import Transaction as TransactionModel
from app.services.file_processing_service import FileProcessingService

logger = logging.getLogger(__name__)

# Канал прогресса. Воркер Celery — отдельный процесс, у него нет доступа к
# event loop веб-приложения, поэтому шаги анализа публикуются в Redis, а
# websocket-эндпоинт пересылает их в браузер.
PROGRESS_CHANNEL = "ntfast:progress:{session_id}"

_redis_client = None


def _get_redis():
    """Ленивый общий клиент: прогресс публикуется десяток раз за анализ."""
    global _redis_client
    if _redis_client is None:
        import redis
        from app.core.config import settings
        _redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    return _redis_client


def _publish_progress(session_id: str, payload: Dict[str, Any]) -> None:
    """Опубликовать событие прогресса. Сбой канала не должен ронять анализ."""
    try:
        payload.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        _get_redis().publish(
            PROGRESS_CHANNEL.format(session_id=session_id), json.dumps(payload)
        )
    except Exception as e:
        logger.debug(f"Progress publish failed (non-fatal): {e}")


def _make_progress_publisher(session_id: str):
    """Собрать колбэк в форме, которую ожидает BankAnalyzer."""
    def callback(step: str, percent: int, message: str, detail: str = "") -> None:
        _publish_progress(session_id, {
            "type": "progress", "step": step, "percent": percent,
            "message": message, "detail": detail,
        })
    return callback


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
def process_file_task(self, analysis_id: int, file_path: str,
                      session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Полный анализ выписки: парсинг, категоризация, аналитика, антифрод.

    Это ЕДИНСТВЕННЫЙ путь обработки файла в системе. Раньше рядом
    существовал синхронный `/api/bank/analyze`, который делал ту же работу
    другим кодом, и результат зависел от того, каким способом загрузили файл.

    Args:
        analysis_id: ID анализа
        file_path: путь к файлу
        session_id: идентификатор WebSocket-сессии для прогресса (опционально)

    Returns:
        Словарь с результатами обработки
    """
    logger.info(f"Starting file processing for analysis_id={analysis_id}, file_path={file_path}")

    try:
        processing_service = FileProcessingService(self.db)

        # Прогресс в браузер через Redis-канал: воркер живёт в отдельном
        # процессе и до event loop веб-приложения дотянуться не может.
        on_progress = _make_progress_publisher(session_id) if session_id else None

        result = processing_service.process_file(analysis_id, file_path, on_progress=on_progress)

        logger.info(f"File processing completed for analysis_id={analysis_id}. Total transactions: {result.get('total_transactions', 0)}")

        if session_id:
            _publish_progress(session_id, {
                "type": "completed", "percent": 100,
                "analysis_id": analysis_id,
                "risk_level": result.get("risk_level"),
            })

        return result

    except Exception as e:
        logger.error(f"File processing failed for analysis_id={analysis_id}: {str(e)}", exc_info=True)

        # Причина отказа должна дойти до открытой вкладки, а не только в лог:
        # пользователь стоит и смотрит на прогресс-бар.
        if session_id:
            from app.services.bank_analyzer.base_parser import StatementParsingError
            _publish_progress(session_id, {
                "type": "error",
                "message": "parsing_failed" if isinstance(e, StatementParsingError) else "analysis_failed",
                "detail": str(e)[:300],
                "analysis_id": analysis_id,
            })

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
