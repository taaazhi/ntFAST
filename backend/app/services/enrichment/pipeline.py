"""Шаг обогащения: то, что нужно детекторам, но чего нет в тексте выписки.

Ставится между разбором и антифродом. Порядок внутри важен: сначала
классификация контрагентов, потом зарплата — детектор зарплаты смотрит на
`counterparty_type`, чтобы не записать в работодатели физлицо.

Работает без языковой модели. Это не заглушка на будущее, а рабочий режим:
на бенчмарке одни только правила поднимают композитный балл незнакомого
формата с 17.4 LOW до 63.0 HIGH, то есть до уровня банк-специфичного
парсера. Модель, когда она подключена, уточняет классификацию — заменяет
рукописные словари мерчантов и стоп-листы, а не создаёт результат с нуля.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence

from .counterparty_classifier import Classification, CounterpartyClassifier, classify_by_rule
from .salary_detector import mark_salary_transactions

logger = logging.getLogger(__name__)


def _names_of(transactions: Sequence[Any]) -> List[str]:
    return [
        (getattr(t, "counterparty", None) or getattr(t, "description", None) or "")
        for t in transactions
    ]


def _classify_offline(transactions: Sequence[Any]) -> Dict[str, Classification]:
    """Классификация правилами — без сети и без ключа."""
    return {
        name.strip(): classify_by_rule(name)
        for name in _names_of(transactions)
        if name and name.strip()
    }


def _run_async(coro):
    """Выполнить корутину из синхронного кода.

    `BankAnalyzer.analyze()` синхронный и вызывается в том числе из Celery.
    Если цикл событий уже крутится (сервер FastAPI), `asyncio.run` бросит
    исключение — в этом случае обогащение через модель пропускаем и
    остаёмся на правилах, вместо того чтобы уронить анализ.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    coro.close()
    raise RuntimeError("event loop is already running")


def enrich_transactions(
    transactions: Sequence[Any],
    ai_manager: Optional[Any] = None,
    cache: Optional[Dict[str, Classification]] = None,
) -> Dict[str, Any]:
    """Обогатить транзакции на месте. Возвращает сводку для отчёта."""
    if not transactions:
        return {"classified": 0, "salary_sources": [], "classifier": None}

    classifier = CounterpartyClassifier(ai_manager=ai_manager, cache=cache)
    stats: Optional[Dict[str, Any]] = None

    if ai_manager is not None:
        try:
            mapping = _run_async(classifier.classify(_names_of(transactions)))
            stats = classifier.stats.as_dict()
        except Exception as exc:
            # Недоступная модель не должна ломать анализ — она его улучшает.
            logger.warning("Обогащение через модель не выполнено (%s), работаем по правилам", exc)
            mapping = _classify_offline(transactions)
    else:
        mapping = _classify_offline(transactions)

    classified = classifier.apply(transactions, mapping)
    salary_sources = mark_salary_transactions(transactions)

    return {
        "classified": classified,
        "salary_sources": [f.as_dict() for f in salary_sources],
        "classifier": stats,
    }
