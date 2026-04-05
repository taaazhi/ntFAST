"""
Velocity Checks — обнаружение быстрых серий транзакций и спайков активности
v4.1: Снижены ложные срабатывания, улучшены пороги для реальных банковских выписок
"""
import logging
from datetime import timedelta
from typing import List, Dict, Optional
from collections import defaultdict
from ..bank_analyzer.base_parser import Transaction
from .models import VelocityResult, AccountProfile, AccountType

logger = logging.getLogger(__name__)

# Контекстные пороги суточных оттоков (доля от avg_monthly_income)
VELOCITY_THRESHOLDS = {
    AccountType.BUSINESS_OWNER:  2.0,   # 200% — норма для бизнеса
    AccountType.TRADER:          1.5,   # 150% — трейдер может гнать большие объёмы
    AccountType.FREELANCER:      0.8,   # 80%
    AccountType.SALARY_EMPLOYEE: 0.5,   # 50%
    AccountType.PENSIONER:       0.4,   # 40%
    AccountType.STUDENT:         0.6,   # 60%
    AccountType.UNKNOWN:         0.7,   # 70%
}

# Пороги burst (количество транзакций за 2ч)
BURST_THRESHOLDS = {
    AccountType.BUSINESS_OWNER:  20,
    AccountType.TRADER:          15,
    AccountType.FREELANCER:      8,
    AccountType.SALARY_EMPLOYEE: 7,
    AccountType.PENSIONER:       5,
    AccountType.STUDENT:         6,
    AccountType.UNKNOWN:         7,
}

# Абсолютный минимальный порог (чтобы не флагировать мелкие суммы)
MIN_ABSOLUTE_FLOOR = 100_000   # 100 000 KZT


class VelocityAnalyzer:
    """Анализ скорости и частоты транзакций"""

    def analyze(
        self,
        transactions: List[Transaction],
        profile: Optional[AccountProfile] = None
    ) -> VelocityResult:
        result = VelocityResult()
        if len(transactions) < 5:
            return result

        if profile is None:
            profile = AccountProfile()

        sorted_txs = sorted(transactions, key=lambda t: t.date)

        burst_threshold = BURST_THRESHOLDS.get(profile.account_type, 7)

        result.burst_alerts = self._detect_bursts(sorted_txs, threshold=burst_threshold)
        result.daily_spikes = self._detect_daily_spikes(sorted_txs)
        result.amount_acceleration = self._detect_amount_acceleration(sorted_txs, profile)
        result.counterparty_churn = self._detect_counterparty_churn(sorted_txs)

        # ── Вычислить risk_score — сбалансированная оценка ──
        # v4.2: Повышены пороги — обычный пользователь Kaspi Gold может делать
        # 20-40 покупок в день (шоппинг, кофе, такси) без подозрения
        score = 0

        # Burst alerts: серьёзно только при множественных
        if len(result.burst_alerts) >= 5:
            score += 30
        elif len(result.burst_alerts) >= 3:
            score += 15
        elif len(result.burst_alerts) >= 1:
            score += 5

        # Daily spikes: только экстремальные (Z > 4.0) или повторяющиеся (Z > 3.0)
        extreme_spikes = [s for s in result.daily_spikes if s.get("z_score", 0) > 4.0]
        high_z_spikes = [s for s in result.daily_spikes if 3.0 < s.get("z_score", 0) <= 4.0]

        if len(extreme_spikes) >= 3:
            score += 25
        elif len(extreme_spikes) >= 1:
            score += 10

        if len(high_z_spikes) >= 5:
            score += 15
        elif len(high_z_spikes) >= 3:
            score += 8

        # Amount acceleration — только при частых
        if len(result.amount_acceleration) >= 5:
            score += 20
        elif len(result.amount_acceleration) >= 3:
            score += 10
        elif len(result.amount_acceleration) >= 1:
            score += 3

        # Counterparty churn — только при серьёзном
        if result.counterparty_churn.get("high_churn_days", 0) >= 5:
            score += 15
        elif result.counterparty_churn.get("high_churn_days", 0) >= 2:
            score += 5

        result.risk_score = min(100, score)
        return result

    def _detect_bursts(self, txs: List[Transaction], window_hours: int = 2,
                       threshold: int = 7) -> List[Dict]:
        """Обнаружение серий: >threshold транзакций за window_hours часов"""
        alerts = []
        window = timedelta(hours=window_hours)
        used_indices = set()

        for i, tx in enumerate(txs):
            if i in used_indices:
                continue

            count = 1
            total = abs(tx.amount)
            indices = [i]
            j = i + 1

            while j < len(txs) and (txs[j].date - tx.date) <= window:
                count += 1
                total += abs(txs[j].amount)
                indices.append(j)
                j += 1

            if count >= threshold:
                alerts.append({
                    "date": tx.date.isoformat(),
                    "transaction_count": count,
                    "total_amount": round(total, 2),
                    "window_hours": window_hours,
                })
                # Пометить все транзакции в этом burst чтобы не дублировать
                used_indices.update(indices)

        return alerts[:10]

    def _detect_daily_spikes(self, txs: List[Transaction]) -> List[Dict]:
        """Обнаружение дней с аномальным количеством транзакций (Z-score > 3.0)"""
        daily_counts = defaultdict(int)
        daily_amounts = defaultdict(float)

        for tx in txs:
            day = tx.date.date()
            daily_counts[day] += 1
            daily_amounts[day] += abs(tx.amount)

        if not daily_counts:
            return []

        counts = list(daily_counts.values())
        mean_count = sum(counts) / len(counts)

        # Нужно минимум 7 дней данных для осмысленной статистики
        if len(counts) < 7:
            return []

        variance = sum((c - mean_count) ** 2 for c in counts) / (len(counts) - 1)
        std_count = variance ** 0.5

        spikes = []
        if std_count > 0:
            # Минимальный абсолютный порог: день должен иметь >= 3x среднего И >= 8 операций
            # v4.2: повышен — Kaspi Gold пользователи часто делают 10-15 покупок/день
            min_count_threshold = max(mean_count * 3, 8)

            for day, count in daily_counts.items():
                z = (count - mean_count) / std_count
                if z > 3.0 and count >= min_count_threshold:
                    spikes.append({
                        "date": day.isoformat(),
                        "transaction_count": count,
                        "total_amount": round(daily_amounts[day], 2),
                        "z_score": round(z, 2),
                        "avg_daily": round(mean_count, 1),
                    })

        return sorted(spikes, key=lambda x: x["z_score"], reverse=True)[:10]

    def _detect_amount_acceleration(
        self,
        txs: List[Transaction],
        profile: AccountProfile
    ) -> List[Dict]:
        """Обнаружение резких крупных оттоков с контекстным порогом"""
        monthly_income = defaultdict(float)
        for tx in txs:
            if tx.amount > 0:
                month_key = (tx.date.year, tx.date.month)
                monthly_income[month_key] += tx.amount

        # Используем avg_monthly_income из профиля или вычисляем из транзакций
        if profile.avg_monthly_income > 0:
            avg_monthly = profile.avg_monthly_income
        elif monthly_income:
            avg_monthly = sum(monthly_income.values()) / len(monthly_income)
        else:
            return []

        if avg_monthly <= 0:
            return []

        # Контекстный порог по типу аккаунта
        threshold_pct = VELOCITY_THRESHOLDS.get(profile.account_type, 0.7)
        threshold = max(avg_monthly * threshold_pct, MIN_ABSOLUTE_FLOOR)

        alerts = []
        expenses = [tx for tx in txs if tx.amount < 0]
        used_indices = set()

        for i, tx in enumerate(expenses):
            if i in used_indices:
                continue

            window_sum = abs(tx.amount)
            indices = [i]
            j = i + 1
            while j < len(expenses) and (expenses[j].date - tx.date) <= timedelta(hours=24):
                window_sum += abs(expenses[j].amount)
                indices.append(j)
                j += 1

            if window_sum >= threshold:
                alerts.append({
                    "date": tx.date.isoformat(),
                    "amount_24h": round(window_sum, 2),
                    "pct_of_monthly_income": round(window_sum / avg_monthly * 100, 1),
                    "threshold_used": round(threshold_pct * 100, 0),
                    "account_type": profile.account_type.value,
                })
                used_indices.update(indices)

        return alerts[:10]

    def _detect_counterparty_churn(self, txs: List[Transaction]) -> Dict:
        """Анализ скорости появления новых контрагентов"""
        seen = set()
        new_per_day = defaultdict(int)

        for tx in sorted(txs, key=lambda t: t.date):
            cp = tx.counterparty or tx.description
            if cp and cp not in seen:
                seen.add(cp)
                new_per_day[tx.date.date()] += 1

        if not new_per_day:
            return {}

        values = list(new_per_day.values())
        avg = sum(values) / len(values)
        # Повышаем порог: high churn = > 4x среднего И минимум 5 новых за день
        high_churn_days = sum(1 for v in values if v > max(avg * 4, 5))

        return {
            "total_unique": len(seen),
            "avg_new_per_day": round(avg, 2),
            "max_new_per_day": max(values) if values else 0,
            "high_churn_days": high_churn_days,
        }
