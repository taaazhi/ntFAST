"""Инструменты следственного агента: что модель может спросить у системы.

Замысел. Языковая модель не должна получать выписку целиком и рассуждать о
ней «в уме»: тысяча транзакций не помещается в разумный контекст, а любые
числа, посчитанные моделью, придётся перепроверять. Вместо этого она
задаёт вопросы, а считает система — детерминированно и воспроизводимо.
Модель отвечает за формулировку вопроса и связывание фактов, арифметика и
поиск остаются за кодом.

Три правила, встроенные в этот слой:

1. **Наружу уходит только обезличенное.** Инструменты возвращают уже
   замаскированные имена: даже отвечая на собственный запрос, модель не
   видит ФИО, ИИН, IBAN и номера карт. Иначе анонимизация на входе
   бессмысленна — данные утекут через ответ инструмента.
2. **Ответ ограничен по объёму.** Запрос «покажи все транзакции» вернёт
   срез и честно сообщит, сколько всего нашлось, а не выгрузит выписку.
3. **Ссылки на нормы проверяются, а не пересказываются.** Для этого есть
   отдельный инструмент поверх сверенного корпуса; сочинять номер статьи
   модели незачем.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

#: Сколько транзакций максимум возвращает один вызов. Больше модели не нужно:
#: если ответ упирается в предел, правильный ход — уточнить запрос, а не
#: листать выписку.
MAX_ROWS = 50

#: Схемы инструментов в формате Anthropic tool use.
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "query_transactions",
        "description": (
            "Найти транзакции по фильтрам. Возвращает срез (не более 50 строк) "
            "и общее число совпадений. Имена контрагентов-физлиц обезличены."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "ДД.ММ.ГГГГ включительно"},
                "date_to": {"type": "string", "description": "ДД.ММ.ГГГГ включительно"},
                "min_amount": {"type": "number", "description": "Минимум по модулю суммы"},
                "max_amount": {"type": "number", "description": "Максимум по модулю суммы"},
                "direction": {
                    "type": "string",
                    "enum": ["income", "expense", "any"],
                    "description": "Поступления, списания или всё",
                },
                "counterparty": {
                    "type": "string",
                    "description": "Подстрока в имени контрагента или описании",
                },
                "counterparty_type": {
                    "type": "string",
                    "enum": ["merchant", "person", "bank", "government", "unknown"],
                },
                "limit": {"type": "integer", "description": "Сколько строк вернуть, до 50"},
            },
        },
    },
    {
        "name": "summarise_counterparties",
        "description": (
            "Свод по контрагентам: сколько операций, на какую сумму, в какую "
            "сторону. Отвечает на вопрос «кому и сколько уходило»."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["income", "expense", "any"]},
                "limit": {"type": "integer", "description": "Сколько контрагентов, до 50"},
            },
        },
    },
    {
        "name": "get_period_totals",
        "description": (
            "Обороты по месяцам: поступления, списания, число операций. "
            "Нужен, чтобы увидеть, когда поведение по счёту менялось."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_risk_breakdown",
        "description": (
            "Из чего сложилась оценка риска: сработавшие модули, их вклад, "
            "найденные схемы и контраргументы к ним."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_legislation",
        "description": (
            "Поиск по нормативным актам РК (УК, Налоговый кодекс, закон о "
            "ПОД/ФТ). Возвращает статьи с названием и ссылкой на официальный "
            "текст. Используй, чтобы найти норму, а не вспоминать её номер."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Что ищем, своими словами"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "verify_citation",
        "description": (
            "Проверить ссылку на статью по официальному тексту. Обязательно "
            "вызывай перед тем, как привести норму в выводе: неподтверждённую "
            "ссылку показывать нельзя."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "«УК РК», «НК РК» или «ЗРК О ПОД/ФТ»",
                },
                "number": {"type": "string", "description": "Номер статьи"},
                "quote": {
                    "type": "string",
                    "description": "Цитата, если приводишь её дословно",
                },
            },
            "required": ["code", "number"],
        },
    },
]


@dataclass
class ToolContext:
    """Данные одного анализа, поверх которых работают инструменты.

    `anonymizer` обязателен: он же используется на входе, поэтому одно и то
    же лицо получает одну и ту же метку и в промпте, и в ответах
    инструментов — иначе модель не свяжет их между собой.
    """

    transactions: Sequence[Any]
    fraud_report: Optional[Dict[str, Any]] = None
    anonymizer: Any = None
    corpus_dir: Optional[str] = None
    #: Журнал вызовов — попадает в отчёт, чтобы вывод агента можно было
    #: воспроизвести и проверить.
    calls: List[Dict[str, Any]] = field(default_factory=list)

    def mask(self, name: Optional[str]) -> str:
        if not name:
            return ""
        if self.anonymizer is None:
            return str(name)
        return self.anonymizer.counterparty(str(name))


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _name_of(tx: Any) -> str:
    return (getattr(tx, "counterparty", None) or getattr(tx, "description", None) or "").strip()


def _row(tx: Any, ctx: ToolContext) -> Dict[str, Any]:
    date = getattr(tx, "date", None)
    return {
        "date": date.strftime("%d.%m.%Y") if isinstance(date, datetime) else None,
        "amount": round(float(getattr(tx, "amount", 0) or 0), 2),
        "counterparty": ctx.mask(_name_of(tx)),
        "type": getattr(getattr(tx, "counterparty_type", None), "value", "unknown"),
        "is_salary": bool(getattr(tx, "is_salary", False)),
        "is_cash": bool(getattr(tx, "is_cash_operation", False)),
    }


# ── Реализация инструментов ──────────────────────────────────────

def query_transactions(ctx: ToolContext, **params: Any) -> Dict[str, Any]:
    date_from = _parse_date(params.get("date_from"))
    date_to = _parse_date(params.get("date_to"))
    min_amount = params.get("min_amount")
    max_amount = params.get("max_amount")
    direction = params.get("direction", "any")
    needle = (params.get("counterparty") or "").strip().lower()
    wanted_type = params.get("counterparty_type")
    limit = max(1, min(int(params.get("limit") or MAX_ROWS), MAX_ROWS))

    matched: List[Any] = []
    for tx in ctx.transactions:
        amount = float(getattr(tx, "amount", 0) or 0)
        date = getattr(tx, "date", None)

        if date_from and (not isinstance(date, datetime) or date < date_from):
            continue
        if date_to and (not isinstance(date, datetime) or date > date_to):
            continue
        if direction == "income" and amount <= 0:
            continue
        if direction == "expense" and amount >= 0:
            continue
        if min_amount is not None and abs(amount) < float(min_amount):
            continue
        if max_amount is not None and abs(amount) > float(max_amount):
            continue
        if needle and needle not in _name_of(tx).lower():
            continue
        if wanted_type and getattr(getattr(tx, "counterparty_type", None), "value", None) != wanted_type:
            continue
        matched.append(tx)

    total_amount = sum(float(getattr(t, "amount", 0) or 0) for t in matched)
    return {
        "found": len(matched),
        "returned": min(len(matched), limit),
        "total_amount": round(total_amount, 2),
        "transactions": [_row(tx, ctx) for tx in matched[:limit]],
        # Честно сообщаем об усечении: иначе модель решит, что видит всё.
        "truncated": len(matched) > limit,
    }


def summarise_counterparties(ctx: ToolContext, **params: Any) -> Dict[str, Any]:
    direction = params.get("direction", "any")
    limit = max(1, min(int(params.get("limit") or 20), MAX_ROWS))

    totals: Dict[str, Dict[str, Any]] = {}
    for tx in ctx.transactions:
        amount = float(getattr(tx, "amount", 0) or 0)
        if direction == "income" and amount <= 0:
            continue
        if direction == "expense" and amount >= 0:
            continue

        name = ctx.mask(_name_of(tx)) or "—"
        entry = totals.setdefault(name, {
            "counterparty": name,
            "operations": 0,
            "total_amount": 0.0,
            "type": getattr(getattr(tx, "counterparty_type", None), "value", "unknown"),
        })
        entry["operations"] += 1
        entry["total_amount"] += amount

    ranked = sorted(totals.values(), key=lambda e: abs(e["total_amount"]), reverse=True)
    for entry in ranked:
        entry["total_amount"] = round(entry["total_amount"], 2)

    return {"unique_counterparties": len(ranked), "top": ranked[:limit]}


def get_period_totals(ctx: ToolContext, **_: Any) -> Dict[str, Any]:
    months: Dict[str, Dict[str, Any]] = {}
    for tx in ctx.transactions:
        date = getattr(tx, "date", None)
        if not isinstance(date, datetime):
            continue
        key = date.strftime("%Y-%m")
        entry = months.setdefault(key, {"month": key, "income": 0.0, "expense": 0.0, "count": 0})
        amount = float(getattr(tx, "amount", 0) or 0)
        entry["count"] += 1
        if amount > 0:
            entry["income"] += amount
        else:
            entry["expense"] += abs(amount)

    for entry in months.values():
        entry["income"] = round(entry["income"], 2)
        entry["expense"] = round(entry["expense"], 2)

    return {"months": [months[k] for k in sorted(months)]}


def get_risk_breakdown(ctx: ToolContext, **_: Any) -> Dict[str, Any]:
    report = ctx.fraud_report or {}
    if not report:
        return {"available": False, "reason": "антифрод-анализ не выполнялся"}

    return {
        "available": True,
        "composite_score": report.get("composite_score"),
        "risk_level": report.get("risk_level"),
        "applied_weights": report.get("applied_weights", {}),
        "explained_flags": report.get("explained_flags", []),
        "flagged_patterns": [
            {
                "pattern": p.get("pattern_name"),
                "confidence": p.get("confidence"),
                "reason": p.get("reason"),
                "counter_evidence": p.get("counter_evidence"),
                "legal_articles": p.get("legal_articles", []),
            }
            for p in report.get("flagged_patterns", [])
        ],
    }


def search_legislation(ctx: ToolContext, **params: Any) -> Dict[str, Any]:
    from app.services.legal import suggest_articles

    query = (params.get("query") or "").strip()
    if not query:
        return {"articles": [], "note": "пустой запрос"}

    limit = max(1, min(int(params.get("limit") or 5), 10))
    articles = suggest_articles(query, limit=limit, corpus_dir=ctx.corpus_dir)
    if not articles:
        return {
            "articles": [],
            "note": (
                "ничего не найдено или корпус НПА не собран — "
                "не приводи норму, которую не удалось подтвердить"
            ),
        }
    return {"articles": articles}


def verify_citation(ctx: ToolContext, **params: Any) -> Dict[str, Any]:
    from app.services.legal import verify_citation as check

    result = check(
        params.get("code", ""),
        str(params.get("number", "")),
        quote=params.get("quote"),
        corpus_dir=ctx.corpus_dir,
    )
    return {
        "citation": result.citation,
        "verified": result.is_trustworthy,
        "verdict": result.verdict.value,
        "title": result.title or "",
        "url": result.url or "",
        "detail": result.detail,
    }


TOOLS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "query_transactions": query_transactions,
    "summarise_counterparties": summarise_counterparties,
    "get_period_totals": get_period_totals,
    "get_risk_breakdown": get_risk_breakdown,
    "search_legislation": search_legislation,
    "verify_citation": verify_citation,
}


def run_tool(name: str, ctx: ToolContext, **params: Any) -> Dict[str, Any]:
    """Выполнить инструмент по имени.

    Неизвестное имя и падение инструмента возвращаются как ошибка в ответе,
    а не как исключение: модель должна увидеть, что попытка не удалась, и
    исправиться — уронить весь разбор из-за неверного вызова нельзя.
    """
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"инструмента «{name}» нет", "available": sorted(TOOLS)}

    try:
        result = tool(ctx, **params)
    except Exception as exc:
        logger.warning("Инструмент %s упал: %s", name, exc)
        return {"error": f"инструмент «{name}» завершился ошибкой: {exc}"}

    ctx.calls.append({"tool": name, "params": params})
    return result
