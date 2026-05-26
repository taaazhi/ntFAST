"""
API эндпоинты для универсального анализа банковских выписок
Поддерживает все банки: Kaspi, Halyk, Сбербанк, Binance и другие

Форматы:
  - PDF: Kaspi, Halyk, Сбербанк и другие
  - XLSX: Binance

v2: Все результаты сохраняются в PostgreSQL (Analysis, Transaction, Subject)
"""
import os
import re
import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.bank_analyzer import BankAnalyzer, BankDetector, BankType
from app.services.pdf_export import NtFastPDFReport
from app.services.websocket_manager import analysis_progress
from app.models.analysis import Analysis
from app.models.transaction import Transaction as DBTransaction
from app.models.subject import Subject
from app.services.auth_service import get_current_user
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

# Допустимые расширения файлов
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}


def _sanitize_filename(name: str) -> str:
    """Strip path separators and whitelist filename chars (defeats path traversal)."""
    if not name:
        return "unnamed"
    safe = Path(name).name
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", safe)
    return safe[:200] or "unnamed"


def _norm_bank_type(meta: dict) -> Optional[str]:
    """Extract bank_type from meta and normalize to lowercase.

    Returns None if the detected type is empty, so queries on bank_type=None
    behave consistently across all analyses.
    """
    raw = (meta.get("detected_bank") or {}).get("type") or meta.get("bank_type")
    if not raw:
        return None
    return str(raw).lower().strip() or None


def _get_file_extension(filename: str) -> str:
    """Получить расширение файла в нижнем регистре"""
    return os.path.splitext(filename or "")[1].lower()


def _validate_file_extension(filename: str) -> str:
    """Проверить расширение и вернуть его. Raises HTTPException если недопустимо."""
    ext = _get_file_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат файла '{ext}'. "
                   f"Поддерживаются: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


def _save_analysis_to_db(
    db: Session,
    result: dict,
    filename: str,
    file_ext: str,
    file_size: int,
    user_id: Optional[int] = None,
) -> Optional[int]:
    """
    Сохранить результаты анализа в PostgreSQL.

    Создаёт:
    - Analysis запись с fraud results
    - Transaction записи для каждой транзакции
    - Subject записи для контрагентов

    Returns:
        ID созданного Analysis или None
    """
    try:
        # ── 1. Создаём Analysis ──
        meta = result.get("meta", {})
        # IMPORTANT: BankAnalyzer returns "account" (not "account_info")
        # and "fraud_report" (not "fraud_analysis")
        account = result.get("account") or result.get("account_info") or {}
        # Use a dict locally for safe .get() calls. Separately compute
        # fraud_for_storage which is None if empty — so the JSON column in DB
        # is NULL (not {}), and frontend `if (!fraud)` correctly detects no-data.
        fraud_raw = result.get("fraud_report") or result.get("fraud_analysis")
        fraud = fraud_raw if isinstance(fraud_raw, dict) else {}
        fraud_for_storage = fraud if fraud else None
        summary = result.get("summary", {})

        db_analysis = Analysis(
            analyst_id=user_id or 1,  # fallback на admin
            file_name=filename,
            file_type=file_ext.lstrip("."),
            file_size=file_size,
            status="completed",

            # Банк (meta contains nested "detected_bank" dict from BankAnalyzer)
            # bank_type normalized to lowercase to make filter/group queries case-insensitive
            bank_type=_norm_bank_type(meta),
            bank_name=(meta.get("detected_bank") or {}).get("name") or meta.get("bank_name"),
            bank_confidence=(meta.get("detected_bank") or {}).get("confidence") or meta.get("confidence"),

            # Счёт
            account_owner=account.get("owner", ""),
            account_number=account.get("account_number") or account.get("card_number", ""),
            account_currency=account.get("currency", "KZT"),
            balance_start=account.get("balance_start"),
            balance_end=account.get("balance_end"),
            parsed_account_info=account,

            # Статистика
            total_transactions=summary.get("total_transactions", 0),
            total_income=summary.get("total_income", 0),
            total_expense=summary.get("total_expense", 0),
            net_flow=summary.get("net_flow", 0),

            # Антифрод — fraud_report is None (not {}) when no fraud data
            fraud_composite_score=fraud.get("composite_score"),
            fraud_risk_level=fraud.get("risk_level"),
            fraud_report=fraud_for_storage,
            fraud_red_flags=fraud.get("red_flags"),
            fraud_recommendations=fraud.get("recommendations"),

            # Отдельные модули
            velocity_result=fraud.get("velocity"),
            graph_result=fraud.get("graph"),
            behavioral_result=fraud.get("behavioral"),
            structuring_result=fraud.get("structuring"),
            cross_reference_result=fraud.get("cross_reference"),
            merchant_risk_result=fraud.get("merchant_risk"),

            # Новые модули v4
            night_transactions_result=fraud.get("night_transactions"),
            duplicate_payments_result=fraud.get("duplicate_payments"),
            round_amounts_result=fraud.get("round_amounts"),
            profile_mismatch_result=fraud.get("profile_mismatch"),

            # Полные результаты аналитики (exclude raw data keys)
            analytics_result={
                k: v for k, v in result.items()
                if k not in ("transactions", "fraud_analysis", "fraud_report", "meta", "account_info", "account", "summary")
            },

            # Risk score (0-100 → 0-10)
            risk_score=min(10, int((fraud.get("composite_score", 0) or 0) / 10)),

            completed_at=datetime.utcnow(),
        )

        # Парсим даты периода
        period = account.get("period", {})
        if period:
            try:
                if period.get("from"):
                    db_analysis.period_start = datetime.fromisoformat(period["from"])
                if period.get("to"):
                    db_analysis.period_end = datetime.fromisoformat(period["to"])
            except (ValueError, TypeError):
                pass

        db.add(db_analysis)
        db.flush()  # Получаем ID

        analysis_id = db_analysis.id
        logger.info(f"Created Analysis ID={analysis_id} for '{filename}'")

        # ── 2. Создаём Subject (владелец счёта) ──
        owner_subject = None
        owner_name = account.get("owner", "").strip()
        account_num = account.get("account_number") or account.get("card_number", "")

        if owner_name:
            unique_id = account_num if account_num else f"{owner_name.lower().replace(' ', '_')}_account_owner"

            owner_subject = db.query(Subject).filter(
                Subject.unique_identifier == unique_id
            ).first()

            if not owner_subject:
                owner_subject = Subject(
                    unique_identifier=unique_id,
                    name=owner_name,
                    type="account_owner",
                    risk_level=0,
                    status="active",
                )
                db.add(owner_subject)
                db.flush()
                logger.info(f"Created owner subject: {owner_name} (ID={owner_subject.id})")

            db_analysis.subject_id = owner_subject.id

        # ── 3. Сохраняем транзакции ──
        raw_transactions = result.get("transactions", [])
        subject_cache = {}  # name → Subject
        saved_tx_count = 0

        for tx_data in raw_transactions:
            try:
                # Парсим дату
                tx_date = None
                date_str = tx_data.get("date")
                if date_str:
                    try:
                        tx_date = datetime.fromisoformat(date_str)
                    except (ValueError, TypeError):
                        tx_date = datetime.utcnow()
                else:
                    tx_date = datetime.utcnow()

                amount = tx_data.get("amount", 0)

                # Определяем тип транзакции
                tx_type = tx_data.get("type", "other")

                db_tx = DBTransaction(
                    analysis_id=analysis_id,
                    amount=amount,
                    currency=tx_data.get("currency", "KZT"),
                    transaction_type=tx_type,
                    transaction_date=tx_date,

                    # Мультивалютность
                    original_amount=tx_data.get("original_amount"),
                    original_currency=tx_data.get("original_currency"),
                    exchange_rate=tx_data.get("exchange_rate"),

                    # Контрагент
                    counterparty_name=tx_data.get("counterparty"),
                    counterparty_type=tx_data.get("counterparty_type"),

                    # Описание
                    description=tx_data.get("description", ""),
                    category=tx_data.get("category"),
                    subcategory=tx_data.get("subcategory"),

                    # Мерчант
                    merchant_name=tx_data.get("merchant_name"),
                    merchant_type=tx_data.get("merchant_type"),

                    # Флаги
                    is_blocked=tx_data.get("is_blocked", False),
                    is_deposit_operation=tx_data.get("is_deposit_operation", False),
                    is_pension_benefit=tx_data.get("is_pension_benefit", False),
                    is_bank_transfer=tx_data.get("is_bank_transfer", False),
                    is_atm=tx_data.get("is_atm", False),
                    is_salary=tx_data.get("is_salary", False),
                    is_cash_operation=tx_data.get("is_cash_operation", False),

                    # Источник
                    source_file=filename,
                    source_page=tx_data.get("source_page"),
                    raw_data=tx_data,
                )

                # ── 3.1. Создаём/ищем Subject для контрагента ──
                counterparty = tx_data.get("counterparty", "").strip()
                if counterparty and counterparty not in subject_cache:
                    # Определяем тип субъекта
                    cp_type = _determine_subject_type(counterparty)
                    cp_uid = _generate_unique_identifier(counterparty, cp_type)

                    # Ищем в БД
                    cp_subject = db.query(Subject).filter(
                        Subject.unique_identifier == cp_uid
                    ).first()

                    if not cp_subject:
                        cp_subject = Subject(
                            unique_identifier=cp_uid,
                            name=counterparty,
                            type=cp_type,
                            risk_level=0,
                            status="active",
                        )
                        db.add(cp_subject)
                        db.flush()

                    subject_cache[counterparty] = cp_subject

                if counterparty and counterparty in subject_cache:
                    db_tx.subject_id = subject_cache[counterparty].id

                db.add(db_tx)
                saved_tx_count += 1

            except Exception as e:
                logger.warning(f"Error saving transaction: {e}")
                continue

        # ── 4. Обновляем счётчики Analysis ──
        suspicious_count = sum(
            1 for tx in raw_transactions
            if tx.get("risk_score", 0) and tx["risk_score"] > 50
        )
        db_analysis.suspicious_count = suspicious_count
        db_analysis.total_transactions = saved_tx_count

        db.commit()

        logger.info(
            f"Saved to DB: Analysis ID={analysis_id}, "
            f"{saved_tx_count} transactions, "
            f"{len(subject_cache)} subjects"
        )

        return analysis_id

    except Exception as e:
        logger.error(f"Error saving analysis to DB: {e}", exc_info=True)
        db.rollback()
        return None


def _determine_subject_type(name: str) -> str:
    """Быстрое определение типа субъекта."""
    import re
    legal_patterns = [
        r'\b(ТОО|АО|ОАО|ЗАО|ПАО|НАО|ИП|ООО|LLC|LTD|Inc|Corp)\b',
    ]
    for pattern in legal_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return 'legal_entity'

    # Казахские имена: "Ержан О."
    if re.match(r'^[А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z]\.?$', name.strip()):
        return 'individual'

    if name.count(' ') >= 1 and len(name.split()) <= 4:
        if not re.search(r'\d', name):
            return 'individual'

    return 'legal_entity'


def _generate_unique_identifier(name: str, subject_type: str) -> str:
    """Генерация unique_identifier для субъекта."""
    import re
    normalized = ' '.join(name.split()).lower()
    normalized = re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9\s]', '', normalized)
    normalized = re.sub(r'\s+', '_', normalized.strip())
    if len(normalized) > 150:
        normalized = normalized[:150]
    return f"{normalized}_{subject_type}"


@router.post("/analyze")
async def analyze_bank_statement(
    file: UploadFile = File(...),
    session_id: Optional[str] = Query(None, description="WebSocket session ID для прогресса"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Анализ загруженной банковской выписки (PDF или XLSX)

    Автоматически определяет банк и выбирает соответствующий парсер.
    Если передан session_id — шлёт прогресс через WebSocket /ws/analysis/{session_id}.

    v2: Результаты сохраняются в PostgreSQL (Analysis + Transactions + Subjects)

    Возвращает полный анализ включая:
    - Информация о счёте и владельце
    - Определённый банк с уверенностью
    - Категоризированные транзакции
    - Помесячная разбивка
    - Анализ по категориям
    - Антифрод-анализ
    """
    # SECURITY: sanitize filename FIRST (defeats ../../etc/passwd traversal attempts)
    safe_filename = _sanitize_filename(file.filename or "")

    # Валидация типа файла
    ext = _validate_file_extension(safe_filename)

    # Создаём прогресс-callback для WebSocket
    progress_callback = None
    if session_id:
        try:
            loop = asyncio.get_running_loop()
            progress_callback = analysis_progress.create_sync_callback(session_id, loop)
        except Exception as e:
            logger.debug(f"Could not create progress callback: {e}")

    # Сохраняем файл временно
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        file_size = len(content)
        logger.info(f"Анализируем банковскую выписку: {safe_filename} ({ext})")

        # Запускаем анализ в thread pool — не блокируем event loop,
        # чтобы WebSocket прогресс доходил до клиента в реальном времени
        analyzer = BankAnalyzer(tmp_path, on_progress=progress_callback)
        result = await asyncio.to_thread(analyzer.analyze)

        # Добавляем оригинальное (санитизированное) имя файла
        result["meta"]["original_filename"] = safe_filename

        # ── Сохраняем в PostgreSQL ──
        analysis_id = _save_analysis_to_db(
            db=db,
            result=result,
            filename=safe_filename,
            file_ext=ext,
            file_size=file_size,
            user_id=current_user.id,
        )

        if analysis_id:
            result["meta"]["analysis_id"] = analysis_id
            logger.info(f"Analysis saved to DB with ID={analysis_id}")
        else:
            logger.warning("Analysis completed but could not save to DB")

        # Persistent notification — appears in the bell icon dropdown
        try:
            from app.services.notification_service import notify
            risk_level = (result.get("fraud_report") or {}).get("risk_level")
            composite = (result.get("fraud_report") or {}).get("composite_score")
            severity = "warning" if (composite and composite >= 60) else "success"
            notify(
                db,
                user_id=current_user.id,
                kind="analysis_completed",
                severity=severity,
                title=f"Analysis completed: {safe_filename}",
                body=f"Risk level: {risk_level or 'n/a'}" if risk_level else None,
                data={"analysis_id": analysis_id, "risk_level": risk_level, "composite_score": composite},
            )
        except Exception as e:
            logger.debug(f"analysis_completed notify failed (non-fatal): {e}")

        # Уведомляем WebSocket о завершении
        if session_id:
            await analysis_progress.send_completed(session_id)

        return JSONResponse(content=result)

    except HTTPException:
        # Don't wrap user-facing HTTPException — re-raise as-is
        if session_id:
            try:
                await analysis_progress.send_error(session_id, "analysis_failed")
            except Exception:
                pass
        raise
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}", exc_info=True)
        # SECURITY: send generic error to client; full details only to logs
        if session_id:
            try:
                await analysis_progress.send_error(session_id, "analysis_failed")
            except Exception:
                pass
        raise HTTPException(
            status_code=500,
            detail="Ошибка анализа банковской выписки",
        )

    finally:
        # Удаляем временный файл
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/detect")
async def detect_bank_type(
    file: UploadFile = File(...),
):
    """
    Определить тип банка без полного анализа

    Быстрая проверка какой банк выпустил выписку.
    Поддерживает PDF и XLSX файлы.
    """
    ext = _validate_file_extension(file.filename)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Для XLSX — автоматически Binance (без детектора)
        if ext in (".xlsx", ".xls"):
            return {
                "bank_type": "binance",
                "bank_name": "Binance",
                "confidence": 0.95,
                "detected_keywords": ["xlsx", "binance"],
                "all_scores": {"binance": 0.95}
            }

        detector = BankDetector(tmp_path)
        result = detector.detect()

        return {
            "bank_type": result.bank_type.value,
            "bank_name": result.bank_name,
            "confidence": result.confidence,
            "detected_keywords": result.detected_keywords,
            "all_scores": result.metadata.get("all_scores", {})
        }

    except Exception as e:
        logger.error(f"Ошибка определения банка: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка: {str(e)}"
        )

    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/supported-banks")
async def get_supported_banks():
    """Получить список поддерживаемых банков"""
    return {
        "banks": [
            {
                "type": "kaspi",
                "name": "Kaspi Bank",
                "country": "Казахстан",
                "status": "полная поддержка",
                "formats": ["PDF выписка Gold карты"]
            },
            {
                "type": "binance",
                "name": "Binance",
                "country": "Международный",
                "status": "полная поддержка",
                "formats": ["XLSX история транзакций"]
            },
            {
                "type": "halyk",
                "name": "Halyk Bank",
                "country": "Казахстан",
                "status": "в разработке",
                "formats": ["PDF справка о наличии счёта"]
            },
            {
                "type": "sberbank",
                "name": "Сбербанк",
                "country": "Казахстан/Россия",
                "status": "в разработке",
                "formats": []
            },
            {
                "type": "jusan",
                "name": "Jusan Bank",
                "country": "Казахстан",
                "status": "в разработке",
                "formats": []
            },
            {
                "type": "forte",
                "name": "ForteBank",
                "country": "Казахстан",
                "status": "в разработке",
                "formats": []
            },
            {
                "type": "freedom",
                "name": "Freedom Finance",
                "country": "Казахстан",
                "status": "в разработке",
                "formats": []
            },
            {
                "type": "unknown",
                "name": "Другие банки",
                "country": "Любой",
                "status": "универсальный парсер",
                "formats": ["PDF с таблицами транзакций"]
            }
        ]
    }


@router.post("/export-pdf")
async def export_analysis_pdf(request: Request):
    """
    Generate a PDF report from analysis results.

    Accepts the full analysis JSON (same structure as /analyze response)
    and returns a branded ntFAST PDF report.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not data or not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Empty or invalid analysis data")

    try:
        report = NtFastPDFReport(data)
        pdf_bytes = report.generate()

        # Build filename — must be pure ASCII for HTTP headers
        import io
        from datetime import datetime as _dt
        ts = _dt.now().strftime('%Y%m%d_%H%M')
        filename = f"ntFAST_report_{ts}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_bytes)),
            }
        )

    except Exception as e:
        logger.error(f"PDF generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(e)}"
        )


@router.get("/categories")
async def get_categories():
    """Получить все доступные категории транзакций"""
    from app.services.kaspi_analyzer import TransactionCategorizer

    categorizer = TransactionCategorizer()

    return {
        "expense_categories": [
            {
                "id": cat_id,
                "name": cat_info["name"],
                "keywords_count": len(cat_info["keywords"])
            }
            for cat_id, cat_info in categorizer.EXPENSE_CATEGORIES.items()
        ],
        "transfer_categories": [
            {"id": cat_id, "name": cat_info["name"]}
            for cat_id, cat_info in categorizer.TRANSFER_CATEGORIES.items()
        ],
        "income_categories": [
            {"id": cat_id, "name": cat_info["name"]}
            for cat_id, cat_info in categorizer.INCOME_CATEGORIES.items()
        ]
    }
