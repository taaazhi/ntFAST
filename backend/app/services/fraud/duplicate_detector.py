"""
Детектор дублирующих платежей — одинаковые суммы одному получателю за короткое время

Суть: повторный перевод той же суммы тому же получателю в течение 24 часов
может быть ошибкой, но чаще — признак мошенничества (кардинг, обнал).
Множественные одинаковые платежи разным людям — тоже подозрительно (массовая рассылка).
"""
import logging
import re
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import timedelta
from ..bank_analyzer.base_parser import Transaction
from .models import AccountProfile

logger = logging.getLogger(__name__)

# Временное окно для поиска дубликатов
DUPLICATE_WINDOW_HOURS = 24

# Минимальная сумма для проверки дубликатов (мелкие — нормально)
MIN_AMOUNT_KZT = 50_000  # 50k KZT (raised from 10k — small duplicates are normal)

# Ключевые слова для категорий, которые не должны проверяться на дубликаты
# (аренда, зарплата, ЖКХ, страховка, ипотека, кредит, абонентская плата)
WHITELIST_KEYWORDS = [
    "АРЕНДА", "ЗАРПЛАТА", "ЖКХ", "КОММУНАЛ",
    "СТРАХОВ", "ИПОТЕКА", "КРЕДИТ", "АБОНЕНТ",
]
_WHITELIST_PATTERN = re.compile("|".join(WHITELIST_KEYWORDS), re.IGNORECASE)

# Параметры детекции рекуррентных (периодических) платежей
RECURRING_INTERVAL_DAYS = 30       # ожидаемый интервал между платежами
RECURRING_INTERVAL_TOLERANCE = 5   # допустимое отклонение ±дней
RECURRING_AMOUNT_TOLERANCE = 0.02  # допустимое отклонение суммы ±2%


class DuplicatePaymentResult:
    """Результат анализа дублирующих платежей"""
    def __init__(self):
        self.duplicate_groups: List[Dict] = []       # Группы дублирующих платежей
        self.same_amount_diff_recipient: List[Dict] = []  # Одна сумма → разные получатели
        self.total_duplicates: int = 0
        self.total_duplicate_amount: float = 0.0
        self.risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "duplicate_groups": self.duplicate_groups[:10],
            "same_amount_diff_recipient": self.same_amount_diff_recipient[:10],
            "total_duplicates": self.total_duplicates,
            "total_duplicate_amount": round(self.total_duplicate_amount, 2),
            "risk_score": self.risk_score,
        }


class DuplicatePaymentDetector:
    """Детектор повторных/дублирующих платежей"""

    def analyze(
        self,
        transactions: List[Transaction],
        profile: Optional[AccountProfile] = None
    ) -> DuplicatePaymentResult:
        result = DuplicatePaymentResult()

        if not transactions or len(transactions) < 3:
            return result

        # Только исходящие транзакции (исключая whitelisted категории)
        outgoing = [
            tx for tx in transactions
            if tx.amount < 0
            and abs(tx.amount) >= MIN_AMOUNT_KZT
            and not _WHITELIST_PATTERN.search(tx.description or "")
        ]

        if len(outgoing) < 2:
            return result

        sorted_txs = sorted(outgoing, key=lambda t: t.date)

        # ── 1. Дубликаты: одинаковая сумма + один получатель + <24ч ──
        result.duplicate_groups = self._find_exact_duplicates(sorted_txs)

        # ── 2. Одна сумма → разные получатели (массовая рассылка) ──
        result.same_amount_diff_recipient = self._find_same_amount_broadcast(sorted_txs)

        # Подсчёт итогов
        for group in result.duplicate_groups:
            result.total_duplicates += group["count"] - 1  # -1 потому что 1 — оригинал
            result.total_duplicate_amount += group["duplicate_amount"]

        # ── 3. Скоринг ──
        score = 0.0

        # Точные дубликаты
        if result.duplicate_groups:
            for group in result.duplicate_groups:
                if group["count"] >= 5:
                    score += 20  # 5+ одинаковых платежей (reduced from 30)
                elif group["count"] >= 3:
                    score += 20
                else:
                    score += 10

                # Бонус за крупные суммы
                if group["amount"] >= 500_000:
                    score += 10
                elif group["amount"] >= 100_000:
                    score += 5

        # Массовая рассылка одинаковой суммы разным получателям
        for broadcast in result.same_amount_diff_recipient:
            if broadcast["recipient_count"] >= 10:
                score += 35  # 10+ получателей одной суммы — очень подозрительно
            elif broadcast["recipient_count"] >= 5:
                score += 20

        result.risk_score = min(100, round(score, 1))

        logger.info(
            f"DuplicatePayments: {result.total_duplicates} duplicates, "
            f"{len(result.same_amount_diff_recipient)} broadcast patterns, "
            f"score={result.risk_score}"
        )

        return result

    def _is_recurring_pattern(self, tx_list: List[Transaction], amount: float) -> bool:
        """
        Определить, является ли набор транзакций рекуррентным (периодическим) платежом.
        Критерий: одинаковая сумма (±2%) одному получателю с интервалом ~30 дней (±5 дней).
        """
        if len(tx_list) < 2:
            return False

        sorted_by_date = sorted(tx_list, key=lambda t: t.date)
        recurring_intervals = 0
        total_intervals = 0

        for i in range(1, len(sorted_by_date)):
            days_gap = (sorted_by_date[i].date - sorted_by_date[i - 1].date).days
            # Проверяем что суммы близки (±2%)
            amt_a = abs(sorted_by_date[i - 1].amount)
            amt_b = abs(sorted_by_date[i].amount)
            if amt_a > 0 and abs(amt_a - amt_b) / amt_a <= RECURRING_AMOUNT_TOLERANCE:
                total_intervals += 1
                # Проверяем интервал ~30 дней (±5)
                if abs(days_gap - RECURRING_INTERVAL_DAYS) <= RECURRING_INTERVAL_TOLERANCE:
                    recurring_intervals += 1

        # Если большинство интервалов — месячные, считаем рекуррентным
        return total_intervals >= 2 and recurring_intervals / total_intervals >= 0.5

    def _find_exact_duplicates(self, txs: List[Transaction]) -> List[Dict]:
        """Найти одинаковые суммы одному получателю в окне 24ч"""
        groups = []
        window = timedelta(hours=DUPLICATE_WINDOW_HOURS)

        # Группируем по (counterparty, amount)
        key_txs = defaultdict(list)
        for tx in txs:
            counterparty = (tx.counterparty or tx.description[:30]).lower().strip()
            amount = round(abs(tx.amount), 2)
            key_txs[(counterparty, amount)].append(tx)

        for (counterparty, amount), tx_list in key_txs.items():
            if len(tx_list) < 2:
                continue

            # Пропускаем рекуррентные (периодические) платежи — аренда, зарплата и т.д.
            if self._is_recurring_pattern(tx_list, amount):
                logger.debug(
                    f"Skipping recurring pattern: {counterparty} x {amount} "
                    f"({len(tx_list)} payments)"
                )
                continue

            # Проверяем что хотя бы 2 транзакции попадают в окно
            for i in range(len(tx_list)):
                cluster = [tx_list[i]]
                for j in range(i + 1, len(tx_list)):
                    if tx_list[j].date - tx_list[i].date <= window:
                        cluster.append(tx_list[j])

                # v4.2: требуем 3+ дубликатов — 2 одинаковых перевода это нормально
                # (часто люди переводят 2 раза по 500k вместо 1 раз по 1M)
                if len(cluster) >= 3:
                    groups.append({
                        "counterparty": counterparty,
                        "amount": amount,
                        "count": len(cluster),
                        "duplicate_amount": amount * (len(cluster) - 1),
                        "dates": [t.date.isoformat() for t in cluster],
                        "time_span_hours": round(
                            (cluster[-1].date - cluster[0].date).total_seconds() / 3600, 1
                        ),
                    })
                    break  # Берём первый кластер для этого ключа

        # Сортируем по количеству (самые массовые сверху)
        groups.sort(key=lambda g: g["count"], reverse=True)
        return groups

    def _find_same_amount_broadcast(self, txs: List[Transaction]) -> List[Dict]:
        """Найти одну сумму, отправленную разным получателям за 48ч"""
        window = timedelta(hours=48)

        # Группируем по сумме
        amount_txs = defaultdict(list)
        for tx in txs:
            amount = round(abs(tx.amount), 2)
            amount_txs[amount].append(tx)

        broadcasts = []
        for amount, tx_list in amount_txs.items():
            if len(tx_list) < 5:
                continue

            # Уникальные получатели
            recipients = set()
            for tx in tx_list:
                counterparty = (tx.counterparty or tx.description[:30]).lower().strip()
                recipients.add(counterparty)

            if len(recipients) < 5:
                continue

            # Проверяем временное окно
            sorted_by_date = sorted(tx_list, key=lambda t: t.date)
            time_span = sorted_by_date[-1].date - sorted_by_date[0].date

            if time_span <= window:
                broadcasts.append({
                    "amount": amount,
                    "recipient_count": len(recipients),
                    "total_count": len(tx_list),
                    "recipients": list(recipients)[:10],
                    "time_span_hours": round(time_span.total_seconds() / 3600, 1),
                    "first_date": sorted_by_date[0].date.isoformat(),
                    "last_date": sorted_by_date[-1].date.isoformat(),
                })

        broadcasts.sort(key=lambda b: b["recipient_count"], reverse=True)
        return broadcasts
