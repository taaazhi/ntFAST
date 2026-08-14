"""
Financial Analytics Engine
Comprehensive metrics and analysis
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import statistics
from dataclasses import dataclass
import math


@dataclass
class MonthlyStats:
    """Monthly financial statistics"""
    month: str
    income: float = 0.0
    expense: float = 0.0
    balance: float = 0.0
    transaction_count: int = 0


class FinancialAnalytics:
    """Calculates comprehensive financial analytics"""

    def __init__(self, transactions: List, account_info):
        self.transactions = transactions
        self.account = account_info
        self.categorized_transactions = []

    def set_categorized_transactions(self, categorized: List[Dict]):
        """Set transactions with categories"""
        self.categorized_transactions = categorized

    def calculate_all(self) -> Dict[str, Any]:
        """Calculate all analytics"""
        return {
            "general_stats": self._general_stats(),
            "monthly_breakdown": self._monthly_breakdown(),
            "category_breakdown": self._category_breakdown(),
            "top_merchants": self._top_merchants(),
            "top_contacts": self._top_contacts(),
            "recurring_payments": self._detect_recurring(),
            "anomalies": self._detect_anomalies(),
            "foreign_currency": self._foreign_currency_analysis(),
            "financial_health": self._financial_health(),
            "weekday_analysis": self._weekday_analysis(),
            "daily_patterns": self._daily_patterns(),
        }

    def _general_stats(self) -> Dict[str, Any]:
        """Calculate general statistics"""
        incomes = [t.amount for t in self.transactions if t.amount > 0]
        expenses = [abs(t.amount) for t in self.transactions if t.amount < 0]

        total_income = sum(incomes)
        total_expense = sum(expenses)

        return {
            "total_transactions": len(self.transactions),
            "total_income": total_income,
            "total_expense": total_expense,
            "net_flow": total_income - total_expense,
            "balance_start": self.account.balance_start,
            "balance_end": self.account.balance_end,
            "avg_daily_expense": self._calc_avg_daily(total_expense),
            "median_transaction": statistics.median([abs(t.amount) for t in self.transactions]) if self.transactions else 0,
            "avg_income": statistics.mean(incomes) if incomes else 0,
            "avg_expense": statistics.mean(expenses) if expenses else 0,
            "income_transactions": len(incomes),
            "expense_transactions": len(expenses),
        }

    def _calc_avg_daily(self, total: float) -> float:
        """Рассчитать среднедневной показатель по реальному периоду выписки."""
        if not self.transactions:
            return 0.0
        # Попробуем взять период из account_info
        if hasattr(self.account, 'period_start') and hasattr(self.account, 'period_end') and self.account.period_start and self.account.period_end:
            days = (self.account.period_end - self.account.period_start).days
        else:
            # Fallback: вычисляем по датам транзакций
            dates = [t.date for t in self.transactions if hasattr(t, 'date') and t.date]
            if len(dates) >= 2:
                days = (max(dates) - min(dates)).days
            else:
                days = 30  # default
        days = max(days, 1)  # Защита от деления на 0
        return round(total / days, 2)

    def _monthly_breakdown(self) -> List[Dict[str, Any]]:
        """Calculate monthly income/expense breakdown"""
        monthly = defaultdict(lambda: {"income": 0, "expense": 0, "count": 0})

        for tx in self.transactions:
            month_key = tx.date.strftime("%Y-%m")
            if tx.amount > 0:
                monthly[month_key]["income"] += tx.amount
            else:
                monthly[month_key]["expense"] += abs(tx.amount)
            monthly[month_key]["count"] += 1

        result = []
        for month, data in sorted(monthly.items()):
            result.append({
                "month": month,
                "month_name": self._month_name(month),
                "income": data["income"],
                "expense": data["expense"],
                "balance": data["income"] - data["expense"],
                "transaction_count": data["count"]
            })

        return result

    def _month_name(self, month_str: str) -> str:
        """Convert YYYY-MM to readable name"""
        months_ru = [
            "", "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
            "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"
        ]
        year, month = month_str.split("-")
        return f"{months_ru[int(month)]} {year}"

    def _category_breakdown(self) -> Dict[str, Any]:
        """Breakdown by category"""
        if not self.categorized_transactions:
            return {"expense": {}, "income": {}}

        expense_cats = defaultdict(lambda: {"amount": 0, "count": 0, "transactions": []})
        income_cats = defaultdict(lambda: {"amount": 0, "count": 0, "transactions": []})

        for tx in self.categorized_transactions:
            amount = tx["amount"]
            category = tx["category"]

            if amount < 0:
                expense_cats[category]["amount"] += abs(amount)
                expense_cats[category]["count"] += 1
            else:
                income_cats[category]["amount"] += amount
                income_cats[category]["count"] += 1

        # Calculate percentages
        total_expense = sum(c["amount"] for c in expense_cats.values())
        total_income = sum(c["amount"] for c in income_cats.values())

        expense_result = []
        for cat, data in sorted(expense_cats.items(), key=lambda x: x[1]["amount"], reverse=True):
            expense_result.append({
                "category": cat,
                "amount": data["amount"],
                "count": data["count"],
                "percentage": (data["amount"] / total_expense * 100) if total_expense > 0 else 0
            })

        income_result = []
        for cat, data in sorted(income_cats.items(), key=lambda x: x[1]["amount"], reverse=True):
            income_result.append({
                "category": cat,
                "amount": data["amount"],
                "count": data["count"],
                "percentage": (data["amount"] / total_income * 100) if total_income > 0 else 0
            })

        return {
            "expense": expense_result,
            "income": income_result,
            "total_expense": total_expense,
            "total_income": total_income
        }

    def _top_merchants(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Top merchants by spending"""
        merchants = defaultdict(lambda: {"amount": 0, "count": 0})

        for tx in self.transactions:
            if tx.type == 'Покупка' and tx.amount < 0:
                merchant = tx.details[:40]  # Truncate long names
                merchants[merchant]["amount"] += abs(tx.amount)
                merchants[merchant]["count"] += 1

        sorted_merchants = sorted(
            merchants.items(),
            key=lambda x: x[1]["amount"],
            reverse=True
        )[:limit]

        return [
            {
                "merchant": name,
                "amount": data["amount"],
                "count": data["count"],
                "avg_transaction": data["amount"] / data["count"]
            }
            for name, data in sorted_merchants
        ]

    def _top_contacts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Top contacts by transfer volume"""
        contacts = defaultdict(lambda: {"sent": 0, "received": 0, "count": 0})

        for tx in self.transactions:
            if tx.type in ['Перевод', 'Пополнение']:
                # Extract contact name
                import re
                name_match = re.search(
                    r'([А-ЯЁа-яёӘәҒғҚқҢңӨөҰұҮүІіҺһəƏ]+\s+[А-ЯЁа-яёƏə]\.?)',
                    tx.details
                )
                if name_match:
                    contact = name_match.group(1).strip()
                    contacts[contact]["count"] += 1
                    if tx.amount < 0:
                        contacts[contact]["sent"] += abs(tx.amount)
                    else:
                        contacts[contact]["received"] += tx.amount

        sorted_contacts = sorted(
            contacts.items(),
            key=lambda x: x[1]["sent"] + x[1]["received"],
            reverse=True
        )[:limit]

        return [
            {
                "name": name,
                "sent": data["sent"],
                "received": data["received"],
                "balance": data["received"] - data["sent"],
                "count": data["count"]
            }
            for name, data in sorted_contacts
        ]

    def _detect_recurring(self) -> List[Dict[str, Any]]:
        """Detect recurring/subscription payments"""
        # Group by details and analyze frequency
        payments = defaultdict(list)

        for tx in self.transactions:
            if tx.amount < 0:
                # Normalize details for grouping
                key = self._normalize_for_recurring(tx.details)
                payments[key].append({
                    "date": tx.date,
                    "amount": abs(tx.amount),
                    "details": tx.details
                })

        recurring = []
        for key, txs in payments.items():
            if len(txs) >= 2:
                amounts = [t["amount"] for t in txs]
                # Check if amounts are similar (within 10% variance)
                if len(set(amounts)) <= 3:  # Allow some variance
                    avg_amount = statistics.mean(amounts)

                    # Check frequency
                    dates = sorted([t["date"] for t in txs])
                    if len(dates) >= 2:
                        intervals = [
                            (dates[i+1] - dates[i]).days
                            for i in range(len(dates)-1)
                        ]
                        avg_interval = statistics.mean(intervals) if intervals else 0

                        frequency = "unknown"
                        if 25 <= avg_interval <= 35:
                            frequency = "monthly"
                        elif 6 <= avg_interval <= 8:
                            frequency = "weekly"
                        elif 13 <= avg_interval <= 16:
                            frequency = "bi-weekly"
                        elif avg_interval <= 3:
                            frequency = "frequent"

                        if frequency != "unknown" or len(txs) >= 3:
                            recurring.append({
                                "name": key,
                                "count": len(txs),
                                "total_amount": sum(amounts),
                                "avg_amount": avg_amount,
                                "frequency": frequency,
                                "avg_interval_days": avg_interval,
                                "last_payment": dates[-1].isoformat()
                            })

        # Sort by total amount
        return sorted(recurring, key=lambda x: x["total_amount"], reverse=True)[:20]

    def _normalize_for_recurring(self, details: str) -> str:
        """Normalize details for recurring detection"""
        # Remove variable parts like transaction IDs, dates
        import re
        normalized = details.upper()
        # Remove numbers that look like IDs
        normalized = re.sub(r'\b\d{6,}\b', '', normalized)
        # Remove common variable suffixes
        normalized = re.sub(r'\s+\d+$', '', normalized)
        return normalized.strip()[:30]

    def _detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalous transactions"""
        anomalies = []
        expenses = [abs(t.amount) for t in self.transactions if t.amount < 0]

        if not expenses:
            return anomalies

        mean_expense = statistics.mean(expenses)
        std_expense = statistics.stdev(expenses) if len(expenses) > 1 else 0
        threshold = mean_expense + 2 * std_expense

        # Large transactions
        for tx in self.transactions:
            if tx.amount < 0 and abs(tx.amount) > threshold:
                anomalies.append({
                    "type": "large_transaction",
                    "date": tx.date.isoformat(),
                    "amount": abs(tx.amount),
                    "details": tx.details,
                    "threshold": threshold,
                    "deviation": (abs(tx.amount) - mean_expense) / std_expense if std_expense > 0 else 0
                })

        # Multiple transactions same day
        daily_counts = defaultdict(list)
        for tx in self.transactions:
            daily_counts[tx.date.date()].append(tx)

        for date, txs in daily_counts.items():
            if len(txs) >= 10:
                anomalies.append({
                    "type": "high_frequency_day",
                    "date": date.isoformat(),
                    "transaction_count": len(txs),
                    "total_amount": sum(abs(t.amount) for t in txs)
                })

        return sorted(anomalies, key=lambda x: x.get("amount", 0), reverse=True)[:20]

    def _foreign_currency_analysis(self) -> Dict[str, Any]:
        """Analyze foreign currency transactions"""
        foreign_txs = [
            tx for tx in self.transactions
            if tx.original_currency and tx.original_currency != "KZT"
        ]

        by_currency = defaultdict(lambda: {"count": 0, "total_original": 0, "total_kzt": 0})

        for tx in foreign_txs:
            curr = tx.original_currency
            by_currency[curr]["count"] += 1
            by_currency[curr]["total_original"] += abs(tx.original_amount or 0)
            by_currency[curr]["total_kzt"] += abs(tx.amount)

        result = []
        for curr, data in by_currency.items():
            avg_rate = data["total_kzt"] / data["total_original"] if data["total_original"] > 0 else 0
            result.append({
                "currency": curr,
                "transaction_count": data["count"],
                "total_original": data["total_original"],
                "total_kzt": data["total_kzt"],
                "avg_exchange_rate": avg_rate
            })

        return {
            "transactions": result,
            "total_foreign_kzt": sum(r["total_kzt"] for r in result)
        }

    # Названия категорий должны совпадать с TransactionCategorizer.EXPENSE_CATEGORIES.
    # Раньше здесь стояли строки с эмодзи ('💊 Здоровье'), а категоризатор
    # возвращает 'Здоровье' — совпадений не было никогда, и essential_ratio
    # всегда равнялся нулю, который показывался пользователю как реальный
    # показатель финансового здоровья.
    ESSENTIAL_CATEGORIES = frozenset({
        "Здоровье", "Связь и коммуналка", "Страхование", "Еда и продукты",
    })
    NON_ESSENTIAL_CATEGORIES = frozenset({
        "Игры и развлечения", "Шоппинг", "Рестораны", "Подписки и сервисы",
    })

    # Порог, ниже которого изменение баланса считается шумом, а не трендом
    TREND_THRESHOLD = 0.10

    def _financial_health(self) -> Dict[str, Any]:
        """Показатели финансового здоровья.

        Все *_rate / *_ratio возвращаются как ДОЛИ (0..1), а не проценты —
        форматирование в проценты делает потребитель. Раньше здесь было
        умножение на 100, и фронтенд умножал на 100 повторно, показывая
        накопления 20% как 2000%.
        """
        total_income = sum(t.amount for t in self.transactions if t.amount > 0)
        total_expense = sum(abs(t.amount) for t in self.transactions if t.amount < 0)

        savings_rate = (total_income - total_expense) / total_income if total_income > 0 else 0.0

        essential_expense = 0.0
        non_essential_expense = 0.0
        for tx in self.categorized_transactions or []:
            if tx["amount"] >= 0:
                continue
            category = tx.get("category") or ""
            if category in self.ESSENTIAL_CATEGORIES:
                essential_expense += abs(tx["amount"])
            elif category in self.NON_ESSENTIAL_CATEGORIES:
                non_essential_expense += abs(tx["amount"])

        # Тренд баланса. Значения должны совпадать с теми, что ожидает UI:
        # growing / declining / stable. Раньше возвращалось "improving",
        # которого фронтенд не знал, поэтому "растёт" не отображалось никогда.
        monthly = self._monthly_breakdown()
        trend = "stable"
        if len(monthly) >= 2:
            first, last = monthly[0]["balance"], monthly[-1]["balance"]
            scale = max(abs(first), abs(last), 1.0)
            delta = (last - first) / scale
            if delta > self.TREND_THRESHOLD:
                trend = "growing"
            elif delta < -self.TREND_THRESHOLD:
                trend = "declining"

        # Среднемесячные значения — по реальному числу месяцев в выписке.
        # Раньше делилось на жёсткие 12, поэтому на трёхмесячной выписке
        # средний доход занижался вчетверо.
        months = max(len(monthly), 1)
        days = self._period_days()

        return {
            "savings_rate": savings_rate,
            "essential_expenses": essential_expense,
            "non_essential_expenses": non_essential_expense,
            "essential_ratio": essential_expense / total_expense if total_expense > 0 else 0.0,
            "balance_trend": trend,
            "months_covered": months,
            "monthly_avg_income": total_income / months,
            "monthly_avg_expense": total_expense / months,
            "financial_buffer_days": (
                self.account.balance_end / (total_expense / days)
                if total_expense > 0 and days > 0 else 0.0
            ),
        }

    def _period_days(self) -> int:
        """Длительность выписки в днях (по периоду счёта либо по датам транзакций)."""
        start = getattr(self.account, "period_start", None)
        end = getattr(self.account, "period_end", None)
        if start and end:
            return max((end - start).days, 1)
        dates = [t.date for t in self.transactions if getattr(t, "date", None)]
        if len(dates) >= 2:
            return max((max(dates) - min(dates)).days, 1)
        return 30

    def _weekday_analysis(self) -> List[Dict[str, Any]]:
        """Analyze spending by day of week"""
        weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        by_weekday = defaultdict(lambda: {"amount": 0, "count": 0})

        for tx in self.transactions:
            if tx.amount < 0:
                day = tx.date.weekday()
                by_weekday[day]["amount"] += abs(tx.amount)
                by_weekday[day]["count"] += 1

        return [
            {
                "day": weekdays[i],
                "day_index": i,
                "amount": by_weekday[i]["amount"],
                "count": by_weekday[i]["count"],
                "avg_transaction": by_weekday[i]["amount"] / by_weekday[i]["count"] if by_weekday[i]["count"] > 0 else 0
            }
            for i in range(7)
        ]

    def _daily_patterns(self) -> List[Dict[str, Any]]:
        """Daily balance and spending patterns"""
        daily = defaultdict(lambda: {"income": 0, "expense": 0, "balance": 0})

        running_balance = self.account.balance_start
        for tx in sorted(self.transactions, key=lambda x: x.date):
            day = tx.date.strftime("%Y-%m-%d")
            if tx.amount > 0:
                daily[day]["income"] += tx.amount
            else:
                daily[day]["expense"] += abs(tx.amount)
            running_balance += tx.amount
            daily[day]["balance"] = running_balance

        return [
            {
                "date": date,
                "income": data["income"],
                "expense": data["expense"],
                "balance": data["balance"]
            }
            for date, data in sorted(daily.items())
        ]
