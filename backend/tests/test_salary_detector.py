"""Тесты детектора зарплаты по поведению платежа.

Почему на этот модуль столько тестов. Абляция на бенчмарке показала, что
`is_salary` в одиночку переводит композитный балл из 17.4 LOW в 63.0 HIGH:
от него зависит тип счёта, а от типа счёта — контекстные веса всех
детекторов. Ошибка здесь не остаётся локальной, она меняет вывод по всему
делу, поэтому важнее проверить, чего детектор НЕ помечает.
"""
from datetime import datetime

import pytest

from app.services.bank_analyzer.base_parser import (
    CounterpartyType, Transaction, TransactionType,
)
from app.services.enrichment import find_salary_sources, mark_salary_transactions


def tx(amount, year=2025, month=1, day=5, counterparty="ТОО Работодатель", **extra):
    return Transaction(
        date=datetime(year, month, day),
        amount=amount,
        type=TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE,
        description="",
        counterparty=counterparty,
        **extra,
    )


def monthly(months=6, amount=500_000, day=5, counterparty="ТОО Работодатель", **extra):
    return [
        tx(amount, month=m + 1, day=day, counterparty=counterparty, **extra)
        for m in range(months)
    ]


# ── Что детектор должен находить ─────────────────────────────────

def test_regular_monthly_income_is_salary():
    """Слова «зарплата» нигде нет — ровно как в реальной выписке, где
    приходит «Пополнение» от ТОО и ничего больше."""
    findings = find_salary_sources(monthly())

    assert len(findings) == 1
    assert findings[0].counterparty == "ТОО Работодатель"
    assert findings[0].months == 6


def test_advance_and_main_payment_still_counts():
    """Аванс 10-го и остаток 25-го — разброс дня около 7, это норма."""
    txs = []
    for m in range(6):
        txs.append(tx(200_000, month=m + 1, day=10))
        txs.append(tx(300_000, month=m + 1, day=25))

    assert len(find_salary_sources(txs)) == 1


def test_finding_explains_itself():
    """Следователю нужен не флаг, а обоснование, которое можно проверить."""
    reason = find_salary_sources(monthly())[0].reason()

    assert "ТОО Работодатель" in reason
    assert "6" in reason


def test_main_employer_comes_first():
    txs = monthly(months=6, amount=500_000) + monthly(
        months=3, amount=80_000, day=20, counterparty="ТОО Подработка"
    )
    findings = find_salary_sources(txs)

    assert [f.counterparty for f in findings][0] == "ТОО Работодатель"


# ── Что детектор помечать НЕ должен ──────────────────────────────

def test_person_is_never_an_employer():
    """Физлицо, регулярно переводящее деньги, — это не работодатель.

    Регресс: пока правило возвращало для «Ержан О.» тип UNKNOWN, он
    проходил проверку и подменял профиль счёта на зарплатный.
    """
    txs = monthly(counterparty="Ержан О.", counterparty_type=CounterpartyType.PERSON)

    assert find_salary_sources(txs) == []


def test_two_payments_are_not_a_pattern():
    """Два одинаковых поступления — это возврат или рассрочка."""
    assert find_salary_sources(monthly(months=2)) == []


def test_irregular_days_are_rejected():
    """Поступления в случайные дни на зарплату не похожи."""
    txs = [tx(500_000, month=m + 1, day=d) for m, d in enumerate([2, 17, 28, 6, 21, 11])]

    assert find_salary_sources(txs) == []


def test_wildly_varying_amounts_are_rejected():
    """Выручка ИП приходит от одного контрагента, но суммами вразнос."""
    txs = [
        tx(amount, month=m + 1, day=5)
        for m, amount in enumerate([50_000, 900_000, 120_000, 2_000_000, 30_000, 700_000])
    ]

    assert find_salary_sources(txs) == []


def test_daily_inflows_are_not_salary():
    """Ежедневные поступления от одного источника — торговая выручка или
    транзит, а не оклад."""
    txs = [tx(50_000, month=1, day=d + 1) for d in range(28)]
    txs += [tx(50_000, month=2, day=d + 1) for d in range(28)]
    txs += [tx(50_000, month=3, day=d + 1) for d in range(28)]

    assert find_salary_sources(txs) == []


@pytest.mark.parametrize("source", [
    "С карты другого банка",
    "Пополнение",
    "Басқа банк картасынан",
    "From another bank",
])
def test_channel_descriptions_are_not_employers(source):
    """Регресс с реальной выписки Kaspi.

    В поле контрагента банк пишет не отправителя, а способ пополнения. По
    поведению такие поступления от зарплаты неотличимы — регулярные,
    сопоставимые, в один день, — и «С карты другого банка» попадало в
    работодатели.
    """
    assert find_salary_sources(monthly(counterparty=source)) == []


@pytest.mark.parametrize("ru,kk,en", [
    (
        "Пополнение Kaspi Gold с карты другого банка",
        "Kaspi Gold-ты басқа банктің картасынан толықтыру",
        "Replenishment of Kaspi Gold from card of other banks",
    ),
    ("Пенсия/пособие", "Зейнетақы/жəрдемақы", "Pension/allowance"),
])
def test_same_operation_in_three_languages_agrees(ru, kk, en):
    """Регресс: один документ, три языка, три разных вывода.

    Kaspi выдаёт выписку на русском, казахском и английском. Стоп-лист был
    русскоязычным, поэтому в русской версии пенсия отсеивалась, а в
    казахской и английской — попадала в работодатели, и счёт пенсионера
    выглядел как счёт наёмного работника.

    Казахский вариант ловится отдельно: порядок слов ставит маркер в
    середину строки, а не в начало. Ə здесь латинская (U+018F) — именно так
    Kaspi печатает казахскую Ә.
    """
    for text in (ru, kk, en):
        assert find_salary_sources(monthly(counterparty=text)) == [], text


def test_pension_is_not_salary():
    """Тоже с реальной выписки: пенсия приходит ровнее любой зарплаты.

    Разделять их важно не из аккуратности: тип счёта задаёт контекстные
    веса всем детекторам, и пенсионер, записанный наёмным работником,
    меняет вывод по всему делу.
    """
    txs = monthly(counterparty="ГЦВП", is_pension_benefit=True)

    assert find_salary_sources(txs) == []


def test_outgoing_payments_are_ignored():
    """Регулярный платёж «в» ту же организацию — аренда или кредит."""
    assert find_salary_sources(monthly(amount=-500_000)) == []


def test_no_transactions_no_findings():
    assert find_salary_sources([]) == []


# ── Проставление флага ───────────────────────────────────────────

def test_mark_sets_flag_only_on_incoming():
    txs = monthly() + [tx(-500_000, month=3, day=7)]

    mark_salary_transactions(txs)

    assert sum(1 for t in txs if t.is_salary) == 6
    assert txs[-1].is_salary is False


def test_existing_flag_is_never_cleared():
    """Флаг мог поставить банк-специфичный парсер по прямому указанию в
    выписке — это надёжнее вывода по поведению."""
    txs = [tx(123_456, month=1, day=3, counterparty="Разовый", is_salary=True)]

    mark_salary_transactions(txs)

    assert txs[0].is_salary is True


@pytest.mark.parametrize("field", ["counterparty", "merchant_name", "description"])
def test_source_falls_back_through_fields(field):
    """В generic-разборе имя источника может лежать в разных полях."""
    txs = []
    for m in range(6):
        t = tx(500_000, month=m + 1, day=5, counterparty="")
        setattr(t, field, "ТОО Работодатель")
        txs.append(t)

    assert len(find_salary_sources(txs)) == 1
