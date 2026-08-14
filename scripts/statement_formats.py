"""Синтетические выписки в форматах, которых нет ни в одном парсере проекта.

Зачем это нужно. Каждый банк-специфичный парсер в `bank_analyzer/parsers/`
кодирует раскладку, которую человек прочитал глазами: какие заголовки, в
каком порядке колонки, как называется тип операции. Это работает ровно до
первого банка, для которого никто такой работы не проделал, — а таких в
Казахстане большинство, и существующие банки меняют формат экспорта.

Файлы отсюда специально не похожи ни на Kaspi, ни на Halyk, ни на Binance:
другие заголовки, другой порядок колонок, другой язык. Детектор отправит их
в GenericParser, и тот заберёт дату, сумму и описание — но не контрагента,
не тип операции и не признаки вроде «зарплата». Именно эта потеря измеряется
в бенчмарке отдельной метрикой: полнота полей.

Персональных данных здесь нет и быть не может: всё генерируется из seed.
Поэтому генератор живёт в репозитории, а реальные выписки — нет.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Sequence


@dataclass(frozen=True)
class StatementFormat:
    """Раскладка выписки: заголовки и способ разложить строку по колонкам."""

    key: str
    label: str
    language: str
    headers: List[str]
    #: Row -> список ячеек в порядке headers
    row_cells: Callable[[object, float], List[str]]
    col_widths: List[int]
    #: Текст шапки документа над таблицей
    preamble: List[str]


def _money(value: float) -> str:
    """Формат сумм, принятый в казахстанских выписках: 1 234 567,89"""
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


# ── Формат 1: вымышленный банк, казахский язык ───────────────────
# Порядок колонок отличается от Halyk, заголовки — тоже. Тип операции и
# контрагент вынесены в отдельные колонки, которых generic-парсер не знает.

KK_OPERATIONS = {
    "Пополнение": "Толықтыру",
    "Покупка": "Зат сатып алу",
    "Перевод": "Аударым",
}


def _kk_cells(row, balance: float) -> List[str]:
    return [
        row.date_str,
        KK_OPERATIONS.get(row.operation, "Басқа"),
        row.counterparty or "—",
        _money(row.amount),
        _money(balance),
    ]


# ── Формат 2: вымышленный банк, русский язык, колонки debit/credit ──
# Сумма разнесена на приход и расход — раскладка, в которой отдельной
# колонки «сумма» вообще нет.

def _ru_cells(row, balance: float) -> List[str]:
    credit = _money(row.amount) if row.amount > 0 else ""
    debit = _money(-row.amount) if row.amount < 0 else ""
    return [
        row.date_str,
        row.operation or "—",
        row.counterparty or "—",
        credit,
        debit,
        _money(balance),
    ]


FORMATS: Dict[str, StatementFormat] = {
    "unseen_kk": StatementFormat(
        key="unseen_kk",
        label="Unseen bank — Kazakh",
        language="kk",
        headers=["Күні", "Операция түрі", "Қарсы агент", "Сомасы", "Қалдық"],
        row_cells=_kk_cells,
        col_widths=[62, 96, 150, 82, 82],
        preamble=[
            "«Алатау Банк» АҚ",
            "Шот бойынша үзінді көшірме",
            "Кезең: 05.01.2025 — 04.07.2025",
        ],
    ),
    "unseen_ru": StatementFormat(
        key="unseen_ru",
        label="Unseen bank — debit/credit columns",
        language="ru",
        headers=["Дата", "Вид операции", "Контрагент", "Приход", "Расход", "Остаток"],
        row_cells=_ru_cells,
        col_widths=[58, 78, 132, 68, 68, 72],
        preamble=[
            "АО «Алатау Банк»",
            "Выписка по текущему счёту",
            "Период: 05.01.2025 — 04.07.2025",
        ],
    ),
}


def write_pdf(rows: Sequence, path: Path, fmt: StatementFormat, font: str,
              opening_balance: float = 1_000_000.0) -> None:
    """Отрисовать выписку в заданном формате как PDF с размеченной таблицей.

    Таблица именно размеченная (с линиями): проверяем не способность найти
    таблицу, а способность понять незнакомые заголовки.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    balance = opening_balance
    data = [list(fmt.headers)]
    for row in rows:
        balance += row.amount
        data.append(fmt.row_cells(row, balance))

    table = Table(data, repeatRows=1, colWidths=fmt.col_widths)
    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("FONT", (0, 0), (-1, -1), font, 7),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ])
    )

    title = ParagraphStyle("t", fontName=font, fontSize=10, leading=13)
    story = [Paragraph(line, title) for line in fmt.preamble]
    story.append(Spacer(1, 12))
    story.append(table)

    doc = SimpleDocTemplate(str(path), pagesize=A4, topMargin=30, bottomMargin=30)
    doc.build(story)
