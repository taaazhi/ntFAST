"""Сборка рабочего контекста агента из сохранённого анализа.

Инструменты агента ожидают объекты с теми же атрибутами, что у
`bank_analyzer.base_parser.Transaction`, а в базе лежит своя модель с
другими именами полей. Этот модуль их сводит — и заодно строит
анонимизатор, без которого контекст создавать нельзя.

Анонимизатор здесь не опция и не украшение: агент отдаёт свои ответы в
языковую модель, и если имена не замаскировать на этом шаге, они уйдут
наружу при первом же вызове инструмента.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional, Sequence

from .tools import ToolContext

logger = logging.getLogger(__name__)


@dataclass
class AgentTransaction:
    """Транзакция в том виде, в каком её читают инструменты.

    Плоская структура вместо ORM-объекта: инструменты не должны тянуть за
    собой сессию базы и ленивую загрузку связей.
    """

    date: Optional[datetime]
    amount: float
    counterparty: str = ""
    description: str = ""
    counterparty_type: Any = None
    merchant_name: str = ""
    is_salary: bool = False
    is_cash_operation: bool = False


class _Kind:
    """Тип контрагента с полем `value` — как у enum, который ждут инструменты."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value or "unknown"


def from_db_transactions(
    rows: Sequence[Any],
    owner_name: Optional[str] = None,
    fraud_report: Optional[dict] = None,
    corpus_dir: Optional[str] = None,
) -> ToolContext:
    """Построить контекст из строк таблицы `transactions`."""
    from app.services.privacy.anonymizer import Anonymizer

    transactions: List[AgentTransaction] = []
    for row in rows:
        transactions.append(AgentTransaction(
            date=getattr(row, "transaction_date", None),
            amount=float(getattr(row, "amount", 0) or 0),
            counterparty=str(getattr(row, "counterparty_name", "") or ""),
            description=str(getattr(row, "description", "") or ""),
            counterparty_type=_Kind(str(getattr(row, "counterparty_type", "") or "unknown")),
            merchant_name=str(getattr(row, "merchant_name", "") or ""),
            is_salary=bool(getattr(row, "is_salary", False)),
            is_cash_operation=bool(getattr(row, "is_cash_operation", False)),
        ))

    anonymizer = Anonymizer(owner_name=owner_name)
    # Первый проход по всем именам сразу: метка должна быть одна и та же,
    # в каком бы инструменте имя ни встретилось.
    anonymizer.register([t.counterparty or t.description for t in transactions])

    return ToolContext(
        transactions=transactions,
        fraud_report=fraud_report,
        anonymizer=anonymizer,
        corpus_dir=corpus_dir,
    )


def from_analysis(analysis: Any, rows: Sequence[Any], corpus_dir: Optional[str] = None) -> ToolContext:
    """Контекст по записи анализа и её транзакциям."""
    return from_db_transactions(
        rows,
        owner_name=getattr(analysis, "account_owner", None),
        fraud_report=getattr(analysis, "fraud_report", None),
        corpus_dir=corpus_dir,
    )
