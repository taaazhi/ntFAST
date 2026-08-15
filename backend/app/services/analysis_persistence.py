"""Сохранение результата анализа выписки в базу.

Выделено из `api/bank_analysis.py`, чтобы одним и тем же кодом пользовались
и HTTP-обработчик, и Celery-задача. Пока эта логика жила в слое API, у
проекта было два независимых пути записи результата — синхронный через
`/api/bank/analyze` и асинхронный через `FileProcessingService` — и они
писали в БД по-разному. Один и тот же файл давал разный отчёт в зависимости
от того, каким способом его загрузили.
"""
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.subject import Subject
from app.models.transaction import Transaction as DBTransaction

logger = logging.getLogger(__name__)

# Форматы выписок, которые умеет разбирать единый конвейер
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv"}

def sanitize_filename(name: str) -> str:
    """Strip path separators and whitelist filename chars (defeats path traversal)."""
    if not name:
        return "unnamed"
    safe = Path(name).name
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", safe)
    return safe[:200] or "unnamed"


def norm_bank_type(meta: dict) -> Optional[str]:
    """Extract bank_type from meta and normalize to lowercase.

    Returns None if the detected type is empty, so queries on bank_type=None
    behave consistently across all analyses.
    """
    raw = (meta.get("detected_bank") or {}).get("type") or meta.get("bank_type")
    if not raw:
        return None
    return str(raw).lower().strip() or None


def get_file_extension(filename: str) -> str:
    """Получить расширение файла в нижнем регистре"""
    return os.path.splitext(filename or "")[1].lower()


class UnsupportedFileType(ValueError):
    """Расширение файла не поддерживается. HTTP-слой превращает в 400."""

    def __init__(self, ext: str):
        self.ext = ext
        self.supported = sorted(ALLOWED_EXTENSIONS)
        super().__init__(
            f"Неподдерживаемый формат файла '{ext}'. "
            f"Поддерживаются: {', '.join(self.supported)}"
        )


def validate_file_extension(filename: str) -> str:
    """Проверить расширение и вернуть его. Raises UnsupportedFileType.

    Сервисный слой не знает про HTTP: одна и та же проверка нужна и веб-
    обработчику, и Celery-задаче, у которой нет ни запроса, ни ответа.
    """
    ext = get_file_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(ext)
    return ext


def save_analysis_to_db(
    db: Session,
    result: dict,
    filename: str,
    file_ext: str,
    file_size: int,
    user_id: Optional[int] = None,
    analysis_id: Optional[int] = None,
) -> Optional[int]:
    """
    Сохранить результаты анализа в PostgreSQL.

    Создаёт (или обновляет, если передан `analysis_id`):
    - Analysis запись с fraud results
    - Transaction записи для каждой транзакции
    - Subject записи для контрагентов

    `analysis_id` нужен асинхронному пути: строка Analysis там создаётся ещё
    на этапе загрузки файла, чтобы пользователь сразу видел её в списке со
    статусом pending, а результат прилетает позже из Celery.

    Returns:
        ID Analysis или None при ошибке
    """
    try:
        # ── 1. Создаём или находим Analysis ──
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

        # Асинхронный путь передаёт id уже созданной строки — дописываем в неё.
        # Синхронного пути больше нет, но параметр остаётся необязательным,
        # чтобы функцию можно было вызвать и на пустом месте (тесты, импорт).
        db_analysis = None
        if analysis_id is not None:
            db_analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if db_analysis is None:
                logger.warning(f"Analysis {analysis_id} не найден, создаём новую запись")

        if db_analysis is None:
            db_analysis = Analysis(analyst_id=user_id or 1)
            db.add(db_analysis)

        fields = {
            "file_name": filename,
            "file_type": file_ext.lstrip("."),
            "file_size": file_size,
            "status": "completed",

            # Банк (meta contains nested "detected_bank" dict from BankAnalyzer)
            # bank_type normalized to lowercase to make filter/group queries case-insensitive
            "bank_type": norm_bank_type(meta),
            "bank_name": (meta.get("detected_bank") or {}).get("name") or meta.get("bank_name"),
            "bank_confidence": (meta.get("detected_bank") or {}).get("confidence") or meta.get("confidence"),

            # Счёт
            "account_owner": account.get("owner", ""),
            "account_number": account.get("account_number") or account.get("card_number", ""),
            "account_currency": account.get("currency", "KZT"),
            "balance_start": account.get("balance_start"),
            "balance_end": account.get("balance_end"),
            "parsed_account_info": account,

            # Статистика
            "total_transactions": summary.get("total_transactions", 0),
            "total_income": summary.get("total_income", 0),
            "total_expense": summary.get("total_expense", 0),
            "net_flow": summary.get("net_flow", 0),

            # Антифрод — fraud_report is None (not {}) when no fraud data
            "fraud_composite_score": fraud.get("composite_score"),
            "fraud_risk_level": fraud.get("risk_level"),
            "fraud_report": fraud_for_storage,
            "fraud_red_flags": fraud.get("red_flags"),
            "fraud_recommendations": fraud.get("recommendations"),

            # Отдельные модули
            "velocity_result": fraud.get("velocity"),
            "graph_result": fraud.get("graph"),
            "behavioral_result": fraud.get("behavioral"),
            "structuring_result": fraud.get("structuring"),
            "cross_reference_result": fraud.get("cross_reference"),
            "merchant_risk_result": fraud.get("merchant_risk"),

            # Новые модули v4
            "night_transactions_result": fraud.get("night_transactions"),
            "duplicate_payments_result": fraud.get("duplicate_payments"),
            "round_amounts_result": fraud.get("round_amounts"),
            "profile_mismatch_result": fraud.get("profile_mismatch"),

            # Полные результаты аналитики. Исключается только то, что уже
            # лежит в собственных колонках или занимает много места.
            #
            # `summary` раньше тоже исключался — и это молча ломало отчёт при
            # повторном открытии: средний расход за день и медиана транзакции
            # хранятся только здесь, своих колонок у них нет, поэтому фронтенд
            # показывал по нулю. Ошибка не проявлялась сразу после анализа,
            # когда отчёт строится из ответа в памяти, а всплывала позже — при
            # открытии сохранённого дела.
            "analytics_result": {
                k: v for k, v in result.items()
                if k not in ("transactions", "fraud_analysis", "fraud_report",
                             "meta", "account_info", "account")
            },

            # Risk score (0-100 → 0-10)
            "risk_score": min(10, int((fraud.get("composite_score", 0) or 0) / 10)),

            "completed_at": datetime.utcnow(),
        }
        for key, value in fields.items():
            setattr(db_analysis, key, value)
        if user_id is not None:
            db_analysis.analyst_id = user_id

        # Повторный анализ той же записи не должен удваивать транзакции
        if analysis_id is not None:
            removed = db.query(DBTransaction).filter(
                DBTransaction.analysis_id == analysis_id
            ).delete(synchronize_session=False)
            if removed:
                logger.info(f"Analysis {analysis_id}: удалено {removed} прежних транзакций")

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

        db.flush()  # Получаем ID для новой записи

        analysis_id = db_analysis.id
        logger.info(f"Analysis ID={analysis_id} сохранён для '{filename}'")

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
                    # Реквизиты из структурированных выгрузок (CSV). В PDF их
                    # обычно нет, но там, где они есть, терять их нельзя —
                    # ИИН контрагента это ключ для сопоставления субъектов.
                    counterparty_iin_bin=tx_data.get("counterparty_iin_bin"),
                    counterparty_account=tx_data.get("counterparty_account"),
                    counterparty_bank=tx_data.get("counterparty_bank"),
                    payment_purpose=tx_data.get("payment_purpose"),

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

