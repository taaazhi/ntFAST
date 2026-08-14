"""Регресс-тесты на разметку колонок в GenericParser.

Сюда попадает то, что уже один раз молча сломалось. GenericParser — путь по
умолчанию для банков, под которые парсер не писали, поэтому его ошибки не
падают с исключением, а тихо отдают правдоподобный мусор: неверные суммы,
лишние строки, пустые поля. Именно такой отказ опаснее всего для инструмента,
которым пользуются следственные органы: анализ «завершён», риск LOW.
"""
import pytest

from app.services.bank_analyzer.parsers.generic import GenericParser


@pytest.fixture
def parser():
    """Разметка колонок и разбор строки не читают файл — путь не нужен."""
    return GenericParser("unused.pdf")


# ── Заголовки на трёх языках ───────────────────────────────────────────

@pytest.mark.parametrize("header,expected", [
    (["Дата", "Описание", "Сумма", "Остаток"],
     {"date": 0, "description": 1, "amount": 2, "balance": 3}),
    (["Күні", "Сипаттама", "Сомасы", "Қалдық"],
     {"date": 0, "description": 1, "amount": 2, "balance": 3}),
    (["Date", "Description", "Amount", "Balance"],
     {"date": 0, "description": 1, "amount": 2, "balance": 3}),
])
def test_headers_recognised_in_three_languages(parser, header, expected):
    """Казахская выписка уходила в текстовый fallback: заголовки искались
    только по русским словам."""
    assert parser._detect_columns(header) == expected


def test_balance_wins_over_amount(parser):
    """«Шот қалдығы» (остаток по счёту) содержит и «қалдық», и смысл суммы.
    Если «сумма» проверяется первой, парсер берёт остаток вместо оборота —
    и все суммы оказываются растущим балансом, а не транзакциями."""
    mapping = parser._detect_columns(["Күні", "Сомасы", "Шот қалдығы"])
    assert mapping["amount"] == 1
    assert mapping["balance"] == 2


def test_debit_credit_layout_marked_as_split(parser):
    """Раскладка без колонки «сумма» вообще: значение разнесено по приходу
    и расходу."""
    mapping = parser._detect_columns(
        ["Дата", "Вид операции", "Контрагент", "Приход", "Расход", "Остаток"]
    )
    assert mapping["credit"] == 3 and mapping["debit"] == 4
    assert "amount_split" in mapping, "layout must be flagged as split-amount"
    assert "amount" not in mapping


# ── Индекс 0 — валидная колонка, но ложное значение ────────────────────

def test_first_column_date_is_not_treated_as_missing():
    """`if not mapping.get('date')` считало колонку 0 ненайденной и перетирало
    разметку заголовков угадыванием по данным. Дата стоит первой почти во
    всех выписках, так что ломались практически все."""
    parser = GenericParser("unused.pdf")
    table = [
        ["Дата", "Вид операции", "Контрагент", "Приход", "Расход", "Остаток"],
        ["06.01.2025", "Покупка", "Yandex Go poezdka", "", "26 341,94", "973 658,06"],
        ["07.01.2025", "Пополнение", "ТОО Работодатель", "450 000,00", "", "1 423 658,06"],
    ]
    parser._parse_table_adaptive(table)

    assert len(parser.transactions) == 2
    expense, income = parser.transactions
    assert expense.amount == pytest.approx(-26341.94)
    assert income.amount == pytest.approx(450000.00)


def test_split_amount_row_takes_debit_not_balance():
    """Худший из возможных исходов: расход 26 341,94 прочитан как 973 658,06,
    потому что колонка остатка стоит правее и совпала с «последним числом»."""
    parser = GenericParser("unused.pdf")
    mapping = parser._detect_columns(
        ["Дата", "Вид операции", "Контрагент", "Приход", "Расход", "Остаток"]
    )
    tx = parser._parse_row_adaptive(
        ["06.01.2025", "Покупка", "Yandex Go poezdka", "", "26 341,94", "973 658,06"],
        mapping,
    )
    assert tx is not None
    assert tx.amount == pytest.approx(-26341.94)
    assert tx.counterparty == "Yandex Go poezdka"


def test_row_with_neither_debit_nor_credit_is_dropped(parser):
    """Итоговые строки («Всего», «Барлығы») попадают в ту же таблицу и не
    должны становиться транзакцией на ноль."""
    mapping = parser._detect_columns(
        ["Дата", "Вид операции", "Контрагент", "Приход", "Расход", "Остаток"]
    )
    assert parser._parse_row_adaptive(
        ["", "Итого", "", "", "", "973 658,06"], mapping
    ) is None
