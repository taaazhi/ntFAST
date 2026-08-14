"""
Базовый класс парсера банковских выписок
Все банковские парсеры наследуются от этого класса
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StatementParsingError(Exception):
    """Выписку не удалось разобрать — ни одной транзакции не извлечено.

    Поднимается вместо молчаливого возврата пустого результата. Раньше парсер
    возвращал success=True с нулём транзакций, анализ продолжался на пустом
    списке, и пользователь видел «Анализ завершён» с риском LOW — то есть
    система сообщала «чисто» там, где она просто не прочитала документ.
    Для инструмента следственных органов это худший класс ошибки.
    """

    def __init__(self, message: str, *, bank: str = "", parser: str = "",
                 details: Optional[List[str]] = None):
        super().__init__(message)
        self.bank = bank
        self.parser = parser
        self.details = details or []


class TransactionType(Enum):
    """Универсальные типы транзакций"""
    INCOME = "income"           # Пополнение
    EXPENSE = "expense"         # Расход/Покупка
    TRANSFER_IN = "transfer_in"  # Входящий перевод
    TRANSFER_OUT = "transfer_out"  # Исходящий перевод
    WITHDRAWAL = "withdrawal"   # Снятие наличных
    DEPOSIT = "deposit"         # Депозит
    FEE = "fee"                 # Комиссия
    REFUND = "refund"           # Возврат
    CRYPTO_BUY = "crypto_buy"   # Покупка крипты
    CRYPTO_SELL = "crypto_sell" # Продажа крипты
    OTHER = "other"             # Прочее


class CounterpartyType(Enum):
    """Типы контрагентов"""
    PERSON = "person"           # Физическое лицо (Ержан О., Маржан П.)
    MERCHANT = "merchant"       # Мерчант/Магазин (YANDEX.GO, Salem Duken)
    BANK = "bank"               # Банковская операция (С карты другого банка)
    ATM = "atm"                 # Банкомат (В Kaspi Банкомате)
    GOVERNMENT = "government"   # Гос. выплаты (Пенсия/пособие)
    DEPOSIT = "deposit"         # Депозитные операции (На Kaspi Депозит)
    UNKNOWN = "unknown"


@dataclass
class Transaction:
    """Универсальная модель транзакции для всех банков"""
    date: datetime
    amount: float
    type: TransactionType
    description: str
    category: str = ""
    subcategory: str = ""
    currency: str = "KZT"
    original_amount: Optional[float] = None
    original_currency: Optional[str] = None
    exchange_rate: Optional[float] = None       # Курс: KZT / foreign (вычисляемый)
    counterparty: Optional[str] = None          # Контрагент
    counterparty_type: CounterpartyType = CounterpartyType.UNKNOWN
    # Реквизиты контрагента. Присутствуют в структурированных выгрузках
    # (CSV с явными колонками), в PDF-выписках обычно недоступны. Хранятся
    # в БД, поэтому модель обязана их переносить — иначе данные теряются
    # на пути «парсер → БД».
    counterparty_iin_bin: Optional[str] = None
    counterparty_account: Optional[str] = None
    counterparty_bank: Optional[str] = None
    payment_purpose: Optional[str] = None
    reference: Optional[str] = None             # Номер операции
    balance_after: Optional[float] = None       # Баланс после операции

    # Метаданные мерчанта
    merchant_name: Optional[str] = None         # Чистое имя мерчанта
    merchant_type: Optional[str] = None         # ИП, ТОО, АО и т.д.

    # Флаги транзакции
    is_blocked: bool = False                    # "Сумма заблокирована"
    is_deposit_operation: bool = False           # На/С Kaspi Депозит(а)
    is_pension_benefit: bool = False             # Пенсия/пособие
    is_bank_transfer: bool = False               # С карты другого банка
    is_atm: bool = False                         # В Kaspi Банкомате
    is_salary: bool = False                      # Зарплата
    is_cash_operation: bool = False              # Наличные операции

    # Источник для отладки
    source_page: Optional[int] = None
    source_row: Optional[int] = None
    raw_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "date": self.date.isoformat() if self.date else None,
            "amount": self.amount,
            "type": self.type.value,
            "description": self.description,
            "category": self.category,
            "subcategory": self.subcategory,
            "currency": self.currency,
            "original_amount": self.original_amount,
            "original_currency": self.original_currency,
            "exchange_rate": self.exchange_rate,
            "counterparty": self.counterparty,
            "counterparty_type": self.counterparty_type.value,
            "counterparty_iin_bin": self.counterparty_iin_bin,
            "counterparty_account": self.counterparty_account,
            "counterparty_bank": self.counterparty_bank,
            "payment_purpose": self.payment_purpose,
            "reference": self.reference,
            "balance_after": self.balance_after,
            "merchant_name": self.merchant_name,
            "merchant_type": self.merchant_type,
            "is_blocked": self.is_blocked,
            "is_deposit_operation": self.is_deposit_operation,
            "is_pension_benefit": self.is_pension_benefit,
            "is_bank_transfer": self.is_bank_transfer,
            "is_atm": self.is_atm,
            "is_salary": self.is_salary,
            "is_cash_operation": self.is_cash_operation,
            "source_page": self.source_page,
        }


@dataclass
class AccountInfo:
    """Универсальная информация о счете"""
    owner: str = ""
    account_number: str = ""
    card_number: str = ""
    currency: str = "KZT"
    bank_name: str = ""
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    balance_start: float = 0.0
    balance_end: float = 0.0
    # Лимиты и доп. информация
    salary_money_limit: float = 0.0             # Остаток зарплатных денег
    other_deposits_limit: float = 0.0           # Другие пополнения (лимит)
    total_cash_limit: float = 0.0               # Итого лимит на снятие
    extra: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "owner": self.owner,
            "account_number": self.account_number,
            "card_number": self.card_number,
            "currency": self.currency,
            "bank_name": self.bank_name,
            "period": {
                "from": self.period_start.isoformat() if self.period_start else None,
                "to": self.period_end.isoformat() if self.period_end else None
            },
            "balance_start": self.balance_start,
            "balance_end": self.balance_end,
            "cash_limits": {
                "salary_money": self.salary_money_limit,
                "other_deposits": self.other_deposits_limit,
                "total": self.total_cash_limit,
            },
            "extra": self.extra
        }


@dataclass
class ExpectedTotals:
    """Ожидаемые итоги из выписки для валидации"""
    deposits: float = 0.0
    withdrawals: float = 0.0
    purchases: float = 0.0
    transfers: float = 0.0
    other: float = 0.0


class BaseParser(ABC):
    """
    Абстрактный базовый класс для всех банковских парсеров

    Каждый банковский парсер должен реализовать:
    - parse() - основной метод парсинга
    - _parse_transactions() - парсинг транзакций
    - _parse_account_info() - парсинг информации о счете
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.account = AccountInfo()
        self.transactions: List[Transaction] = []
        self.expected_totals = ExpectedTotals()
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @abstractmethod
    def parse(self) -> bool:
        """
        Основной метод парсинга
        Возвращает True если парсинг успешен
        """
        pass

    @abstractmethod
    def _parse_account_info(self) -> None:
        """Извлечь информацию о счете и владельце"""
        pass

    @abstractmethod
    def _parse_transactions(self) -> None:
        """Извлечь все транзакции"""
        pass

    def get_account_info(self) -> AccountInfo:
        """Получить информацию о счете"""
        return self.account

    def get_transactions(self) -> List[Transaction]:
        """Получить список транзакций"""
        return self.transactions

    def get_expected_totals(self) -> ExpectedTotals:
        """Получить ожидаемые итоги для валидации"""
        return self.expected_totals

    def validate(self) -> Dict[str, Any]:
        """
        Валидация спарсенных данных
        Сравнивает фактические суммы с ожидаемыми
        """
        # Подсчёт фактических сумм — ПО ЗНАКУ, а не по перечню типов.
        # Прежняя версия перечисляла типы явно, и операции с типом OTHER
        # (Kaspi «Разное»), REFUND, CRYPTO_* не попадали ни в доходы, ни в
        # расходы. Баланс не сходился на корректно разобранной выписке, флаг
        # is_valid уходил в False, и UI показывал «Есть расхождения» всегда.
        # Знак суммы — единственный универсальный признак направления, и он
        # не ломается при добавлении новых типов операций.
        actual_deposits = sum(t.amount for t in self.transactions if t.amount > 0)
        actual_expenses = sum(-t.amount for t in self.transactions if t.amount < 0)

        expected = {
            "deposits": self.expected_totals.deposits,
            "withdrawals": self.expected_totals.withdrawals,
            "purchases": self.expected_totals.purchases,
            "transfers": self.expected_totals.transfers,
            "other": self.expected_totals.other
        }

        actual = {
            "deposits": actual_deposits,
            "expenses": actual_expenses
        }

        # Балансы извлекаются не из каждой выписки: у Binance их нет вовсе,
        # и складывать суммы в USDT/BTC/ETH в один «оборот» бессмысленно.
        has_balances = bool(self.account.balance_start or self.account.balance_end)

        # Проверка баланса с ОТНОСИТЕЛЬНЫМ допуском.
        # Жёсткий порог в 1 тенге — это 0.00008% от оборота в 1.2 млн, то есть
        # строже, чем сходятся сами банковские справки: в мультивалютных
        # выписках Halyk остатки по KZT/USD/EUR дают копеечную невязку на
        # стороне банка. Проверено на реальных выписках: строка «Всего»,
        # напечатанная банком, совпадает с извлечёнными суммами до копейки,
        # а остатки расходятся на единицы тенге. Абсолютный порог помечал
        # такие корректно разобранные выписки как невалидные, и UI показывал
        # «Есть расхождения» практически всегда.
        turnover = actual_deposits + actual_expenses
        tolerance = max(1.0, turnover * 1e-5)  # 0.001% от оборота, но не менее 1 ₸

        calculated_end = self.account.balance_start + actual_deposits - actual_expenses
        balance_diff = abs(calculated_end - self.account.balance_end)

        # balance_reconciled — свойство ДОКУМЕНТА: сходится ли он сам с собой.
        # None означает «проверить нечем» (балансы не извлекаются из этого формата).
        balance_reconciled: Optional[bool] = None
        if has_balances:
            balance_reconciled = balance_diff <= tolerance

        # is_valid — свойство ИЗВЛЕЧЕНИЯ: пригодны ли данные для анализа.
        # Это разные вещи, и раньше они были смешаны: мультивалютная справка
        # Halyk (KZT-таблица операций при остатках по KZT/USD/EUR) не сходится
        # по построению, и выписка помечалась как невалидная, хотя строка
        # «Всего» банка совпадает с извлечёнными суммами до копейки.
        is_valid = len(self.transactions) > 0

        if balance_reconciled is False:
            self.warnings.append(
                f"Баланс не сходится: начальный {self.account.balance_start:,.2f} + "
                f"доход {actual_deposits:,.2f} - расход {actual_expenses:,.2f} = "
                f"{calculated_end:,.2f}, в выписке {self.account.balance_end:,.2f} "
                f"(отклонение {balance_diff:,.2f} при допуске {tolerance:,.2f}). "
                f"Возможная причина — мультивалютная выписка или комиссии вне таблицы операций."
            )

        return {
            "total_transactions": len(self.transactions),
            "is_valid": is_valid,
            "balance_reconciled": balance_reconciled,
            "expected": expected,
            "actual": actual,
            "balance_check": {
                "start": self.account.balance_start,
                "calculated_end": calculated_end,
                "actual_end": self.account.balance_end,
                "difference": balance_diff,
                "tolerance": round(tolerance, 2),
                "checked": has_balances,
            },
            "errors": self.errors,
            "warnings": self.warnings,
            "account": self.account.to_dict()
        }

    def get_summary(self) -> Dict[str, Any]:
        """Получить краткую сводку"""
        total_income = sum(t.amount for t in self.transactions if t.amount > 0)
        total_expense = sum(abs(t.amount) for t in self.transactions if t.amount < 0)

        return {
            "total_transactions": len(self.transactions),
            "total_income": total_income,
            "total_expense": total_expense,
            "net_flow": total_income - total_expense,
            "avg_transaction": (total_income + total_expense) / len(self.transactions) if self.transactions else 0,
            "period": {
                "from": self.account.period_start.isoformat() if self.account.period_start else None,
                "to": self.account.period_end.isoformat() if self.account.period_end else None
            }
        }
