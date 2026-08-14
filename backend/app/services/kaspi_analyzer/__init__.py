"""Категоризация и финансовая аналитика.

Несмотря на историческое имя пакета, к парсингу Kaspi он отношения не имеет:
парсеры живут в `bank_analyzer/parsers/`. Здесь остались две вещи, которыми
пользуется общий конвейер анализа — присвоение категорий транзакциям и расчёт
финансовых показателей.

Удалённые отсюда `parser.py` и `analyzer.py` были дубликатом
`bank_analyzer/parsers/kaspi.py` и точкой входа мёртвого API.
"""
from .categorizer import TransactionCategorizer
from .analytics import FinancialAnalytics

__all__ = [
    "TransactionCategorizer",
    "FinancialAnalytics",
]
