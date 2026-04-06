"""
Детектор несоответствия профилю аккаунта

Суть: если аккаунт определён как "зарплатник" (200K KZT/мес), а человек
внезапно переводит 5M KZT крипте или получает 10M от неизвестного — это красный флаг.
Каждый тип аккаунта имеет свои "нормальные" рамки.
"""
import logging
from typing import List, Dict, Optional
from ..bank_analyzer.base_parser import Transaction, TransactionType, CounterpartyType
from .models import AccountProfile, AccountType

logger = logging.getLogger(__name__)


class ProfileMismatchResult:
    """Результат анализа несоответствия профилю"""
    def __init__(self):
        self.mismatches: List[Dict] = []             # Все обнаруженные несоответствия
        self.oversized_transactions: List[Dict] = [] # Транзакции слишком крупные для профиля
        self.unexpected_activity: List[Dict] = []    # Неожиданная активность для типа
        self.income_anomalies: List[Dict] = []       # Аномальные доходы
        self.risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "mismatches": self.mismatches[:15],
            "oversized_transactions": self.oversized_transactions[:10],
            "unexpected_activity": self.unexpected_activity[:10],
            "income_anomalies": self.income_anomalies[:10],
            "risk_score": self.risk_score,
        }


# Максимальная "нормальная" разовая транзакция по типу аккаунта (KZT)
MAX_NORMAL_TRANSACTION = {
    AccountType.SALARY_EMPLOYEE: 1_000_000,    # 1M — max зарплата или крупная покупка
    AccountType.PENSIONER:       300_000,       # 300K
    AccountType.STUDENT:         200_000,       # 200K
    AccountType.FREELANCER:      3_000_000,     # 3M — крупные контракты бывают
    AccountType.BUSINESS_OWNER: 50_000_000,     # 50M — бизнес
    AccountType.TRADER:         20_000_000,     # 20M — крупные сделки
    AccountType.UNKNOWN:         2_000_000,     # 2M — средний порог
}

# Множитель от среднемесячного дохода (транзакция > X * avg_monthly = подозрительно)
INCOME_MULTIPLIER_THRESHOLD = 3.0  # транзакция > 3 * среднемесячный доход


class ProfileMismatchDetector:
    """Детектор несоответствия профилю аккаунта"""

    def analyze(
        self,
        transactions: List[Transaction],
        profile: Optional[AccountProfile] = None
    ) -> ProfileMismatchResult:
        result = ProfileMismatchResult()

        if not transactions or len(transactions) < 5:
            return result

        if profile is None:
            profile = AccountProfile()

        # ── 1. Транзакции, слишком крупные для профиля ──
        max_normal = MAX_NORMAL_TRANSACTION.get(
            profile.account_type, MAX_NORMAL_TRANSACTION[AccountType.UNKNOWN]
        )

        # Также учитываем среднемесячный доход
        income_threshold = float('inf')
        if profile.avg_monthly_income > 0:
            income_threshold = profile.avg_monthly_income * INCOME_MULTIPLIER_THRESHOLD

        effective_threshold = min(max_normal, income_threshold)

        for tx in transactions:
            if abs(tx.amount) > effective_threshold:
                result.oversized_transactions.append({
                    "date": tx.date.isoformat(),
                    "amount": tx.amount,
                    "threshold": round(effective_threshold, 2),
                    "excess_ratio": round(abs(tx.amount) / effective_threshold, 2),
                    "counterparty": tx.counterparty or "",
                    "type": tx.type.value,
                    "description": tx.description[:100],
                })

        result.oversized_transactions.sort(
            key=lambda x: abs(x["amount"]), reverse=True
        )

        # ── 2. Неожиданная активность для типа аккаунта ──
        result.unexpected_activity = self._detect_unexpected_activity(
            transactions, profile
        )

        # ── 3. Аномальные доходы ──
        result.income_anomalies = self._detect_income_anomalies(
            transactions, profile
        )

        # Собираем все несоответствия вместе
        result.mismatches = (
            [{"type": "oversized", **m} for m in result.oversized_transactions[:5]] +
            [{"type": "unexpected", **m} for m in result.unexpected_activity[:5]] +
            [{"type": "income_anomaly", **m} for m in result.income_anomalies[:5]]
        )

        # ── 4. Скоринг ──
        score = 0.0

        # Oversized transactions
        if result.oversized_transactions:
            max_excess = max(t["excess_ratio"] for t in result.oversized_transactions)

            if max_excess >= 10:
                score += 35  # транзакция в 10x больше нормы
            elif max_excess >= 5:
                score += 25
            elif max_excess >= 3:
                score += 15

            # Количество oversized
            if len(result.oversized_transactions) >= 5:
                score += 15
            elif len(result.oversized_transactions) >= 3:
                score += 10

        # Unexpected activity
        if result.unexpected_activity:
            score += min(25, len(result.unexpected_activity) * 8)

        # Income anomalies
        if result.income_anomalies:
            score += min(20, len(result.income_anomalies) * 10)

        result.risk_score = min(100, round(score, 1))

        logger.info(
            f"ProfileMismatch: {len(result.oversized_transactions)} oversized, "
            f"{len(result.unexpected_activity)} unexpected, "
            f"{len(result.income_anomalies)} income anomalies, "
            f"score={result.risk_score}"
        )

        return result

    def _detect_unexpected_activity(
        self,
        transactions: List[Transaction],
        profile: AccountProfile
    ) -> List[Dict]:
        """Обнаружить активность, нехарактерную для типа аккаунта"""
        unexpected = []
        atype = profile.account_type

        for tx in transactions:
            reason = None

            # Пенсионер покупает крипту
            if atype == AccountType.PENSIONER:
                if tx.type in (TransactionType.CRYPTO_BUY, TransactionType.CRYPTO_SELL):
                    reason = "Крипто-операция от пенсионера"
                elif tx.counterparty_type == CounterpartyType.ATM and abs(tx.amount) >= 500_000:
                    reason = "Крупное снятие наличных пенсионером"

            # Студент с крупными переводами
            elif atype == AccountType.STUDENT:
                if abs(tx.amount) >= 500_000 and tx.type == TransactionType.TRANSFER_OUT:
                    reason = "Крупный исходящий перевод от студента"
                elif tx.type in (TransactionType.CRYPTO_BUY,) and abs(tx.amount) >= 200_000:
                    reason = "Студент покупает крипту на крупную сумму"

            # Зарплатник с крипто-активностью
            elif atype == AccountType.SALARY_EMPLOYEE:
                if tx.type in (TransactionType.CRYPTO_BUY, TransactionType.CRYPTO_SELL):
                    if abs(tx.amount) >= 500_000:
                        reason = "Крупная крипто-операция от зарплатника"

            # Любой тип: крупные ATM-снятия
            # v4.3: порог зависит от дохода — для фрилансера 300K снятие = норма
            atm_threshold = max(500_000, profile.avg_monthly_income * 0.7) if profile.avg_monthly_income > 0 else 500_000
            if tx.is_atm and abs(tx.amount) >= atm_threshold:
                if atype not in (AccountType.BUSINESS_OWNER, AccountType.FREELANCER):
                    if not reason:
                        reason = "Крупное снятие наличных через банкомат"

            if reason:
                unexpected.append({
                    "date": tx.date.isoformat(),
                    "amount": tx.amount,
                    "reason": reason,
                    "account_type": atype.value,
                    "counterparty": tx.counterparty or "",
                    "type": tx.type.value,
                })

        return unexpected

    def _detect_income_anomalies(
        self,
        transactions: List[Transaction],
        profile: AccountProfile
    ) -> List[Dict]:
        """Обнаружить аномальные поступления (неизвестные крупные доходы)"""
        anomalies = []

        if profile.avg_monthly_income <= 0:
            return anomalies

        threshold = profile.avg_monthly_income * 2  # Разовый доход > 2x месячного

        for tx in transactions:
            if tx.amount > 0 and tx.amount > threshold:
                # Игнорируем зарплату и пенсию — это ожидаемые доходы
                if tx.is_salary or tx.is_pension_benefit:
                    continue

                anomalies.append({
                    "date": tx.date.isoformat(),
                    "amount": tx.amount,
                    "expected_monthly": round(profile.avg_monthly_income, 2),
                    "excess_ratio": round(tx.amount / profile.avg_monthly_income, 2),
                    "counterparty": tx.counterparty or "неизвестен",
                    "type": tx.type.value,
                    "description": tx.description[:100],
                })

        anomalies.sort(key=lambda x: x["amount"], reverse=True)
        return anomalies
