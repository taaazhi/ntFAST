"""
Модели данных для антифрод-движка
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


# ─────────────────────────────────────────────────────────────
#  Account Profiler models
# ─────────────────────────────────────────────────────────────

class AccountType(Enum):
    SALARY_EMPLOYEE = "salary_employee"   # Наёмный работник с регулярной зарплатой
    BUSINESS_OWNER  = "business_owner"    # Владелец бизнеса / ИП
    FREELANCER      = "freelancer"        # Фрилансер / подрядчик
    TRADER          = "trader"            # Трейдер (крипто/акции)
    PENSIONER       = "pensioner"         # Пенсионер / получатель пособия
    STUDENT         = "student"           # Студент / низкий доход
    UNKNOWN         = "unknown"           # Неопределённый тип


@dataclass
class AccountProfile:
    """Профиль аккаунта — используется всеми fraud-модулями для контекстного анализа."""
    account_type: AccountType = AccountType.UNKNOWN
    avg_monthly_income: float = 0.0
    avg_monthly_expense: float = 0.0
    income_regularity_score: float = 0.0   # 0 = хаотично, 1 = идеально регулярно
    monthly_income_cv: float = 0.0         # Коэффициент вариации месячного дохода
    unique_income_sources: int = 0
    unique_expense_destinations: int = 0
    income_source_count: int = 0
    primary_income_source: Optional[str] = None
    has_salary_flag: bool = False
    has_pension_flag: bool = False
    has_crypto_activity: bool = False
    has_business_activity: bool = False
    pass_through_ratio: float = 0.0        # Доля входящих средств, быстро уходящих обратно

    def to_dict(self) -> Dict:
        return {
            "account_type": self.account_type.value,
            "avg_monthly_income": round(self.avg_monthly_income, 2),
            "avg_monthly_expense": round(self.avg_monthly_expense, 2),
            "income_regularity_score": round(self.income_regularity_score, 3),
            "monthly_income_cv": round(self.monthly_income_cv, 3),
            "unique_income_sources": self.unique_income_sources,
            "unique_expense_destinations": self.unique_expense_destinations,
            "has_salary_flag": self.has_salary_flag,
            "has_pension_flag": self.has_pension_flag,
            "has_crypto_activity": self.has_crypto_activity,
            "has_business_activity": self.has_business_activity,
            "pass_through_ratio": round(self.pass_through_ratio, 3),
        }


# ─────────────────────────────────────────────────────────────
#  Pattern Detector models
# ─────────────────────────────────────────────────────────────

@dataclass
class FlaggedPattern:
    """Конкретная схема мошенничества, обнаруженная PatternDetector."""
    pattern_name: str = ""               # машинный ключ: "money_laundering_layering"
    display_name: str = ""               # для UI: "Подозрение на отмывание — расслоение"
    confidence: float = 0.0             # 0.0–1.0
    risk_contribution: float = 0.0      # вклад в итоговый скор (0–100)
    evidence: List[Dict] = field(default_factory=list)   # конкретные транзакции
    reason: str = ""                    # текст для следователя
    counter_evidence: str = ""          # почему может быть легально
    regulatory_reference: str = ""      # ссылка на нормативный акт РК

    def to_dict(self) -> Dict:
        return {
            "pattern_name": self.pattern_name,
            "display_name": self.display_name,
            "confidence": round(self.confidence, 3),
            "risk_contribution": round(self.risk_contribution, 2),
            "evidence": self.evidence,
            "reason": self.reason,
            "counter_evidence": self.counter_evidence,
            "regulatory_reference": self.regulatory_reference,
        }


# ─────────────────────────────────────────────────────────────
#  Explainability model
# ─────────────────────────────────────────────────────────────

@dataclass
class ExplainedFlag:
    """Структурированный флаг с доказательствами и контраргументами."""
    module: str = ""                     # Модуль-источник
    severity: str = "warning"           # "info" | "warning" | "critical"
    reason: str = ""                    # Понятное объяснение для аналитика
    evidence: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    counter_evidence: str = ""
    score_contribution: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "module": self.module,
            "severity": self.severity,
            "reason": self.reason,
            "evidence": self.evidence[:5],   # Максимум 5 примеров
            "confidence": round(self.confidence, 3),
            "counter_evidence": self.counter_evidence,
            "score_contribution": round(self.score_contribution, 2),
        }




@dataclass
class VelocityResult:
    burst_alerts: List[Dict] = field(default_factory=list)        # Rapid-fire transactions
    daily_spikes: List[Dict] = field(default_factory=list)        # Days with abnormal activity
    amount_acceleration: List[Dict] = field(default_factory=list)  # Large outflows
    counterparty_churn: Dict = field(default_factory=dict)         # New counterparties rate
    risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "burst_alerts": self.burst_alerts,
            "daily_spikes": self.daily_spikes,
            "amount_acceleration": self.amount_acceleration,
            "counterparty_churn": self.counterparty_churn,
            "risk_score": self.risk_score,
        }


@dataclass
class GraphResult:
    node_count: int = 0
    edge_count: int = 0
    cycles: List[Dict] = field(default_factory=list)
    communities: List[Dict] = field(default_factory=list)
    centrality: Dict[str, float] = field(default_factory=dict)
    hub_nodes: List[Dict] = field(default_factory=list)
    risk_score: float = 0.0
    nodes: List[Dict] = field(default_factory=list)
    edges: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "cycles": self.cycles,
            "communities": self.communities,
            "centrality": self.centrality,
            "hub_nodes": self.hub_nodes,
            "risk_score": self.risk_score,
            "nodes": self.nodes,
            "edges": self.edges,
        }


@dataclass
class BehavioralResult:
    baseline_deviation_score: float = 0.0
    unusual_hours: List[Dict] = field(default_factory=list)
    spending_trend: str = "stable"          # stable, increasing, decreasing, volatile
    category_anomalies: List[Dict] = field(default_factory=list)
    weekday_pattern: Dict[str, float] = field(default_factory=dict)
    risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "baseline_deviation_score": self.baseline_deviation_score,
            "unusual_hours": self.unusual_hours,
            "spending_trend": self.spending_trend,
            "category_anomalies": self.category_anomalies,
            "weekday_pattern": self.weekday_pattern,
            "risk_score": self.risk_score,
        }


@dataclass
class StructuringResult:
    just_under_threshold: List[Dict] = field(default_factory=list)
    split_groups: List[Dict] = field(default_factory=list)
    smurfing_patterns: List[Dict] = field(default_factory=list)
    risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "just_under_threshold": self.just_under_threshold,
            "split_groups": self.split_groups,
            "smurfing_patterns": self.smurfing_patterns,
            "risk_score": self.risk_score,
        }


@dataclass
class CrossReferenceResult:
    income_expense_ratio: float = 0.0
    unexplained_inflows: List[Dict] = field(default_factory=list)
    rapid_pass_through: List[Dict] = field(default_factory=list)
    source_destination_map: Dict = field(default_factory=dict)
    risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "income_expense_ratio": self.income_expense_ratio,
            "unexplained_inflows": self.unexplained_inflows,
            "rapid_pass_through": self.rapid_pass_through,
            "source_destination_map": self.source_destination_map,
            "risk_score": self.risk_score,
        }


@dataclass
class MerchantRiskResult:
    high_risk_merchants: List[Dict] = field(default_factory=list)
    medium_risk_merchants: List[Dict] = field(default_factory=list)
    # Подставные («шелл») компании: юрлица с обезличенными названиями вроде
    # "ТОО Global Invest Consulting". MerchantRiskScorer заполнял это поле,
    # но в датаклассе его не было — Python молча создавал атрибут на лету,
    # поэтому детект влиял на risk_score, но не попадал ни в to_dict(), ни в
    # БД, ни в UI. Аналитик видел балл без объяснения, откуда он взялся.
    shell_companies: List[Dict] = field(default_factory=list)
    total_high_risk_amount: float = 0.0
    total_high_risk_pct: float = 0.0
    risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "high_risk_merchants": self.high_risk_merchants,
            "medium_risk_merchants": self.medium_risk_merchants,
            "shell_companies": self.shell_companies,
            "total_high_risk_amount": self.total_high_risk_amount,
            "total_high_risk_pct": self.total_high_risk_pct,
            "risk_score": self.risk_score,
        }


# ─────────────────────────────────────────────────────────────
#  Новые модули v4: Night / Duplicate / Round / ProfileMismatch
# ─────────────────────────────────────────────────────────────

@dataclass
class NightTransactionResult:
    """Результат детектора ночных транзакций"""
    night_count: int = 0
    night_total_amount: float = 0.0
    night_ratio: float = 0.0
    large_night_transfers: List[Dict] = field(default_factory=list)
    night_clusters: List[Dict] = field(default_factory=list)
    risk_score: float = 0.0
    no_time_data: bool = False  # True если в выписке нет данных о времени

    def to_dict(self) -> Dict:
        return {
            "night_count": self.night_count,
            "night_total_amount": round(self.night_total_amount, 2),
            "night_ratio": round(self.night_ratio, 3),
            "large_night_transfers": self.large_night_transfers[:10],
            "night_clusters": self.night_clusters[:5],
            "risk_score": self.risk_score,
            "no_time_data": self.no_time_data,
        }


@dataclass
class DuplicatePaymentResult:
    """Результат детектора дублирующих платежей"""
    duplicate_groups: List[Dict] = field(default_factory=list)
    same_amount_diff_recipient: List[Dict] = field(default_factory=list)
    total_duplicates: int = 0
    total_duplicate_amount: float = 0.0
    risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "duplicate_groups": self.duplicate_groups[:10],
            "same_amount_diff_recipient": self.same_amount_diff_recipient[:10],
            "total_duplicates": self.total_duplicates,
            "total_duplicate_amount": round(self.total_duplicate_amount, 2),
            "risk_score": self.risk_score,
        }


@dataclass
class RoundAmountResult:
    """Результат детектора круглых сумм"""
    round_count: int = 0
    round_ratio: float = 0.0
    round_total_amount: float = 0.0
    amount_distribution: Dict[str, int] = field(default_factory=dict)
    consecutive_round: List[Dict] = field(default_factory=list)
    round_transactions: List[Dict] = field(default_factory=list)
    risk_score: float = 0.0

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


@dataclass
class ProfileMismatchResult:
    """Результат детектора несоответствия профилю"""
    mismatches: List[Dict] = field(default_factory=list)
    oversized_transactions: List[Dict] = field(default_factory=list)
    unexpected_activity: List[Dict] = field(default_factory=list)
    income_anomalies: List[Dict] = field(default_factory=list)
    risk_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "mismatches": self.mismatches[:15],
            "oversized_transactions": self.oversized_transactions[:10],
            "unexpected_activity": self.unexpected_activity[:10],
            "income_anomalies": self.income_anomalies[:10],
            "risk_score": self.risk_score,
        }


@dataclass
class FraudReport:
    """Полный отчёт антифрод-анализа"""
    composite_score: float = 0.0
    risk_level: str = "low"                # low, medium, high, critical
    velocity: VelocityResult = field(default_factory=VelocityResult)
    graph: GraphResult = field(default_factory=GraphResult)
    behavioral: BehavioralResult = field(default_factory=BehavioralResult)
    structuring: StructuringResult = field(default_factory=StructuringResult)
    cross_reference: CrossReferenceResult = field(default_factory=CrossReferenceResult)
    merchant_risk: MerchantRiskResult = field(default_factory=MerchantRiskResult)
    # ─── Новые модули v4 ───────────────────────────────────────
    night_transactions: NightTransactionResult = field(default_factory=NightTransactionResult)
    duplicate_payments: DuplicatePaymentResult = field(default_factory=DuplicatePaymentResult)
    round_amounts: RoundAmountResult = field(default_factory=RoundAmountResult)
    profile_mismatch: ProfileMismatchResult = field(default_factory=ProfileMismatchResult)
    red_flags: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    # ─── Новые поля v2 ───────────────────────────────────────
    account_profile: Optional[AccountProfile] = None
    flagged_patterns: List[FlaggedPattern] = field(default_factory=list)
    explained_flags: List[ExplainedFlag] = field(default_factory=list)
    applied_weights: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        result = {
            "composite_score": self.composite_score,
            "risk_level": self.risk_level,
            "velocity": self.velocity.to_dict(),
            "graph": self.graph.to_dict(),
            "behavioral": self.behavioral.to_dict(),
            "structuring": self.structuring.to_dict(),
            "cross_reference": self.cross_reference.to_dict(),
            "merchant_risk": self.merchant_risk.to_dict(),
            "night_transactions": self.night_transactions.to_dict(),
            "duplicate_payments": self.duplicate_payments.to_dict(),
            "round_amounts": self.round_amounts.to_dict(),
            "profile_mismatch": self.profile_mismatch.to_dict(),
            "red_flags": self.red_flags,
            "recommendations": self.recommendations,
        }
        # v2 поля (опциональные, для обратной совместимости)
        if self.account_profile is not None:
            result["account_profile"] = self.account_profile.to_dict()
        if self.flagged_patterns:
            result["flagged_patterns"] = [p.to_dict() for p in self.flagged_patterns]
        if self.explained_flags:
            result["explained_flags"] = [f.to_dict() for f in self.explained_flags]
        if self.applied_weights:
            result["applied_weights"] = self.applied_weights
        return result
