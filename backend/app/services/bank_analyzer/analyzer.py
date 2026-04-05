"""
Универсальный анализатор банковских выписок
Автоматически определяет банк и выбирает соответствующий парсер
"""
import logging
from typing import Dict, Any, List, Optional, Type
from datetime import datetime

from .detector import BankDetector, BankType, BankDetectionResult
from .base_parser import BaseParser, Transaction, TransactionType, AccountInfo
from .parsers.kaspi import KaspiParser
from .parsers.halyk import HalykParser
from .parsers.generic import GenericParser
from .parsers.binance import BinanceParser
from ..kaspi_analyzer.categorizer import TransactionCategorizer
from ..kaspi_analyzer.analytics import FinancialAnalytics
# FraudEngine импортируется лениво внутри метода, чтобы избежать циклического импорта

logger = logging.getLogger(__name__)


class BankAnalyzer:
    """
    Умный анализатор банковских выписок

    Возможности:
    - Автоматическое определение типа банка
    - Адаптивный парсинг для разных форматов
    - Категоризация транзакций
    - Финансовая аналитика
    """

    # Маппинг типов банков на парсеры
    PARSER_MAPPING: Dict[BankType, Type[BaseParser]] = {
        BankType.KASPI: KaspiParser,
        BankType.HALYK: HalykParser,
        BankType.BINANCE: BinanceParser,
        # Здесь будут добавлены другие банки:
        # BankType.SBERBANK: SberbankParser,
    }

    def __init__(self, pdf_path: str, on_progress: Optional[callable] = None):
        self.pdf_path = pdf_path
        self.detection_result: Optional[BankDetectionResult] = None
        self.parser: Optional[BaseParser] = None
        self.categorizer = TransactionCategorizer()
        self.analytics: Optional[FinancialAnalytics] = None
        # Callback: on_progress(step, percent, message, detail)
        self._on_progress = on_progress

    def _emit(self, step: str, percent: int, message: str, detail: str = ""):
        """Отправить прогресс через callback (если задан)."""
        if self._on_progress:
            try:
                self._on_progress(step, percent, message, detail)
            except Exception:
                pass

    def analyze(self) -> Dict[str, Any]:
        """
        Полный анализ банковской выписки

        Этапы:
        1. Определение типа банка
        2. Выбор подходящего парсера
        3. Парсинг транзакций
        4. Категоризация
        5. Аналитика
        6. Антифрод-анализ
        7. Формирование результата
        """
        import os
        logger.info(f"Начинаем анализ: {self.pdf_path}")
        self._emit("init", 5, "Инициализация анализа", "Загрузка файла...")

        # 1. Определяем банк (PDF или XLSX — детектор поддерживает оба формата)
        self._emit("detecting", 10, "Определение банка", "Сканирование файла...")
        detector = BankDetector(self.pdf_path)
        self.detection_result = detector.detect()

        logger.info(
            f"Определён банк: {self.detection_result.bank_name} "
            f"(уверенность: {self.detection_result.confidence:.0%})"
        )
        self._emit("detected", 15, "Банк определён",
                    f"{self.detection_result.bank_name} ({self.detection_result.confidence:.0%})")

        # 2. Выбираем парсер
        parser_class = self.PARSER_MAPPING.get(
            self.detection_result.bank_type,
            GenericParser  # Универсальный парсер для неизвестных банков
        )
        self.parser = parser_class(self.pdf_path)

        logger.info(f"Используем парсер: {parser_class.__name__}")

        # 3. Парсим
        self._emit("parsing", 20, "Парсинг транзакций", f"Парсер: {parser_class.__name__}")
        success = self.parser.parse()
        if not success:
            logger.warning("Парсинг завершился с ошибками")

        transactions = self.parser.get_transactions()
        account = self.parser.get_account_info()

        logger.info(f"Спарсено транзакций: {len(transactions)}")
        self._emit("parsed", 35, "Транзакции извлечены",
                    f"Найдено {len(transactions)} транзакций")

        # 4. Категоризация
        self._emit("categorizing", 40, "Категоризация", "Классификация транзакций...")
        categorized_transactions = self._categorize_transactions(transactions)
        self._emit("categorized", 50, "Категоризация завершена",
                    f"Обработано {len(categorized_transactions)} транзакций")

        # 5. Аналитика - создаём объекты для analytics
        self._emit("analytics", 55, "Финансовая аналитика", "Расчёт показателей...")
        tx_objects = self._create_tx_objects_for_analytics(categorized_transactions)
        account_obj = self._create_account_object_for_analytics(account)
        self.analytics = FinancialAnalytics(tx_objects, account_obj)
        self.analytics.set_categorized_transactions(categorized_transactions)
        self._emit("analytics_done", 65, "Аналитика готова", "Финансовые показатели рассчитаны")

        # 6. Антифрод-анализ (ленивый импорт для избежания циклических зависимостей)
        fraud_report = None
        try:
            self._emit("fraud", 70, "Антифрод-анализ", "11 модулей проверки...")
            from ..fraud.engine import FraudEngine
            fraud_engine = FraudEngine()
            fraud_report = fraud_engine.full_analysis(transactions, account)
            logger.info(f"Антифрод: composite={fraud_report.composite_score}, level={fraud_report.risk_level}")
            self._emit("fraud_done", 85, "Антифрод-анализ завершён",
                        f"Риск: {fraud_report.risk_level}")
        except Exception as e:
            logger.error(f"Антифрод-анализ не удался: {e}", exc_info=True)
            self._emit("fraud_error", 85, "Антифрод-анализ", "Ошибка — продолжаем без фрод-анализа")

        # 7. Формируем результат
        self._emit("building", 90, "Формирование отчёта", "Сборка финального результата...")
        result = self._build_result(categorized_transactions, account, fraud_report)
        self._emit("completed", 100, "Анализ завершён", "Отчёт готов!")

        return result

    def _categorize_transactions(self, transactions: List[Transaction]) -> List[Dict]:
        """Категоризация транзакций"""
        from dataclasses import dataclass

        @dataclass
        class TxForCategorizer:
            details: str
            type: str
            amount: float

        result = []

        for tx in transactions:
            # Конвертируем в формат для категоризатора
            tx_dict = tx.to_dict()

            # Создаём объект для категоризатора
            tx_obj = TxForCategorizer(
                details=tx.description,
                type=self._get_kaspi_type(tx.type),
                amount=tx.amount
            )

            # Определяем категорию
            category, subcategory = self.categorizer.categorize(tx_obj)

            tx_dict['category'] = category
            tx_dict['subcategory'] = subcategory

            result.append(tx_dict)

        return result

    def _create_tx_objects_for_analytics(self, categorized_transactions: List[Dict]):
        """Создать объекты транзакций для analytics из словарей"""
        from dataclasses import dataclass
        from datetime import datetime

        @dataclass
        class TxForAnalytics:
            date: datetime
            amount: float
            type: str
            details: str
            category: str
            subcategory: str
            currency: str = "KZT"
            original_amount: float = None
            original_currency: str = None

        result = []
        for tx_dict in categorized_transactions:
            date = tx_dict.get('date')
            if isinstance(date, str):
                try:
                    date = datetime.fromisoformat(date)
                except (ValueError, TypeError):
                    date = datetime.now()

            result.append(TxForAnalytics(
                date=date,
                amount=tx_dict.get('amount', 0),
                type=tx_dict.get('type', ''),
                details=tx_dict.get('description', ''),
                category=tx_dict.get('category', ''),
                subcategory=tx_dict.get('subcategory', ''),
                currency=tx_dict.get('currency', 'KZT'),
                original_amount=tx_dict.get('original_amount'),
                original_currency=tx_dict.get('original_currency')
            ))
        return result

    def _create_account_object_for_analytics(self, account: AccountInfo):
        """Создать объект счёта для analytics"""
        from dataclasses import dataclass
        from datetime import datetime

        @dataclass
        class AccountForAnalytics:
            balance_start: float
            balance_end: float
            period_start: datetime
            period_end: datetime

        return AccountForAnalytics(
            balance_start=account.balance_start,
            balance_end=account.balance_end,
            period_start=account.period_start or datetime.now(),
            period_end=account.period_end or datetime.now()
        )

    def _get_kaspi_type(self, tx_type: TransactionType) -> str:
        """Конвертировать универсальный тип в формат Kaspi для категоризатора"""
        type_mapping = {
            TransactionType.INCOME: 'Пополнение',
            TransactionType.EXPENSE: 'Покупка',
            TransactionType.TRANSFER_IN: 'Перевод',
            TransactionType.TRANSFER_OUT: 'Перевод',
            TransactionType.WITHDRAWAL: 'Снятие',
            TransactionType.DEPOSIT: 'Пополнение',
            TransactionType.FEE: 'Разное',
            TransactionType.REFUND: 'Пополнение',
            TransactionType.CRYPTO_BUY: 'Покупка',
            TransactionType.CRYPTO_SELL: 'Пополнение',
            TransactionType.OTHER: 'Разное',
        }
        return type_mapping.get(tx_type, 'Разное')

    def _build_result(self, transactions: List[Dict], account, fraud_report=None) -> Dict[str, Any]:
        """Сформировать финальный результат анализа"""

        # Валидация
        validation = self.parser.validate()

        # Суммарная статистика
        total_income = sum(t['amount'] for t in transactions if t['amount'] > 0)
        total_expense = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
        net_flow = total_income - total_expense

        # Средний дневной расход
        if account.period_start and account.period_end:
            days = (account.period_end - account.period_start).days or 1
            avg_daily_expense = total_expense / days
        else:
            avg_daily_expense = total_expense / 30  # Дефолт 30 дней

        # Медианная транзакция
        amounts = sorted([abs(t['amount']) for t in transactions])
        median = amounts[len(amounts) // 2] if amounts else 0

        return {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "pdf_file": self.pdf_path.split('/')[-1].split('\\')[-1],
                "parser_version": "3.0",
                "detected_bank": {
                    "type": self.detection_result.bank_type.value,
                    "name": self.detection_result.bank_name,
                    "confidence": self.detection_result.confidence,
                    "keywords_found": self.detection_result.detected_keywords[:5]  # Топ 5
                }
            },
            "account": account.to_dict(),
            "validation": validation,
            "summary": {
                "total_transactions": len(transactions),
                "total_income": round(total_income, 2),
                "total_expense": round(total_expense, 2),
                "net_flow": round(net_flow, 2),
                "avg_daily_expense": round(avg_daily_expense, 2),
                "median_transaction": round(median, 2)
            },
            "transactions": transactions,
            "analytics": self.analytics.calculate_all() if self.analytics else {},
            "contacts": self._extract_contacts(transactions),
            "fraud_report": fraud_report.to_dict() if fraud_report else None
        }

    def _extract_contacts(self, transactions: List[Dict]) -> Dict[str, Any]:
        """Извлечь контакты из транзакций"""
        contacts = {}

        for tx in transactions:
            # Ищем имена в переводах
            if 'перевод' in tx.get('type', '').lower() or tx.get('type') in ['transfer_in', 'transfer_out']:
                desc = tx.get('description', '')
                # Простая эвристика - имена с большой буквы
                import re
                name_match = re.search(r'([А-ЯЁӘҒҚҢӨҰҮІҺəƏA-Z][а-яёәғқңөұүіһəƏa-z]+\s+[А-ЯЁӘҒҚҢӨҰҮІҺəƏA-Z]\.?)', desc)
                if name_match:
                    name = name_match.group(1)
                    if name not in contacts:
                        contacts[name] = {"count": 0, "is_frequent": False}
                    contacts[name]["count"] += 1

        # Помечаем частые контакты
        for name, data in contacts.items():
            data["is_frequent"] = data["count"] >= 3

        return contacts
