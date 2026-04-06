"""
Cross-Reference анализ — корреляция источников дохода и расходов
"""
import logging
from typing import List, Dict, Optional
from datetime import timedelta
from collections import defaultdict
from ..bank_analyzer.base_parser import Transaction
from .models import CrossReferenceResult, AccountProfile, AccountType

logger = logging.getLogger(__name__)

# Ключевые слова мерчантов/банков (легальные получатели для бизнес cash-flow)
MERCHANT_KEYWORDS = ("ТОО", "АО ", "ИП ", "ООО", "ЗАО", "ОАО", "BANK", "БАНК", "KASPI")


class CrossReferenceAnalyzer:
    """Перекрёстный анализ доходов и расходов"""

    def analyze(
        self,
        transactions: List[Transaction],
        profile: Optional[AccountProfile] = None
    ) -> CrossReferenceResult:
        result = CrossReferenceResult()
        if len(transactions) < 5:
            return result

        if profile is None:
            profile = AccountProfile()

        income_txs = [t for t in transactions if t.amount > 0]
        expense_txs = [t for t in transactions if t.amount < 0]

        total_income = sum(t.amount for t in income_txs)
        total_expense = sum(abs(t.amount) for t in expense_txs)

        result.income_expense_ratio = round(total_income / total_expense, 3) if total_expense > 0 else 0

        result.rapid_pass_through = self._detect_pass_through(transactions, profile)
        result.source_destination_map = self._build_source_dest_map(transactions)

        # Risk score
        score = 0

        # Расходы СИЛЬНО превышают доход (>67% больше)
        if result.income_expense_ratio < 0.6 and total_expense > 1_000_000:
            score += 20

        # v4.2: Аномально высокий P2P оборот для обычного человека
        # Если зарплатник/пенсионер/студент имеет огромный оборот от физлиц — подозрительно
        if profile.account_type in (AccountType.SALARY_EMPLOYEE, AccountType.PENSIONER,
                                     AccountType.STUDENT, AccountType.UNKNOWN):
            p2p_income = sum(t.amount for t in income_txs
                           if not any(kw in (t.description or '').upper()
                                     for kw in ('ЗАРПЛАТА', 'SALARY', 'КЭШБЭК', 'CASHBACK',
                                               'ПЕНСИЯ', 'ПОСОБИЕ', 'ДЕПОЗИТ')))
            monthly_salary = profile.avg_monthly_income or 1
            # P2P доход > 3x зарплаты = подозрительно
            if p2p_income > monthly_salary * 3 * 12:
                score += 25
            elif p2p_income > monthly_salary * 2 * 12:
                score += 15

        # Транзитные операции (штрафуем только если > 8 случаев)
        pass_through_count = len(result.rapid_pass_through)
        if pass_through_count > 8:
            score += min(30, (pass_through_count - 8) * 8)
        elif pass_through_count > 3:
            score += min(15, (pass_through_count - 3) * 3)

        result.risk_score = min(100, score)
        return result

    def _is_merchant_payee(self, cp: str) -> bool:
        """Получатель — мерчант или банк (легальный cash-flow для бизнеса)."""
        cp_upper = cp.upper() if cp else ""
        return any(kw in cp_upper for kw in MERCHANT_KEYWORDS)

    def _detect_pass_through(
        self,
        txs: List[Transaction],
        profile: AccountProfile,
        window_hours: int = 24,
        tolerance_pct: float = 0.05
    ) -> List[Dict]:
        """
        Обнаружение транзитных операций:
        крупное поступление → быстрый отток похожей суммы.

        Для FREELANCER / BUSINESS_OWNER: не штрафуем если получатель — мерчант/банк.
        """
        is_business_type = profile.account_type in (
            AccountType.FREELANCER,
            AccountType.BUSINESS_OWNER
        )

        sorted_txs = sorted(txs, key=lambda t: t.date)
        income_txs = [t for t in sorted_txs if t.amount > 0 and t.amount >= 200000]
        expense_txs = [t for t in sorted_txs if t.amount < 0 and abs(t.amount) >= 200000]

        alerts = []
        used_expenses = set()

        for inc in income_txs:
            window_end = inc.date + timedelta(hours=window_hours)

            for j, exp in enumerate(expense_txs):
                if j in used_expenses:
                    continue
                if exp.date < inc.date:
                    continue
                if exp.date > window_end:
                    break

                ratio = abs(exp.amount) / inc.amount
                if (1 - tolerance_pct) <= ratio <= (1 + tolerance_pct):
                    # Для бизнеса/фрилансера: пропускаем если получатель — мерчант
                    payee = exp.counterparty or exp.description or ""
                    if is_business_type and self._is_merchant_payee(payee):
                        used_expenses.add(j)
                        continue

                    used_expenses.add(j)
                    alerts.append({
                        "income_date": inc.date.isoformat(),
                        "income_amount": inc.amount,
                        "income_source": inc.counterparty or inc.description,
                        "expense_date": exp.date.isoformat(),
                        "expense_amount": abs(exp.amount),
                        "expense_dest": payee,
                        "match_ratio": round(ratio, 3),
                        "time_gap_hours": round((exp.date - inc.date).total_seconds() / 3600, 1),
                    })
                    break

        return sorted(alerts, key=lambda a: a["income_amount"], reverse=True)[:10]

    def _build_source_dest_map(self, txs: List[Transaction]) -> Dict:
        """Карта: откуда приходят деньги и куда уходят"""
        sources = defaultdict(float)
        destinations = defaultdict(float)

        for tx in txs:
            cp = tx.counterparty or tx.description
            if tx.amount > 0:
                sources[cp] += tx.amount
            else:
                destinations[cp] += abs(tx.amount)

        top_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]
        top_destinations = sorted(destinations.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "top_sources": [{"name": k, "amount": v} for k, v in top_sources],
            "top_destinations": [{"name": k, "amount": v} for k, v in top_destinations],
        }
