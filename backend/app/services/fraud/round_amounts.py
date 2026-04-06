"""
Детектор подозрительных круглых сумм

Суть: мошенники часто переводят круглые суммы (100 000, 500 000, 999 000 KZT).
Реальные покупки редко бывают идеально круглыми (цена товара = 47 890 KZT).
Особенно подозрительно: суммы "чуть ниже порога" (999K вместо 1M) — это structuring,
но круглые суммы сами по себе — отдельный сигнал.
"""
import logging
from typing import List, Dict, Optional
from collections import Counter
from ..bank_analyzer.base_parser import Transaction, TransactionType
from .models import AccountProfile, AccountType

logger = logging.getLogger(__name__)

# Минимальная сумма для анализа
MIN_AMOUNT_KZT = 50_000  # 50k KZT

# Пороги "круглости"
ROUND_THRESHOLDS = [
    100_000,     # 100K
    200_000,     # 200K
    250_000,     # 250K
    300_000,     # 300K
    500_000,     # 500K
    1_000_000,   # 1M
    2_000_000,   # 2M
    5_000_000,   # 5M
    10_000_000,  # 10M
]

# Типы транзакций, которые обычно НЕ бывают круглыми (покупки, комиссии)
NORMALLY_NON_ROUND_TYPES = {
    TransactionType.EXPENSE,
    TransactionType.FEE,
}


class RoundAmountResult:
    """Результат анализа круглых сумм"""
    def __init__(self):
        self.round_transactions: List[Dict] = []    # Все круглые транзакции
        self.round_count: int = 0                    # Количество круглых
        self.round_ratio: float = 0.0                # Доля круглых от общего числа
        self.round_total_amount: float = 0.0         # Общая сумма круглых
        self.amount_distribution: Dict[str, int] = {}  # Распределение по "ступеням"
        self.consecutive_round: List[Dict] = []      # Последовательные круглые
        self.risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "round_count": self.round_count,
            "round_ratio": round(self.round_ratio, 3),
            "round_total_amount": round(self.round_total_amount, 2),
            "amount_distribution": self.amount_distribution,
            "consecutive_round": self.consecutive_round[:5],
            "round_transactions": self.round_transactions[:15],
            "risk_score": self.risk_score,
        }


class RoundAmountDetector:
    """Детектор подозрительных круглых сумм"""

    def analyze(
        self,
        transactions: List[Transaction],
        profile: Optional[AccountProfile] = None
    ) -> RoundAmountResult:
        result = RoundAmountResult()

        if not transactions or len(transactions) < 5:
            return result

        if profile is None:
            profile = AccountProfile()

        # Фильтруем: только ИСХОДЯЩИЕ переводы выше порога
        # Зарплата, пенсия, депозиты, ATM, входящие — естественно круглые
        relevant_txs = [
            tx for tx in transactions
            if abs(tx.amount) >= MIN_AMOUNT_KZT
            and tx.amount < 0                          # Только расходы/исходящие
            and not tx.is_salary                       # Не зарплата
            and not tx.is_pension_benefit               # Не пенсия/пособие
            and not tx.is_deposit_operation             # Не депозитные операции
            and not tx.is_atm                          # Не ATM (снятие всегда круглое)
            and not tx.is_cash_operation               # Не наличные
            and tx.type not in NORMALLY_NON_ROUND_TYPES  # Не комиссии
            and not self._is_regular_payment(tx)        # Не регулярные платежи
        ]

        if not relevant_txs or len(relevant_txs) < 3:
            return result

        sorted_txs = sorted(relevant_txs, key=lambda t: t.date)

        # ── 1. Определить круглые транзакции ──
        round_txs = []
        for tx in sorted_txs:
            amount = abs(tx.amount)
            roundness = self._get_roundness_level(amount)

            if roundness > 0:
                round_txs.append(tx)
                result.round_transactions.append({
                    "date": tx.date.isoformat(),
                    "amount": tx.amount,
                    "abs_amount": amount,
                    "counterparty": tx.counterparty or "",
                    "type": tx.type.value,
                    "roundness_level": roundness,
                    "description": tx.description[:80],
                })

        result.round_count = len(round_txs)
        result.round_ratio = len(round_txs) / len(relevant_txs) if relevant_txs else 0
        result.round_total_amount = sum(abs(tx.amount) for tx in round_txs)

        # ── 2. Распределение по ступеням ──
        distribution = Counter()
        for tx in round_txs:
            amount = abs(tx.amount)
            bucket = self._amount_bucket(amount)
            distribution[bucket] += 1
        result.amount_distribution = dict(distribution.most_common())

        # ── 3. Последовательные круглые суммы ──
        result.consecutive_round = self._find_consecutive_rounds(sorted_txs)

        # ── 4. Скоринг ──
        score = 0.0

        # Доля круглых от исходящих (relevant_txs уже отфильтрован на исходящие)
        # Повышенные пороги: в Казахстане круглые суммы — норма (аренда, ЖКХ, переводы)
        if result.round_ratio > 0.85:
            score += 20  # >85% исходящих — круглые суммы
        elif result.round_ratio > 0.75:
            score += 12
        elif result.round_ratio > 0.60:
            score += 5

        # Крупные круглые суммы (>1M) — только если много
        large_round = [
            tx for tx in round_txs
            if abs(tx.amount) >= 1_000_000
        ]
        if len(large_round) >= 5:
            score += 20
        elif len(large_round) >= 3:
            score += 10

        # Идеально круглые (100K, 500K, 1M — делятся на 100K без остатка)
        perfectly_round = [
            tx for tx in round_txs
            if abs(tx.amount) % 100_000 == 0
        ]
        if len(perfectly_round) >= 10:
            score += 15
        elif len(perfectly_round) >= 5:
            score += 8

        # Последовательные круглые
        if result.consecutive_round:
            max_consecutive = max(c["count"] for c in result.consecutive_round)
            if max_consecutive >= 7:
                score += 15
            elif max_consecutive >= 5:
                score += 8

        # Модуль ограничен максимум 60 баллами — круглые суммы сами по себе слабый сигнал
        result.risk_score = min(60, round(score, 1))

        logger.info(
            f"RoundAmounts: {result.round_count}/{len(relevant_txs)} round "
            f"({result.round_ratio:.1%}), score={result.risk_score}"
        )

        return result

    @staticmethod
    def _is_regular_payment(tx: Transaction) -> bool:
        """Проверить, является ли транзакция регулярным платежом (депозит, подписка, аренда)"""
        desc = ((tx.description or "") + " " + (tx.counterparty or "")).upper()
        regular_keywords = [
            "ДЕПОЗИТ", "DEPOSIT", "АРЕНДА", "RENT", "ИПОТЕКА", "MORTGAGE",
            "КРЕДИТ", "CREDIT", "СТРАХОВ", "INSURANCE", "ЖКХ", "КОММУНАЛ",
            "БАНКОМАТ", "ATM", "KASPI ДЕПОЗИТ"
        ]
        return any(kw in desc for kw in regular_keywords)

    def _get_roundness_level(self, amount: float) -> int:
        """
        Определить уровень "круглости" суммы.
        0 = не круглая, 1 = слабо круглая, 2 = круглая, 3 = идеально круглая
        """
        if amount < MIN_AMOUNT_KZT:
            return 0

        # Идеально круглая (делится на 100K)
        if amount % 100_000 == 0:
            return 3

        # Круглая (делится на 50K)
        if amount % 50_000 == 0:
            return 2

        # Слабо круглая (делится на 10K)
        if amount % 10_000 == 0:
            return 1

        return 0

    def _amount_bucket(self, amount: float) -> str:
        """Классифицировать сумму в человекочитаемую категорию"""
        if amount >= 10_000_000:
            return "10M+"
        elif amount >= 5_000_000:
            return "5M-10M"
        elif amount >= 1_000_000:
            return "1M-5M"
        elif amount >= 500_000:
            return "500K-1M"
        elif amount >= 100_000:
            return "100K-500K"
        else:
            return "50K-100K"

    def _find_consecutive_rounds(self, sorted_txs: List[Transaction]) -> List[Dict]:
        """Найти серии подряд идущих круглых транзакций"""
        sequences = []
        current_seq = []

        for tx in sorted_txs:
            if self._get_roundness_level(abs(tx.amount)) >= 2:
                current_seq.append(tx)
            else:
                if len(current_seq) >= 3:
                    sequences.append({
                        "start": current_seq[0].date.isoformat(),
                        "end": current_seq[-1].date.isoformat(),
                        "count": len(current_seq),
                        "amounts": [tx.amount for tx in current_seq],
                        "total": round(sum(abs(tx.amount) for tx in current_seq), 2),
                    })
                current_seq = []

        # Последняя серия
        if len(current_seq) >= 3:
            sequences.append({
                "start": current_seq[0].date.isoformat(),
                "end": current_seq[-1].date.isoformat(),
                "count": len(current_seq),
                "amounts": [tx.amount for tx in current_seq],
                "total": round(sum(abs(tx.amount) for tx in current_seq), 2),
            })

        return sequences
