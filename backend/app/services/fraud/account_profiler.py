"""
AccountProfiler — автоматическая классификация типа аккаунта.

Запускается ПЕРВЫМ перед всеми fraud-модулями.
Результат (AccountProfile) передаётся во все модули для контекстного анализа.
"""
import math
from collections import defaultdict
from typing import List, Optional

from .models import AccountProfile, AccountType


# Ключевые слова для классификации
SALARY_KEYWORDS = {"ЗАРПЛАТА", "SALARY", "ОКЛАД", "ЗП", "ЖАЛАҚЫ"}
GOVERNMENT_KEYWORDS = {
    "ПЕНСИЯ", "ПОСОБИЕ", "БЮДЖЕТ", "EGOVPAYMENT", "МСЗН",
    "ЕНПФ", "ГЦВП", "ЗЕЙНЕТАҚЫ", "ЖӘРДЕМАҚЫ", "ENBEK"
}
CRYPTO_KEYWORDS = {
    "BINANCE", "BYBIT", "OKEX", "HUOBI", "KUCOIN", "MEXC",
    "GATE.IO", "COINBASE", "KRAKEN", "BITGET", "OKXBROKER",
    "BITMEX", "PHEMEX", "CRYPTO", "BITCOIN", "USDT"
}
BUSINESS_KEYWORDS = {"ТОО", "АО", "ИП ", "ООО", "ЗАО", "ОАО", "КОРПОРАЦИЯ"}


class AccountProfiler:
    """
    Профилировщик аккаунта.

    Использует транзакции за весь период для определения:
    - Типа аккаунта (7 категорий)
    - Средних месячных доходов/расходов
    - Регулярности доходов
    - Наличия крипто/бизнес активности
    """

    def profile(self, transactions: list) -> AccountProfile:
        """
        Основной метод: анализирует список транзакций и возвращает AccountProfile.

        Ожидает объекты с атрибутами:
        - amount (float): положительный = доход, отрицательный = расход
        - transaction_date или date (datetime)
        - counterparty_name или description (str, опционально)
        - is_salary (bool, опционально)
        - is_atm (bool, опционально)
        """
        p = AccountProfile()
        if not transactions:
            return p

        income_txs = [t for t in transactions if self._get_amount(t) > 0]
        expense_txs = [t for t in transactions if self._get_amount(t) < 0]

        # ── Статистика доходов ──────────────────────────────────
        monthly_income: dict = defaultdict(float)
        for t in income_txs:
            dt = self._get_date(t)
            if dt:
                monthly_income[(dt.year, dt.month)] += self._get_amount(t)

        if monthly_income:
            vals = list(monthly_income.values())
            p.avg_monthly_income = sum(vals) / len(vals)
            if p.avg_monthly_income > 0 and len(vals) > 1:
                variance = sum((v - p.avg_monthly_income) ** 2 for v in vals) / len(vals)
                p.monthly_income_cv = math.sqrt(variance) / p.avg_monthly_income

        # ── Статистика расходов ─────────────────────────────────
        monthly_expense: dict = defaultdict(float)
        for t in expense_txs:
            dt = self._get_date(t)
            if dt:
                monthly_expense[(dt.year, dt.month)] += abs(self._get_amount(t))

        if monthly_expense:
            p.avg_monthly_expense = sum(monthly_expense.values()) / len(monthly_expense)

        # ── Источники и направления ─────────────────────────────
        income_sources = set()
        expense_dests = set()

        for t in income_txs:
            cp = self._get_counterparty(t).upper()
            if cp:
                income_sources.add(cp)
            # Флаги типов дохода
            if self._is_salary(t, cp):
                p.has_salary_flag = True
            if any(kw in cp for kw in GOVERNMENT_KEYWORDS):
                p.has_pension_flag = True
            if any(kw in cp for kw in CRYPTO_KEYWORDS):
                p.has_crypto_activity = True

        for t in expense_txs:
            cp = self._get_counterparty(t).upper()
            if cp:
                expense_dests.add(cp)
            if any(kw in cp for kw in CRYPTO_KEYWORDS):
                p.has_crypto_activity = True

        p.unique_income_sources = len(income_sources)
        p.unique_expense_destinations = len(expense_dests)
        p.income_source_count = len(income_sources)

        # Бизнес-активность: много разных получателей платежей
        if p.unique_expense_destinations > 20:
            p.has_business_activity = True

        # ── Регулярность дохода ─────────────────────────────────
        p.income_regularity_score = self._calc_income_regularity(income_txs)

        # ── Pass-through ratio ──────────────────────────────────
        total_in = sum(self._get_amount(t) for t in income_txs)
        total_out = sum(abs(self._get_amount(t)) for t in expense_txs)
        if total_in > 0:
            p.pass_through_ratio = min(1.0, total_out / total_in)

        # ── Классификация ───────────────────────────────────────
        p.account_type = self._classify(p)
        return p

    # ── Вспомогательные методы ──────────────────────────────────

    def _get_amount(self, t) -> float:
        """Получить сумму транзакции."""
        if hasattr(t, 'amount'):
            return float(t.amount or 0)
        return 0.0

    def _get_date(self, t):
        """Получить дату транзакции."""
        for attr in ('transaction_date', 'date', 'created_at'):
            val = getattr(t, attr, None)
            if val is not None:
                return val
        return None

    def _get_counterparty(self, t) -> str:
        """Получить имя контрагента."""
        for attr in ('counterparty_name', 'counterparty', 'description', 'merchant_name'):
            val = getattr(t, attr, None)
            if val:
                return str(val)
        return ""

    def _is_salary(self, t, cp_upper: str) -> bool:
        """Определить зарплатную транзакцию."""
        if getattr(t, 'is_salary', False):
            return True
        if any(kw in cp_upper for kw in SALARY_KEYWORDS):
            return True
        desc = str(getattr(t, 'description', '') or '').upper()
        return any(kw in desc for kw in SALARY_KEYWORDS)

    def _calc_income_regularity(self, income_txs: list) -> float:
        """
        Регулярность дохода: 1.0 = доход приходит в один и тот же день каждый месяц.
        Анализируем день первого поступления в каждом месяце.
        """
        if not income_txs:
            return 0.0

        month_first_day: dict = {}
        for t in income_txs:
            dt = self._get_date(t)
            if dt is None:
                continue
            key = (dt.year, dt.month)
            if key not in month_first_day or dt.day < month_first_day[key]:
                month_first_day[key] = dt.day

        days = list(month_first_day.values())
        if len(days) < 2:
            return 0.5  # Недостаточно данных

        mean_day = sum(days) / len(days)
        variance = sum((d - mean_day) ** 2 for d in days) / len(days)
        std_dev = math.sqrt(variance)

        # std_dev <= 3 дня → очень регулярно (1.0), std_dev >= 15 → хаотично (0.0)
        return max(0.0, 1.0 - std_dev / 15.0)

    def _classify(self, p: AccountProfile) -> AccountType:
        """Классифицировать аккаунт по собранному профилю."""

        # Пенсионер: государственный доход, низкий уровень
        if p.has_pension_flag and p.avg_monthly_income < 300_000:
            return AccountType.PENSIONER

        # Трейдер: активная крипто-деятельность + высокий pass-through
        if p.has_crypto_activity and p.pass_through_ratio > 0.6:
            return AccountType.TRADER

        # Зарплатный сотрудник: регулярный доход, стабильная зарплата
        # v4.2: расширен до 8 источников — кэшбэк, переводы друзей это нормально
        if (p.has_salary_flag and
                p.income_source_count <= 8 and
                p.income_regularity_score >= 0.5 and
                p.monthly_income_cv <= 0.35):
            return AccountType.SALARY_EMPLOYEE

        # Владелец бизнеса: много источников дохода И много получателей И высокий оборот
        # v4.2: ужесточены пороги — требуем 10+ источников + 30+ получателей + доход > 2M
        if (p.unique_income_sources > 10 and
                p.unique_expense_destinations > 30 and
                p.avg_monthly_income > 2_000_000):
            return AccountType.BUSINESS_OWNER

        # Фрилансер: несколько источников, нерегулярный доход
        if (p.income_source_count >= 3 and
                p.monthly_income_cv > 0.30 and
                not p.has_salary_flag):
            return AccountType.FREELANCER

        # Студент / низкий доход
        if p.avg_monthly_income < 150_000:
            return AccountType.STUDENT

        return AccountType.UNKNOWN
