"""
FraudEngine v4 — оркестратор всех модулей антифрод-анализа
Запускает AccountProfiler → Whitelist → 11 модулей → PatternDetector
Вычисляет контекстно-взвешенный composite score (чисто rule-based)
"""
import logging
from typing import List, Dict, Optional
from ..bank_analyzer.base_parser import Transaction, AccountInfo
from .models import FraudReport, AccountProfile, AccountType, ExplainedFlag
from .account_profiler import AccountProfiler
from .whitelist import PatternWhitelist
from .pattern_detector import PatternDetector
from .velocity import VelocityAnalyzer
from .graph_analysis import TransactionGraphAnalyzer
from .behavioral import BehavioralProfiler
from .structuring import StructuringDetector
from .cross_reference import CrossReferenceAnalyzer
from .merchant_risk import MerchantRiskScorer
from .night_transactions import NightTransactionDetector
from .duplicate_detector import DuplicatePaymentDetector
from .round_amounts import RoundAmountDetector
from .profile_mismatch import ProfileMismatchDetector

logger = logging.getLogger(__name__)


# ── Базовые веса (до применения множителей) ──────────────────────
# v4: Behavioral отключен (бесполезен для реальных банковских выписок)
# Новые модули: night_transactions, duplicate_payments, round_amounts, profile_mismatch
BASE_WEIGHTS = {
    "velocity":           0.15,   # Быстрые серии транзакций
    "graph":              0.12,   # Графовый анализ (циклы, хабы)
    "behavioral":         0.00,   # ОТКЛЮЧЕН — нужна история (>6 месяцев)
    "structuring":        0.18,   # Дробление под порогом 1M KZT
    "cross_reference":    0.08,   # Сопоставление доходов/расходов
    "merchant_risk":      0.15,   # Высокорисковые мерчанты
    "pattern_detector":   0.12,   # Детектор конкретных схем
    "night_transactions": 0.05,   # Ночные транзакции (23:00-06:00)
    "duplicate_payments": 0.03,   # Дублирующие платежи (снижен — много false positives)
    "round_amounts":      0.03,   # Подозрительные круглые суммы (снижен)
    "profile_mismatch":   0.09,   # Несоответствие профилю аккаунта
}

# ── Множители по типу аккаунта (1.0 = без изменений) ─────────────
# Снижаем вес модулей, которые дают много ложных срабатываний для данного типа
WEIGHT_MULTIPLIERS = {
    AccountType.BUSINESS_OWNER: {
        "velocity": 0.5, "graph": 0.3,
        "behavioral": 0.0, "structuring": 0.8,
        "cross_reference": 0.4, "merchant_risk": 0.8,
        "pattern_detector": 1.0,
        "night_transactions": 0.3,    # бизнес часто работает ночью
        "duplicate_payments": 0.8,    # дубли важны для бизнеса
        "round_amounts": 0.4,        # бизнес часто платит круглыми суммами
        "profile_mismatch": 0.5,     # у бизнеса гибкий профиль
    },
    AccountType.TRADER: {
        "velocity": 0.5, "graph": 0.7,
        "behavioral": 0.0, "structuring": 0.7,
        "cross_reference": 0.6, "merchant_risk": 0.2,
        "pattern_detector": 1.0,
        "night_transactions": 0.2,    # трейдеры торгуют 24/7
        "duplicate_payments": 0.6,    # повторные сделки нормальны
        "round_amounts": 0.3,        # круглые суммы в крипте нормальны
        "profile_mismatch": 0.4,     # крипто-активность ожидаема
    },
    AccountType.FREELANCER: {
        "velocity": 0.7, "graph": 0.8,
        "behavioral": 0.0, "structuring": 0.9,
        "cross_reference": 0.6, "merchant_risk": 0.9,
        "pattern_detector": 1.0,
        "night_transactions": 0.6,    # фрилансеры работают нерегулярно
        "duplicate_payments": 0.9,
        "round_amounts": 0.7,
        "profile_mismatch": 0.7,
    },
    AccountType.SALARY_EMPLOYEE: {
        "velocity": 1.0, "graph": 1.0,
        "behavioral": 0.0, "structuring": 1.0,
        "cross_reference": 1.0, "merchant_risk": 1.0,
        "pattern_detector": 1.0,
        "night_transactions": 1.0,    # ночные переводы подозрительны
        "duplicate_payments": 1.0,
        "round_amounts": 1.0,
        "profile_mismatch": 1.0,     # отклонения от профиля заметны
    },
    AccountType.PENSIONER: {
        "velocity": 1.0, "graph": 1.0,
        "behavioral": 0.0, "structuring": 1.0,
        "cross_reference": 1.0, "merchant_risk": 1.0,
        "pattern_detector": 1.0,
        "night_transactions": 1.2,    # ночные переводы у пенсионеров ОЧЕНЬ подозрительны
        "duplicate_payments": 1.0,
        "round_amounts": 1.0,
        "profile_mismatch": 1.2,     # для пенсионера любое отклонение подозрительно
    },
    AccountType.STUDENT: {
        "velocity": 0.9, "graph": 0.9,
        "behavioral": 0.0, "structuring": 0.9,
        "cross_reference": 0.9, "merchant_risk": 0.9,
        "pattern_detector": 1.0,
        "night_transactions": 0.5,    # студенты живут ночью
        "duplicate_payments": 0.9,
        "round_amounts": 0.8,
        "profile_mismatch": 1.0,
    },
    AccountType.UNKNOWN: {
        "velocity": 1.0, "graph": 1.0,
        "behavioral": 0.0, "structuring": 1.0,
        "cross_reference": 1.0, "merchant_risk": 1.0,
        "pattern_detector": 1.0,
        "night_transactions": 1.0,
        "duplicate_payments": 1.0,
        "round_amounts": 1.0,
        "profile_mismatch": 1.0,
    },
}


class FraudEngine:
    """
    Главный движок антифрод-анализа v4
    Порядок: AccountProfiler → Whitelist → 11 модулей + PatternDetector → Composite Score
    v4: Behavioral отключен, добавлены Night/Duplicate/Round/ProfileMismatch
    """

    def __init__(self):
        self.profiler = AccountProfiler()
        self.whitelist = PatternWhitelist()
        self.pattern_detector = PatternDetector()
        # Оригинальные модули (Behavioral отключен через веса)
        self.velocity = VelocityAnalyzer()
        self.graph = TransactionGraphAnalyzer()
        self.behavioral = BehavioralProfiler()
        self.structuring = StructuringDetector()
        self.cross_reference = CrossReferenceAnalyzer()
        self.merchant_risk = MerchantRiskScorer()
        # Новые модули v4
        self.night_detector = NightTransactionDetector()
        self.duplicate_detector = DuplicatePaymentDetector()
        self.round_detector = RoundAmountDetector()
        self.profile_mismatch_detector = ProfileMismatchDetector()

    def full_analysis(
        self,
        transactions: List[Transaction],
        account_info: AccountInfo
    ) -> FraudReport:
        """Запустить полный антифрод-анализ v4"""
        report = FraudReport()

        if not transactions:
            return report

        logger.info(f"Starting fraud analysis v4 on {len(transactions)} transactions")

        # ── Фаза 1: Профилирование аккаунта ──────────────────────
        try:
            profile = self.profiler.profile(transactions)
            report.account_profile = profile
            logger.info(
                f"Account profile: type={profile.account_type.value}, "
                f"avg_income={profile.avg_monthly_income:.0f}, "
                f"regularity={profile.income_regularity_score:.2f}"
            )
        except Exception as e:
            logger.error(f"Account profiling failed: {e}")
            profile = AccountProfile()

        # ── Фаза 2: Whitelist (исключить легальные транзакции) ────
        try:
            whitelisted_ids = self.whitelist.build_whitelisted_tx_ids(transactions, profile)
            filtered_txs = [t for i, t in enumerate(transactions) if i not in whitelisted_ids]
            logger.info(
                f"Whitelist: {len(whitelisted_ids)} transactions excluded, "
                f"{len(filtered_txs)} remaining for analysis"
            )
        except Exception as e:
            logger.error(f"Whitelist failed: {e}")
            filtered_txs = transactions

        amounts = [t.amount for t in filtered_txs]

        # ── Фаза 3: Запуск 7 аналитических модулей ───────────────

        # 2. Velocity checks
        try:
            report.velocity = self.velocity.analyze(filtered_txs, profile)
            logger.info(f"Velocity: score={report.velocity.risk_score}")
        except Exception as e:
            logger.error(f"Velocity analysis failed: {e}")

        # 3. Графовый анализ
        try:
            report.graph = self.graph.build_and_analyze(filtered_txs, account_info, profile)
            logger.info(
                f"Graph: nodes={report.graph.node_count}, "
                f"cycles={len(report.graph.cycles)}, score={report.graph.risk_score}"
            )
        except Exception as e:
            logger.error(f"Graph analysis failed: {e}")

        # 4. Поведенческий анализ
        try:
            report.behavioral = self.behavioral.analyze(filtered_txs, profile)
            logger.info(f"Behavioral: trend={report.behavioral.spending_trend}, score={report.behavioral.risk_score}")
        except Exception as e:
            logger.error(f"Behavioral analysis failed: {e}")

        # 5. Структурирование
        try:
            report.structuring = self.structuring.analyze(filtered_txs, profile)
            logger.info(f"Structuring: score={report.structuring.risk_score}")
        except Exception as e:
            logger.error(f"Structuring analysis failed: {e}")

        # 6. Cross-reference
        try:
            report.cross_reference = self.cross_reference.analyze(filtered_txs, profile)
            logger.info(
                f"CrossRef: ratio={report.cross_reference.income_expense_ratio}, "
                f"score={report.cross_reference.risk_score}"
            )
        except Exception as e:
            logger.error(f"Cross-reference analysis failed: {e}")

        # 7. Merchant risk
        try:
            report.merchant_risk = self.merchant_risk.analyze(filtered_txs, profile)
            logger.info(
                f"Merchant: high_risk={report.merchant_risk.total_high_risk_pct}%, "
                f"score={report.merchant_risk.risk_score}"
            )
        except Exception as e:
            logger.error(f"Merchant risk analysis failed: {e}")

        # ── Фаза 3.5: Новые модули v4 ─────────────────────────────

        # 8. Ночные транзакции
        try:
            night_result = self.night_detector.analyze(filtered_txs, profile)
            # Конвертируем результат из класса модуля в dataclass models.py
            report.night_transactions.night_count = night_result.night_count
            report.night_transactions.night_total_amount = night_result.night_total_amount
            report.night_transactions.night_ratio = night_result.night_ratio
            report.night_transactions.large_night_transfers = night_result.large_night_transfers
            report.night_transactions.night_clusters = night_result.night_clusters
            report.night_transactions.risk_score = night_result.risk_score
            report.night_transactions.no_time_data = night_result.no_time_data
            logger.info(
                f"NightTx: {night_result.night_count} night txs, "
                f"score={night_result.risk_score}, "
                f"no_time_data={night_result.no_time_data}"
            )
        except Exception as e:
            logger.error(f"Night transaction analysis failed: {e}")

        # 9. Дублирующие платежи
        try:
            dup_result = self.duplicate_detector.analyze(filtered_txs, profile)
            report.duplicate_payments.duplicate_groups = dup_result.duplicate_groups
            report.duplicate_payments.same_amount_diff_recipient = dup_result.same_amount_diff_recipient
            report.duplicate_payments.total_duplicates = dup_result.total_duplicates
            report.duplicate_payments.total_duplicate_amount = dup_result.total_duplicate_amount
            report.duplicate_payments.risk_score = dup_result.risk_score
            logger.info(
                f"Duplicates: {dup_result.total_duplicates} dups, "
                f"score={dup_result.risk_score}"
            )
        except Exception as e:
            logger.error(f"Duplicate payment analysis failed: {e}")

        # 10. Круглые суммы
        try:
            round_result = self.round_detector.analyze(filtered_txs, profile)
            report.round_amounts.round_count = round_result.round_count
            report.round_amounts.round_ratio = round_result.round_ratio
            report.round_amounts.round_total_amount = round_result.round_total_amount
            report.round_amounts.amount_distribution = round_result.amount_distribution
            report.round_amounts.consecutive_round = round_result.consecutive_round
            report.round_amounts.round_transactions = round_result.round_transactions
            report.round_amounts.risk_score = round_result.risk_score
            logger.info(
                f"RoundAmounts: {round_result.round_count} round, "
                f"ratio={round_result.round_ratio:.1%}, "
                f"score={round_result.risk_score}"
            )
        except Exception as e:
            logger.error(f"Round amount analysis failed: {e}")

        # 11. Несоответствие профилю
        try:
            pm_result = self.profile_mismatch_detector.analyze(filtered_txs, profile)
            report.profile_mismatch.mismatches = pm_result.mismatches
            report.profile_mismatch.oversized_transactions = pm_result.oversized_transactions
            report.profile_mismatch.unexpected_activity = pm_result.unexpected_activity
            report.profile_mismatch.income_anomalies = pm_result.income_anomalies
            report.profile_mismatch.risk_score = pm_result.risk_score
            logger.info(
                f"ProfileMismatch: {len(pm_result.mismatches)} mismatches, "
                f"score={pm_result.risk_score}"
            )
        except Exception as e:
            logger.error(f"Profile mismatch analysis failed: {e}")

        # ── Фаза 4: Детектор конкретных схем ─────────────────────
        try:
            # PatternDetector работает на ВСЕХ транзакциях (не фильтрованных)
            report.flagged_patterns = self.pattern_detector.detect_all(transactions, profile)
            logger.info(f"PatternDetector: {len(report.flagged_patterns)} patterns found")
        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")

        # ── Фаза 5: Контекстные веса ─────────────────────────────
        weights = self._get_contextual_weights(profile)
        report.applied_weights = {k: round(v, 4) for k, v in weights.items()}

        # ── Фаза 6: Composite score (rule-based) ─────────────────
        report.composite_score = self._calculate_composite(report, weights)
        report.risk_level = self._classify_risk(report.composite_score)
        logger.info(f"Composite score: {report.composite_score:.1f}, level={report.risk_level}")

        # ── Фаза 7: Red flags + Recommendations ──────────────────
        report.red_flags = self._generate_red_flags(report)
        report.recommendations = self._generate_recommendations(report)

        # ── Фаза 8: Explained flags (для аудита) ─────────────────
        report.explained_flags = self._build_explained_flags(report, profile)

        logger.info(
            f"Fraud analysis v4 complete: composite={report.composite_score:.1f}, "
            f"level={report.risk_level}, type={profile.account_type.value}"
        )
        return report

    def _get_contextual_weights(self, profile: AccountProfile) -> Dict[str, float]:
        """Вычислить контекстные веса модулей для данного типа аккаунта."""
        multipliers = WEIGHT_MULTIPLIERS.get(
            profile.account_type,
            WEIGHT_MULTIPLIERS[AccountType.UNKNOWN]
        )

        raw = {
            module: BASE_WEIGHTS[module] * multipliers.get(module, 1.0)
            for module in BASE_WEIGHTS
        }

        # Ре-нормализация: сумма весов = 1.0
        total = sum(raw.values())
        if total > 0:
            return {k: v / total for k, v in raw.items()}
        return {k: 1.0 / len(raw) for k in raw}

    def _calculate_composite(
        self,
        report: FraudReport,
        weights: Dict[str, float]
    ) -> float:
        """Взвешенный composite score с corroboration bonus."""

        # Оценки pattern_detector
        pattern_score = 0.0
        if report.flagged_patterns:
            pattern_score = min(100, sum(p.risk_contribution for p in report.flagged_patterns))

        module_scores = {
            "velocity": report.velocity.risk_score,
            "graph": report.graph.risk_score,
            "behavioral": report.behavioral.risk_score,
            "structuring": report.structuring.risk_score,
            "cross_reference": report.cross_reference.risk_score,
            "merchant_risk": report.merchant_risk.risk_score,
            "pattern_detector": pattern_score,
            "night_transactions": report.night_transactions.risk_score,
            "duplicate_payments": report.duplicate_payments.risk_score,
            "round_amounts": report.round_amounts.risk_score,
            "profile_mismatch": report.profile_mismatch.risk_score,
        }

        score = sum(
            module_scores.get(module, 0) * weight
            for module, weight in weights.items()
        )

        # Corroboration bonus: каждый дополнительный модуль выше 60 баллов +3
        # (повышен порог с 50→60, снижен бонус с 5→3 для уменьшения ложных срабатываний)
        high_signal_count = sum(1 for s in module_scores.values() if s >= 60)
        if high_signal_count > 1:
            bonus = (high_signal_count - 1) * 3
            score += bonus
            logger.debug(f"Corroboration bonus: +{bonus} ({high_signal_count} high-signal modules)")

        # Pattern override: если найдены мошеннические схемы,
        # поднимаем минимальный score чтобы отразить серьёзность
        if report.flagged_patterns:
            max_confidence = max(p.confidence for p in report.flagged_patterns)

            # Volume boost: много однотипных паттернов повышают уверенность
            # 10+ паттернов → +0.15, 50+ → +0.25, 100+ → +0.35
            pattern_count = len(report.flagged_patterns)
            if pattern_count >= 100:
                volume_boost = 0.35
            elif pattern_count >= 50:
                volume_boost = 0.25
            elif pattern_count >= 10:
                volume_boost = 0.15
            elif pattern_count >= 5:
                volume_boost = 0.1
            else:
                volume_boost = 0.0

            effective_confidence = min(1.0, max_confidence + volume_boost)

            if effective_confidence >= 0.7:
                # Минимальный score = confidence * 70 (уверенность 0.95 → минимум 66.5)
                min_score_from_pattern = effective_confidence * 70
                if score < min_score_from_pattern:
                    score = min_score_from_pattern
                    logger.debug(
                        f"Pattern override: score raised to {score:.1f} "
                        f"(max_confidence={max_confidence:.2f}, "
                        f"volume_boost=+{volume_boost:.2f}, "
                        f"pattern_count={pattern_count})"
                    )

        return float(round(min(100.0, float(score)), 1))

    def _classify_risk(self, score: float) -> str:
        if score >= 75:
            return "critical"
        elif score >= 55:
            return "high"
        elif score >= 30:
            return "medium"
        return "low"

    def _generate_red_flags(self, report: FraudReport) -> List[str]:
        flags = []

        if report.velocity.burst_alerts:
            flags.append(
                f"Обнаружены серии быстрых транзакций "
                f"({len(report.velocity.burst_alerts)} случаев)"
            )

        if report.velocity.daily_spikes:
            flags.append(f"Дни с аномальной активностью: {len(report.velocity.daily_spikes)}")

        if report.graph.cycles:
            flags.append(f"Круговые переводы обнаружены: {len(report.graph.cycles)} циклов")

        if report.structuring.just_under_threshold:
            flags.append(
                f"Суммы близкие к порогу отчётности: "
                f"{len(report.structuring.just_under_threshold)}"
            )

        if report.structuring.split_groups:
            flags.append(f"Возможное дробление операций: {len(report.structuring.split_groups)} групп")

        if report.cross_reference.rapid_pass_through:
            flags.append(
                f"Транзитные операции: {len(report.cross_reference.rapid_pass_through)}"
            )

        if report.merchant_risk.high_risk_merchants:
            names = ", ".join(m["name"] for m in report.merchant_risk.high_risk_merchants[:3])
            flags.append(f"Высокорисковые мерчанты: {names}")

        if report.merchant_risk.total_high_risk_pct > 10:
            flags.append(
                f"{report.merchant_risk.total_high_risk_pct:.1f}% расходов — "
                f"высокорисковые операции"
            )

        if report.behavioral.spending_trend == "volatile":
            flags.append("Нестабильный паттерн расходов")

        # ── Флаги новых модулей v4 ──

        # Ночные транзакции
        nt = report.night_transactions
        if nt.large_night_transfers:
            flags.append(
                f"Крупные ночные переводы (23:00-06:00): "
                f"{len(nt.large_night_transfers)} операций"
            )
        if nt.night_clusters:
            flags.append(
                f"Серии ночных транзакций: {len(nt.night_clusters)} кластеров"
            )

        # Дублирующие платежи
        dp = report.duplicate_payments
        if dp.total_duplicates > 0:
            flags.append(
                f"Дублирующие платежи: {dp.total_duplicates} повторов "
                f"на сумму {dp.total_duplicate_amount:,.0f} KZT"
            )
        if dp.same_amount_diff_recipient:
            flags.append(
                f"Веерная отправка одинаковых сумм: "
                f"{len(dp.same_amount_diff_recipient)} паттернов"
            )

        # Круглые суммы
        ra = report.round_amounts
        if ra.round_ratio > 0.3:
            flags.append(
                f"Высокая доля круглых сумм: {ra.round_ratio:.0%} "
                f"({ra.round_count} транзакций)"
            )
        if ra.consecutive_round:
            flags.append(
                f"Серии круглых сумм подряд: {len(ra.consecutive_round)} серий"
            )

        # Несоответствие профилю
        pm = report.profile_mismatch
        if pm.oversized_transactions:
            flags.append(
                f"Транзакции превышающие норму для профиля: "
                f"{len(pm.oversized_transactions)} операций"
            )
        if pm.unexpected_activity:
            flags.append(
                f"Нехарактерная активность для типа аккаунта: "
                f"{len(pm.unexpected_activity)} случаев"
            )
        if pm.income_anomalies:
            flags.append(
                f"Аномальные поступления: {len(pm.income_anomalies)} операций"
            )

        # Флаги от PatternDetector
        for pattern in report.flagged_patterns:
            if pattern.confidence >= 0.5:
                flags.append(f"[{pattern.display_name}] {pattern.reason}")

        return flags

    def _generate_recommendations(self, report: FraudReport) -> List[str]:
        recs = []

        if report.risk_level in ["high", "critical"]:
            recs.append("Рекомендуется углублённая проверка (Enhanced Due Diligence)")

        if report.graph.cycles:
            recs.append("Проверить круговые переводы на предмет отмывания средств")

        if report.merchant_risk.high_risk_merchants:
            gambling = [
                m for m in report.merchant_risk.high_risk_merchants
                if m["category"] == "gambling"
            ]
            if gambling:
                recs.append("Проверить источники средств для игорной деятельности")

        if report.structuring.split_groups:
            recs.append("Проверить дробление операций на предмет обхода порогов")

        if report.cross_reference.rapid_pass_through:
            recs.append("Проверить транзитные операции — возможная схема отмывания")

        # Рекомендации от новых модулей v4
        if report.night_transactions.risk_score >= 30:
            recs.append("Проверить ночные переводы — возможен несанкционированный доступ")

        if report.duplicate_payments.total_duplicates >= 3:
            recs.append("Проверить повторные платежи — возможное дублирование или обнал")

        if report.duplicate_payments.same_amount_diff_recipient:
            recs.append("Проверить веерные переводы — признак массового вывода средств")

        if report.round_amounts.risk_score >= 30:
            recs.append("Обратить внимание на круглые суммы переводов — возможно обналичивание")

        if report.profile_mismatch.oversized_transactions:
            recs.append("Проверить крупные операции, не соответствующие профилю клиента")

        if report.profile_mismatch.unexpected_activity:
            recs.append("Запросить пояснения по нехарактерной активности аккаунта")

        # Рекомендации от PatternDetector
        for pattern in report.flagged_patterns:
            if pattern.confidence >= 0.7 and pattern.regulatory_reference:
                recs.append(
                    f"Сообщить в ПОД/ФТ согласно {pattern.regulatory_reference} "
                    f"(схема: {pattern.display_name})"
                )

        if not recs:
            recs.append("Признаков значимых нарушений не обнаружено")

        return recs

    def _build_explained_flags(
        self,
        report: FraudReport,
        profile: AccountProfile
    ) -> List[ExplainedFlag]:
        """Формирует структурированные ExplainedFlag для аудита."""
        explained = []

        module_data = [
            ("velocity", report.velocity.risk_score,
             f"Burst транзакций: {len(report.velocity.burst_alerts)}" if report.velocity.burst_alerts else "",
             "critical" if report.velocity.risk_score >= 60 else "warning"),
            ("structuring", report.structuring.risk_score,
             f"Дробление: {len(report.structuring.split_groups)} групп" if report.structuring.split_groups else "",
             "critical" if report.structuring.risk_score >= 60 else "warning"),
            ("merchant_risk", report.merchant_risk.risk_score,
             f"Высокорисковых мерчантов: {len(report.merchant_risk.high_risk_merchants)}" if report.merchant_risk.high_risk_merchants else "",
             "warning"),
            ("cross_reference", report.cross_reference.risk_score,
             f"Транзитных: {len(report.cross_reference.rapid_pass_through)}" if report.cross_reference.rapid_pass_through else "",
             "warning"),
            ("graph", report.graph.risk_score,
             f"Циклов: {len(report.graph.cycles)}" if report.graph.cycles else "",
             "warning"),
            # Новые модули v4
            ("night_transactions", report.night_transactions.risk_score,
             f"Ночных транзакций: {report.night_transactions.night_count}, "
             f"крупных: {len(report.night_transactions.large_night_transfers)}"
             if report.night_transactions.night_count > 0 else "",
             "critical" if report.night_transactions.risk_score >= 50 else "warning"),
            ("duplicate_payments", report.duplicate_payments.risk_score,
             f"Дублей: {report.duplicate_payments.total_duplicates}, "
             f"сумма: {report.duplicate_payments.total_duplicate_amount:,.0f} KZT"
             if report.duplicate_payments.total_duplicates > 0 else "",
             "warning"),
            ("round_amounts", report.round_amounts.risk_score,
             f"Круглых: {report.round_amounts.round_count} "
             f"({report.round_amounts.round_ratio:.0%})"
             if report.round_amounts.round_count > 0 else "",
             "warning"),
            ("profile_mismatch", report.profile_mismatch.risk_score,
             f"Несоответствий профилю: {len(report.profile_mismatch.mismatches)}"
             if report.profile_mismatch.mismatches else "",
             "critical" if report.profile_mismatch.risk_score >= 50 else "warning"),
        ]

        for module, score, reason, severity in module_data:
            if score > 0 and reason:
                counter_ev = self._get_counter_evidence(module, profile)
                explained.append(ExplainedFlag(
                    module=module,
                    severity=severity,
                    reason=reason,
                    confidence=min(1.0, score / 100),
                    counter_evidence=counter_ev,
                    score_contribution=round(
                        score * report.applied_weights.get(module, 0), 2
                    ),
                ))

        # ExplainedFlag от PatternDetector
        for pattern in report.flagged_patterns:
            explained.append(ExplainedFlag(
                module="pattern_detector",
                severity="critical" if pattern.confidence >= 0.8 else "warning",
                reason=pattern.reason,
                evidence=pattern.evidence[:5],
                confidence=pattern.confidence,
                counter_evidence=pattern.counter_evidence,
                score_contribution=round(pattern.risk_contribution, 2),
            ))

        return explained

    def _get_counter_evidence(self, module: str, profile: AccountProfile) -> str:
        """Контраргумент к сигналу модуля на основе типа аккаунта."""
        atype = profile.account_type

        counter_map = {
            ("velocity", AccountType.BUSINESS_OWNER):
                "Высокая скорость транзакций норма для бизнеса",
            ("velocity", AccountType.TRADER):
                "Трейдеры совершают множество операций в день",
            ("merchant_risk", AccountType.TRADER):
                "Крипто-операции являются основным видом деятельности трейдера",
            ("cross_reference", AccountType.FREELANCER):
                "Фрилансеры перечисляют полученные средства субподрядчикам",
            ("cross_reference", AccountType.BUSINESS_OWNER):
                "Перечисление поставщикам — стандартный бизнес cash-flow",
            ("graph", AccountType.BUSINESS_OWNER):
                "Бизнес по определению имеет много контрагентов",
            ("behavioral", AccountType.FREELANCER):
                "Нерегулярный доход — характеристика фриланса",
            # Контраргументы для новых модулей v4
            ("night_transactions", AccountType.BUSINESS_OWNER):
                "Бизнес часто проводит платежи в нерабочее время (автоматические списания)",
            ("night_transactions", AccountType.TRADER):
                "Трейдеры торгуют 24/7, ночные операции нормальны",
            ("night_transactions", AccountType.STUDENT):
                "Студенты часто активны в ночное время",
            ("duplicate_payments", AccountType.BUSINESS_OWNER):
                "Бизнес может делать регулярные одинаковые платежи (аренда, ЗП)",
            ("duplicate_payments", AccountType.TRADER):
                "Повторные сделки одинакового объёма — стандарт для трейдинга",
            ("round_amounts", AccountType.BUSINESS_OWNER):
                "Бизнес-платежи часто бывают круглыми (аренда, закупки)",
            ("round_amounts", AccountType.TRADER):
                "Крипто-операции часто совершаются круглыми суммами",
            ("profile_mismatch", AccountType.BUSINESS_OWNER):
                "Бизнес-аккаунты имеют гибкий профиль расходов",
            ("profile_mismatch", AccountType.FREELANCER):
                "Фрилансеры могут получать нерегулярные крупные платежи от проектов",
        }

        return counter_map.get((module, atype), "")
