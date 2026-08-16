"""Определение разметки таблицы выписки языковой моделью.

Зачем именно здесь. Парсеры написаны под Kaspi, Halyk и Binance; всё
остальное идёт общим путём, который узнаёт колонки по словарю заголовков.
Словарь закрывает те формулировки, которые кто-то видел своими глазами, — а
банков в Казахстане куда больше трёх.

Что происходит с незнакомым банком, измерено: выписка с заголовками
«Күні/Дата», «Мәні», «Кредит теңге», «Сальдо» даёт **0 из 200** верных строк
и 201 лишнюю, причём суммой становится остаток по счёту, а первой
«транзакцией» — строка периода. Отчёт при этом выглядит успешным. Для
инструмента следствия молчаливая подмена сумм опаснее падения.

Модель решает здесь ровно одну задачу — понять, что означают колонки. Она
видит заголовок и несколько строк, а не всю выписку: разметка одна на файл,
поэтому вызов один, дешёвый и не зависящий от числа транзакций. Сами данные
извлекает код — модель не считает и не переписывает суммы.

Ответ модели проверяется на данных, а не принимается на слово: колонка дат
обязана содержать даты, колонка сумм — числа. Разметка, не прошедшая
проверку, отбрасывается, и файл идёт прежним путём по словарю.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

#: Роли колонок, которые умеет разбирать `GenericParser`.
ROLES = ("date", "amount", "credit", "debit", "balance", "counterparty",
         "description", "type", "currency")

LAYOUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "columns": {
            "type": "array",
            "description": "По одной записи на каждую колонку таблицы, по порядку",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "Номер колонки с нуля"},
                    "role": {
                        "type": "string",
                        "enum": list(ROLES) + ["ignore"],
                        "description": (
                            "date — дата операции; amount — сумма со знаком; "
                            "credit — приход; debit — расход; balance — остаток "
                            "после операции; counterparty — вторая сторона; "
                            "description — назначение или детали; type — вид "
                            "операции; currency — валюта; ignore — служебная "
                            "колонка (номер строки, код, комиссия)"
                        ),
                    },
                },
                "required": ["index", "role"],
            },
        }
    },
    "required": ["columns"],
}

SYSTEM_PROMPT = """Ты определяешь структуру таблицы из банковской выписки.

Тебе дан заголовок таблицы и несколько первых строк. Скажи, что означает
каждая колонка.

Важно:
- Названия колонок бывают на русском, казахском и английском, иногда сразу
  на двух языках через дробь.
- Отличай сумму операции от остатка по счёту. Остаток («Сальдо», «Қалдық»,
  «Balance») меняется от строки к строке и обычно много больше суммы —
  перепутать их значит исказить все обороты.
- Если сумма разнесена на две колонки (приход и расход, «Кредит»/«Дебет»),
  отметь их как credit и debit, а не как amount.
- Колонку, которая не несёт данных о транзакции, помечай ignore.
- Не угадывай: если по заголовку и данным роль не ясна, ставь ignore.
"""

_DATE_HINT = re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}")
_NUMBER_HINT = re.compile(r"-?\d[\d\s  ]*[.,]?\d*")


def _looks_like_date(values: Sequence[str]) -> bool:
    filled = [v for v in values if v and v.strip()]
    if not filled:
        return False
    return sum(1 for v in filled if _DATE_HINT.search(v)) >= max(1, len(filled) // 2)


def _looks_numeric(values: Sequence[str]) -> bool:
    filled = [v for v in values if v and v.strip()]
    if not filled:
        return False
    hits = 0
    for value in filled:
        cleaned = re.sub(r"[^\d.,-]", "", value)
        if cleaned and _NUMBER_HINT.fullmatch(cleaned):
            hits += 1
    return hits >= max(1, len(filled) // 2)


def validate_layout(
    layout: Dict[str, int], header: Sequence[str], rows: Sequence[Sequence[str]]
) -> Dict[str, int]:
    """Отбросить роли, не подтверждённые данными.

    Модель может назвать датой колонку с номером строки. Проверка идёт по
    самим данным: то, что объявлено датой, обязано содержать даты, а суммы —
    числа. Непроверяемое поле (контрагент, описание) остаётся как есть.
    """
    if not rows:
        return layout

    checked: Dict[str, int] = {}
    for role, index in layout.items():
        if not isinstance(index, int) or index < 0 or index >= len(header):
            continue

        column = [row[index] if index < len(row) else "" for row in rows]
        if role == "date" and not _looks_like_date(column):
            logger.info("Колонка %d объявлена датой, но дат не содержит", index)
            continue
        if role in ("amount", "credit", "debit", "balance") and not _looks_numeric(column):
            logger.info("Колонка %d объявлена числовой, но чисел не содержит", index)
            continue
        checked[role] = index
    return checked


def detect_layout(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    ai_manager: Any,
    sample: int = 4,
) -> Optional[Dict[str, int]]:
    """Разметка колонок по заголовку и первым строкам.

    Возвращает None, когда модели нет или её ответ не подтвердился данными —
    в этом случае вызывающий код разбирает файл по словарю заголовков, как
    раньше. Отсутствие модели ухудшает разбор незнакомого формата, но не
    ломает разбор знакомого.
    """
    if ai_manager is None or not header:
        return None

    preview = [list(row)[:len(header)] for row in rows[:sample]]
    prompt = (
        "Определи, что означает каждая колонка таблицы.\n\n"
        f"Заголовок: {json.dumps(list(header), ensure_ascii=False)}\n"
        f"Первые строки:\n"
        + "\n".join(json.dumps(row, ensure_ascii=False) for row in preview)
    )

    try:
        import asyncio

        payload, provider = asyncio.run(
            ai_manager.generate_structured(prompt, LAYOUT_SCHEMA, SYSTEM_PROMPT)
        )
    except Exception as exc:
        logger.warning("Разметку определить не удалось (%s) — работаем по словарю", exc)
        return None

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return None
    if not isinstance(payload, dict):
        return None

    layout: Dict[str, int] = {}
    for item in payload.get("columns") or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        index = item.get("index")
        if role in ROLES and isinstance(index, int) and role not in layout:
            layout[role] = index

    checked = validate_layout(layout, header, rows)
    if "date" not in checked:
        # Без даты строка не транзакция; такой разметке доверять нельзя.
        logger.info("Модель не нашла колонку с датой — разметка отброшена")
        return None
    if not any(r in checked for r in ("amount", "credit", "debit")):
        logger.info("Модель не нашла колонку с суммой — разметка отброшена")
        return None

    # Раздельные приход и расход разбираются тем же кодом, что и раньше.
    if "amount" not in checked and "credit" in checked and "debit" in checked:
        checked["amount_split"] = 1

    logger.info("Разметка от %s: %s", provider, checked)
    return checked
