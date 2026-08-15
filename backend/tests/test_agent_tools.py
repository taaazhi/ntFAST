"""Инструменты следственного агента.

Главное, что здесь проверяется, — приватность на выходе. Анонимизация на
входе бессмысленна, если данные утекают через ответ инструмента: модель
спросит «покажи крупные расходы» и получит ФИО в открытом виде. Поэтому
маскирование проверяется на каждом инструменте, который возвращает имена.

Второе — честность ответа. Инструмент, молча вернувший первые 50 строк из
тысячи, заставит модель рассуждать о выписке, которой она не видела, и вывод
будет уверенным и неверным.
"""
from datetime import datetime

import pytest

from app.services.bank_analyzer.base_parser import (
    CounterpartyType, Transaction, TransactionType,
)
from app.services.privacy.anonymizer import Anonymizer
from app.services.agent import ToolContext, run_tool

OWNER = "Тажибаев Нурдаулет Ерланович"


def tx(amount, day=5, month=1, counterparty="Magnum", cp_type=CounterpartyType.MERCHANT,
       description="", **extra):
    return Transaction(
        date=datetime(2025, month, day),
        amount=amount,
        type=TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE,
        description=description,
        counterparty=counterparty,
        counterparty_type=cp_type,
        **extra,
    )


@pytest.fixture
def ctx():
    transactions = [
        tx(-3500, day=1, counterparty="Magnum"),
        tx(-1200, day=2, counterparty="YANDEX.GO"),
        tx(-150_000, day=3, counterparty="Ержан О.", cp_type=CounterpartyType.PERSON),
        tx(-90_000, day=4, counterparty="Аружан С.", cp_type=CounterpartyType.PERSON),
        tx(500_000, day=5, counterparty="ТОО Астана Строй", is_salary=True),
        tx(-25_000, day=6, month=2, counterparty="Банкомат", is_cash_operation=True),
    ]
    anonymizer = Anonymizer(owner_name=OWNER)
    anonymizer.register([t.counterparty for t in transactions])
    return ToolContext(transactions=transactions, anonymizer=anonymizer)


# ── Приватность на выходе ────────────────────────────────────────

@pytest.mark.parametrize("tool,params", [
    ("query_transactions", {}),
    ("summarise_counterparties", {}),
])
def test_person_names_never_reach_the_model(ctx, tool, params):
    """Анонимизация на входе не спасёт, если имя вернётся в ответе."""
    payload = str(run_tool(tool, ctx, **params))

    assert "Ержан" not in payload
    assert "Аружан" not in payload
    assert "PERSON_" in payload


def test_organisations_stay_visible(ctx):
    """Мерчанты — не персональные данные, и без них рассуждать не о чем."""
    payload = str(run_tool("summarise_counterparties", ctx, direction="expense"))

    assert "Magnum" in payload
    assert "YANDEX.GO" in payload


def test_same_person_keeps_the_same_tag(ctx):
    """Иначе модель не свяжет два упоминания одного человека."""
    first = run_tool("query_transactions", ctx, counterparty="Ержан")
    second = run_tool("summarise_counterparties", ctx, direction="expense")

    tag = first["transactions"][0]["counterparty"]
    assert any(entry["counterparty"] == tag for entry in second["top"])


# ── Честность ответа ─────────────────────────────────────────────

def test_truncation_is_reported(ctx):
    """Модель должна знать, что видит срез, а не всю выписку."""
    result = run_tool("query_transactions", ctx, limit=2)

    assert result["returned"] == 2
    assert result["found"] == 6
    assert result["truncated"] is True


def test_limit_cannot_exceed_the_cap(ctx):
    result = run_tool("query_transactions", ctx, limit=10_000)

    assert result["returned"] <= 50


def test_totals_cover_all_matches_not_just_the_returned_slice(ctx):
    """Сумма считается по всем совпадениям: иначе модель сложит три строки
    из пятидесяти и назовёт это оборотом по счёту."""
    result = run_tool("query_transactions", ctx, direction="expense", limit=1)

    assert result["found"] == 5
    assert result["total_amount"] == pytest.approx(-269_700)


# ── Фильтры ──────────────────────────────────────────────────────

def test_direction_filter(ctx):
    income = run_tool("query_transactions", ctx, direction="income")

    assert income["found"] == 1
    assert income["transactions"][0]["is_salary"] is True


def test_amount_filter_uses_absolute_value(ctx):
    """Списание на 150 000 — крупное, несмотря на минус."""
    result = run_tool("query_transactions", ctx, min_amount=100_000)

    assert result["found"] == 2


def test_date_filter_accepts_kazakh_statement_format(ctx):
    result = run_tool("query_transactions", ctx, date_from="01.02.2025")

    assert result["found"] == 1


def test_counterparty_type_filter(ctx):
    result = run_tool("query_transactions", ctx, counterparty_type="person")

    assert result["found"] == 2


def test_period_totals_split_income_and_expense(ctx):
    months = run_tool("get_period_totals", ctx)["months"]

    assert [m["month"] for m in months] == ["2025-01", "2025-02"]
    assert months[0]["income"] == pytest.approx(500_000)
    assert months[0]["expense"] == pytest.approx(244_700)


# ── Устойчивость ─────────────────────────────────────────────────

def test_unknown_tool_returns_an_error_not_a_crash(ctx):
    """Модель ошибётся именем инструмента — разбор от этого падать не должен."""
    result = run_tool("сделай_хорошо", ctx)

    assert "error" in result
    assert "query_transactions" in result["available"]


def test_failing_tool_is_reported_as_error(ctx):
    result = run_tool("query_transactions", ctx, min_amount="не число")

    assert "error" in result


def test_risk_breakdown_without_analysis(ctx):
    result = run_tool("get_risk_breakdown", ctx)

    assert result["available"] is False


def test_calls_are_journalled(ctx):
    """Вывод агента должен быть воспроизводим: видно, что он спрашивал."""
    run_tool("query_transactions", ctx, direction="income")
    run_tool("get_period_totals", ctx)

    assert [c["tool"] for c in ctx.calls] == ["query_transactions", "get_period_totals"]


def test_failed_call_is_not_journalled(ctx):
    """В журнал попадает то, что действительно отработало."""
    run_tool("несуществующий", ctx)

    assert ctx.calls == []
