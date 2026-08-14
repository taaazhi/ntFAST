"""Обогащение распарсенных транзакций тем, чего нет в тексте выписки."""
from .counterparty_classifier import (
    Classification,
    ClassificationStats,
    CounterpartyClassifier,
    classify_by_rule,
)
from .pipeline import enrich_transactions
from .salary_detector import SalaryFinding, find_salary_sources, mark_salary_transactions

__all__ = [
    "enrich_transactions",
    "Classification",
    "ClassificationStats",
    "CounterpartyClassifier",
    "classify_by_rule",
    "SalaryFinding",
    "find_salary_sources",
    "mark_salary_transactions",
]
