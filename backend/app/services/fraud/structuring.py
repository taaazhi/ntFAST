"""
Обнаружение структурирования — дробление сумм для обхода порогов отчётности
"""
import logging
from typing import List, Dict, Optional, Set
from datetime import timedelta
from collections import defaultdict
from ..bank_analyzer.base_parser import Transaction
from .models import StructuringResult, AccountProfile, AccountType

logger = logging.getLogger(__name__)

# Пороги для Казахстана
KZ_AML_THRESHOLD = 1_000_000       # Регуляторный порог обязательного сообщения
KZ_ENHANCED_DD = 3_000_000          # Усиленная проверка
JUST_UNDER_PCT = 0.95               # 95% от порога (was 0.90 — too many false positives on rent/salary)

# Ключевые слова для исключения из structuring-проверки (регулярные платежи)
WHITELIST_KEYWORDS = {"АРЕНДА", "ИПОТЕКА", "КРЕДИТ", "СТРАХОВ", "ЗАРПЛАТА", "ПЕНСИЯ"}


class StructuringDetector:
    """Обнаружение структурирования (smurfing, split transactions)"""

    def analyze(
        self,
        transactions: List[Transaction],
        profile: Optional[AccountProfile] = None
    ) -> StructuringResult:
        result = StructuringResult()
        if len(transactions) < 5:
            return result

        if profile is None:
            profile = AccountProfile()

        # Pre-filter: exclude whitelisted and recurring transactions
        filtered = self._exclude_whitelisted(transactions)
        recurring_ids = self._find_recurring_tx_ids(filtered)
        filtered = [tx for tx in filtered if id(tx) not in recurring_ids]

        result.just_under_threshold = self._detect_just_under(filtered, profile)
        result.split_groups = self._detect_splits(filtered, profile)
        result.smurfing_patterns = self._detect_smurfing(filtered, profile)

        # Risk score — capped at 70 to reduce structuring module influence
        score = 0
        if result.just_under_threshold:
            score += min(30, len(result.just_under_threshold) * 10)
        if result.split_groups:
            score += min(40, len(result.split_groups) * 15)
        if result.smurfing_patterns:
            score += min(30, len(result.smurfing_patterns) * 15)

        result.risk_score = min(70, score)
        return result

    @staticmethod
    def _is_whitelisted(tx: Transaction) -> bool:
        """Проверка описания на ключевые слова регулярных платежей."""
        desc = ((tx.description or "") + " " + (tx.counterparty or "")).upper()
        return any(kw in desc for kw in WHITELIST_KEYWORDS)

    def _exclude_whitelisted(self, txs: List[Transaction]) -> List[Transaction]:
        """Исключить транзакции с ключевыми словами регулярных платежей."""
        return [tx for tx in txs if not self._is_whitelisted(tx)]

    def _find_recurring_tx_ids(self, txs: List[Transaction]) -> Set[int]:
        """
        Найти recurring-платежи: одинаковая сумма (±3%) одному контрагенту
        с интервалом ~25-35 дней, 2+ раза → исключить из structuring.
        """
        recurring_ids: Set[int] = set()
        # Группировка по контрагенту
        by_cp = defaultdict(list)
        for tx in txs:
            cp = (tx.counterparty or tx.description or "").strip()
            if cp:
                by_cp[cp].append(tx)

        for cp, cp_txs in by_cp.items():
            if len(cp_txs) < 2:
                continue
            cp_txs_sorted = sorted(cp_txs, key=lambda t: t.date)
            for i in range(len(cp_txs_sorted)):
                for j in range(i + 1, len(cp_txs_sorted)):
                    a, b = cp_txs_sorted[i], cp_txs_sorted[j]
                    # Проверяем ±3% по сумме
                    if abs(a.amount) == 0:
                        continue
                    ratio = abs(abs(b.amount) - abs(a.amount)) / abs(a.amount)
                    if ratio > 0.03:
                        continue
                    # Проверяем интервал 25-35 дней
                    gap = abs((b.date - a.date).days)
                    if 25 <= gap <= 35:
                        recurring_ids.add(id(a))
                        recurring_ids.add(id(b))
        return recurring_ids

    def _get_effective_threshold(self, profile: AccountProfile) -> float:
        """
        Контекстный порог структурирования.
        Для SALARY_EMPLOYEE: всегда строгий регуляторный 1M.
        Для остальных: max(1M, 80% от среднего месячного дохода).
        """
        if profile.account_type == AccountType.SALARY_EMPLOYEE:
            return KZ_AML_THRESHOLD

        if profile.avg_monthly_income > 0:
            income_based = profile.avg_monthly_income * 0.8
            return max(KZ_AML_THRESHOLD, income_based)

        return KZ_AML_THRESHOLD

    def _get_min_significant(self, profile: AccountProfile) -> float:
        """Минимальная значимая сумма для smurfing (относительная к доходу)."""
        if profile.avg_monthly_income > 0:
            return max(100_000, profile.avg_monthly_income * 0.1)
        return 100_000

    def _detect_just_under(
        self,
        txs: List[Transaction],
        profile: AccountProfile
    ) -> List[Dict]:
        """Суммы 90-99% от порога отчётности (с контекстным порогом)"""
        threshold = self._get_effective_threshold(profile)
        low = threshold * JUST_UNDER_PCT
        high = threshold

        alerts = []
        for tx in txs:
            abs_amount = abs(tx.amount)
            if low <= abs_amount < high:
                alerts.append({
                    "date": tx.date.isoformat(),
                    "amount": abs_amount,
                    "threshold": threshold,
                    "pct_of_threshold": round(abs_amount / threshold * 100, 1),
                    "counterparty": tx.counterparty or tx.description,
                    "account_type": profile.account_type.value,
                })

        return alerts

    def _detect_splits(
        self,
        txs: List[Transaction],
        profile: AccountProfile
    ) -> List[Dict]:
        """
        Обнаружение дробления: несколько сумм одному контрагенту за 24ч,
        которые в совокупности превышают порог
        """
        threshold = self._get_effective_threshold(profile)

        outgoing = [tx for tx in txs if tx.amount < 0]
        outgoing.sort(key=lambda t: t.date)

        # Группировка по контрагенту + дню
        groups = defaultdict(list)
        for tx in outgoing:
            cp = tx.counterparty or tx.description
            day = tx.date.date()
            groups[(cp, day)].append(tx)

        split_alerts = []
        for (cp, day), group_txs in groups.items():
            # v4.2: требуем 3+ транзакций — 2 перевода одному человеку это нормально
            if len(group_txs) < 3:
                continue

            total = sum(abs(t.amount) for t in group_txs)
            if total >= threshold * 0.8:
                split_alerts.append({
                    "counterparty": cp,
                    "date": day.isoformat(),
                    "transaction_count": len(group_txs),
                    "individual_amounts": [abs(t.amount) for t in group_txs],
                    "total_amount": total,
                    "exceeds_threshold": total >= threshold,
                    "threshold_used": threshold,
                })

        return sorted(split_alerts, key=lambda a: a["total_amount"], reverse=True)[:10]

    def _detect_smurfing(
        self,
        txs: List[Transaction],
        profile: AccountProfile
    ) -> List[Dict]:
        """
        Обнаружение smurfing: одинаковые суммы разным контрагентам
        за короткий период
        """
        min_significant = self._get_min_significant(profile)

        outgoing = [tx for tx in txs if tx.amount < 0]

        # Группировка по сумме (с допуском ±1%)
        amount_groups = defaultdict(list)
        for tx in outgoing:
            rounded = round(abs(tx.amount), -2)  # Округлить до 100
            if rounded >= min_significant:
                amount_groups[rounded].append(tx)

        patterns = []
        for amount, group in amount_groups.items():
            if len(group) < 6:
                continue

            # Разные контрагенты? Требуем минимум 6 (was 4 — too many false positives)
            counterparties = set(t.counterparty or t.description for t in group)
            if len(counterparties) >= 6:
                dates = sorted(t.date for t in group)
                span = (dates[-1] - dates[0]).days

                patterns.append({
                    "amount": amount,
                    "occurrence_count": len(group),
                    "unique_counterparties": len(counterparties),
                    "counterparties": list(counterparties)[:5],
                    "date_span_days": span,
                    "total_amount": amount * len(group),
                    "min_significant_threshold": min_significant,
                })

        return sorted(patterns, key=lambda p: p["total_amount"], reverse=True)[:5]
